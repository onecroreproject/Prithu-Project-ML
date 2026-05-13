from fastapi import FastAPI, Query, HTTPException
import pandas as pd
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from pymongo import MongoClient
from bson import ObjectId
import os
import random
from typing import List, Optional
import asyncio
from datetime import datetime, timedelta
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

app = FastAPI(title="Prithu-ML Recommendation Engine")

# ----------------------------------------
# CONFIGURATION
# ----------------------------------------
MONGO_URI = "mongodb+srv://prithuapp_db_user:eETUIeouSRU7Xipu@cluster0.x0vkq8e.mongodb.net/Prithu-DB?retryWrites=true&w=majority&appName=Cluster0"
DB_NAME = "Prithu-DB"

# Interaction Weights
WEIGHTS = {
    "view": 1,
    "like": 3,
    "watch_20s": 4,
    "share": 5,
    "comment": 6
}

# ----------------------------------------
# DATA ENGINE
# ----------------------------------------
class DataEngine:
    def __init__(self):
        self.feeds_df = pd.DataFrame()
        self.similarity = None
        self.vectorizer = TfidfVectorizer(stop_words="english")
        self.client = MongoClient(MONGO_URI)
        self.db = self.client[DB_NAME]
        self.last_refresh = None

    async def refresh_all(self):
        """Fetch fresh data from MongoDB and rebuild similarity matrix."""
        try:
            # 1. Fetch Approved Feeds
            feeds_col = self.db["Feeds"]
            feeds_cursor = feeds_col.find(
                {"isApproved": True, "isDeleted": False},
                {"_id": 1, "category": 1, "postType": 1, "caption": 1, "hashtags": 1}
            ).sort("createdAt", -1).limit(1000)
            
            feeds_list = []
            for f in feeds_cursor:
                feeds_list.append({
                    "feed_id": str(f["_id"]),
                    "category": str(f.get("category", ["Misc"])[0]),
                    "post_type": f.get("postType", "image"),
                    "content": f"{f.get('caption', '')} {' '.join(f.get('hashtags', []))}"
                })
            
            if not feeds_list:
                logger.warning("No feeds found in database.")
                return False

            self.feeds_df = pd.DataFrame(feeds_list)
            
            # 2. Build TF-IDF & Similarity
            tfidf_matrix = self.vectorizer.fit_transform(self.feeds_df["content"])
            self.similarity = cosine_similarity(tfidf_matrix)
            self.last_refresh = datetime.now()
            
            logger.info(f"ML Engine: Data refreshed. Total feeds: {len(self.feeds_df)}")
            return True
        except Exception as e:
            logger.error(f"ML Engine Refresh Error: {e}")
            return False

    def get_user_interactions(self, user_id: str):
        """Fetch and weight user interactions from the new UserFeedAnalytics collection."""
        try:
            uid = ObjectId(user_id)
            weighted_interests = {}

            # New Analytics Model
            analytics = self.db["UserFeedAnalytics"].find({"userId": uid})
            
            for entry in analytics:
                feed_id = str(entry["feedId"])
                weight = 0
                
                # Align with Node.js weights
                if entry.get("liked"): weight += 3
                if entry.get("saved"): weight += 2
                if entry.get("shared"): weight += 2
                if entry.get("commented"): weight += 1
                
                # Watch time weight (e.g., 1 point per 10 seconds, max 5)
                watch_time = entry.get("watchTime", 0)
                weight += min(watch_time // 10, 5)
                
                # Penalties
                if entry.get("skipped"): weight -= 2
                if entry.get("notInterested"): weight -= 10

                if weight != 0:
                    self._add_weight(weighted_interests, feed_id, weight)

            return weighted_interests
        except Exception as e:
            logger.error(f"Error fetching interactions for {user_id}: {e}")
            return {}

    def _add_weight(self, interests, feed_id, weight):
        feed_row = self.feeds_df[self.feeds_df["feed_id"] == str(feed_id)]
        if not feed_row.empty:
            cat = feed_row.iloc[0]["category"]
            interests[cat] = interests.get(cat, 0) + weight

engine = DataEngine()

@app.on_event("startup")
async def startup_event():
    await engine.refresh_all()

# ----------------------------------------
# UTILS
# ----------------------------------------
def apply_diversity_filter(recos, max_per_cat=5):
    filtered = []
    cat_counts = {}
    for r in recos:
        cat = r["category"]
        if cat_counts.get(cat, 0) < max_per_cat:
            filtered.append(r)
            cat_counts[cat] = cat_counts.get(cat, 0) + 1
    return filtered

# ----------------------------------------
# ENDPOINTS
# ----------------------------------------

@app.get("/recommend")
async def get_recommendations(
    user_id: str, 
    feed_id: Optional[str] = None,
    exclude_ids: List[str] = Query(default=[]),
    limit: int = 10
):
    if engine.feeds_df.empty:
        await engine.refresh_all()

    try:
        # Filter out excluded IDs first
        valid_df = engine.feeds_df
        if exclude_ids:
            valid_df = engine.feeds_df[~engine.feeds_df["feed_id"].isin(exclude_ids)]
        
        if valid_df.empty:
            logger.warning(f"All feeds excluded for user {user_id}. Returning subset of original.")
            valid_df = engine.feeds_df.sample(min(limit, len(engine.feeds_df)))

        recommendations = []
        pers_limit = int(limit * 0.7)
        
        # --- 1. Personalized (Similarity + Interests) ---
        # A. Similarity-based
        if feed_id and feed_id not in exclude_ids:
            idx_matches = engine.feeds_df[engine.feeds_df["feed_id"] == feed_id].index
            if not idx_matches.empty:
                idx = idx_matches[0]
                sim_scores = list(enumerate(engine.similarity[idx]))
                # Sort and filter by valid_df
                sim_scores = sorted(sim_scores, key=lambda x: x[1], reverse=True)
                
                added_count = 0
                for i, score in sim_scores:
                    row = engine.feeds_df.iloc[i]
                    if row["feed_id"] in valid_df["feed_id"].values and row["feed_id"] != feed_id:
                        recommendations.append({
                            "feed_id": row["feed_id"],
                            "category": row["category"],
                            "score": round(float(score), 2),
                            "reason": f"Similar content in {row['category']}"
                        })
                        added_count += 1
                        if added_count >= pers_limit: break

        # B. Interest-based
        if len(recommendations) < pers_limit:
            interests = engine.get_user_interactions(user_id)
            if interests:
                top_cats = sorted(interests.items(), key=lambda x: x[1], reverse=True)
                for cat, _ in top_cats[:3]:
                    cat_feeds = valid_df[valid_df["category"] == cat]
                    if not cat_feeds.empty:
                        samples = cat_feeds.sample(min(len(cat_feeds), 3))
                        for _, row in samples.iterrows():
                            if row["feed_id"] not in [r["feed_id"] for r in recommendations]:
                                recommendations.append({
                                    "feed_id": row["feed_id"],
                                    "category": row["category"],
                                    "score": 0.85,
                                    "reason": f"Matched your interest in {cat}"
                                })
                            if len(recommendations) >= pers_limit: break
                    if len(recommendations) >= pers_limit: break

        # --- 2. Trending (20%) ---
        trend_limit = max(1, int(limit * 0.2))
        trending_pool = valid_df[~valid_df["feed_id"].isin([r["feed_id"] for r in recommendations])]
        if not trending_pool.empty:
            trending = trending_pool.sample(min(trend_limit, len(trending_pool)))
            for _, row in trending.iterrows():
                recommendations.append({
                    "feed_id": row["feed_id"],
                    "category": row["category"],
                    "score": 0.90,
                    "reason": "Trending now"
                })

        # --- 3. Exploration (10%) ---
        exp_limit = max(1, limit - len(recommendations))
        remaining_pool = valid_df[~valid_df["feed_id"].isin([r["feed_id"] for r in recommendations])]
        if not remaining_pool.empty:
            discovery = remaining_pool.sample(min(exp_limit, len(remaining_pool)))
            for _, row in discovery.iterrows():
                recommendations.append({
                    "feed_id": row["feed_id"],
                    "category": row["category"],
                    "score": 0.50,
                    "reason": "Discover something new"
                })

        # Apply Diversity Filter (Max 5 per category)
        final_recos = apply_diversity_filter(recommendations, max_per_cat=5)
        
        # Final shuffle for discovery feel
        random.shuffle(final_recos)

        logger.info(f"Recommended {len(final_recos)} feeds for user {user_id} (Excluded: {len(exclude_ids)})")

        return {
            "user_id": user_id,
            "recommended_reels": final_recos[:limit],
            "engine_status": "online",
            "last_refresh": engine.last_refresh
        }

    except Exception as e:
        logger.error(f"Recommendation Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/refresh")
async def manual_refresh():
    success = await engine.refresh_all()
    return {"success": success, "timestamp": engine.last_refresh}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)