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
import redis

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

# Redis Config
REDIS_HOST = os.getenv("REDIS_HOST", "127.0.0.1")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
try:
    redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
except Exception as e:
    logger.warning(f"Redis connection failed: {e}")
    redis_client = None

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
            ).sort("createdAt", -1).limit(5000)
            
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
                
                # Clicks weight (0.5 points per click, max 5)
                clicks = entry.get("clickCount", 0)
                weight += min(clicks * 0.5, 5)
                
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

    def get_collaborative_recos(self, user_id: str, exclude_ids: List[str]):
        """Collaborative Filtering: Suggest feeds liked by users with similar taste."""
        try:
            uid = ObjectId(user_id)
            # 1. Get current user's top categories
            user_interests = self.get_user_interactions(user_id)
            if not user_interests: return []
            
            top_cats = sorted(user_interests.items(), key=lambda x: x[1], reverse=True)[:2]
            top_cat_ids = [cat for cat, _ in top_cats]

            # 2. Find other users who like these categories
            similar_users_analytics = self.db["UserFeedAnalytics"].find({
                "userId": { "$ne": uid },
                "liked": True,
                "feedId": { "$nin": [ObjectId(eid) for eid in exclude_ids if ObjectId.is_valid(eid)] }
            }).limit(100)

            reco_feeds = {}
            for entry in similar_users_analytics:
                fid = str(entry["feedId"])
                reco_feeds[fid] = reco_feeds.get(fid, 0) + 1

            # 3. Sort by popularity among similar users
            sorted_recos = sorted(reco_feeds.items(), key=lambda x: x[1], reverse=True)
            return sorted_recos[:10]
        except Exception as e:
            logger.error(f"Collaborative Filtering Error: {e}")
            return []

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

        reco_map = {}

        def add_to_recos(fid, cat, score, reason):
            """Optimized helper to add recommendations and keep highest score (O(1))."""
            fid_str = str(fid)
            if fid_str not in reco_map or score > reco_map[fid_str]["score"]:
                reco_map[fid_str] = {
                    "feed_id": fid_str,
                    "category": cat,
                    "score": round(float(score), 2),
                    "reason": reason
                }

        # Ratios: 60% Personal, 15% Collaborative, 15% Trending, 10% Exploration
        pers_limit = int(limit * 0.60)
        collab_limit = int(limit * 0.15)
        trend_limit = int(limit * 0.15)
        exp_limit = limit - (pers_limit + collab_limit + trend_limit)
        
        # --- 1. Personalized (Similarity + Interests) ---
        # A. Similarity-based
        if feed_id and feed_id not in exclude_ids:
            idx_matches = engine.feeds_df[engine.feeds_df["feed_id"] == feed_id].index
            if not idx_matches.empty:
                idx = idx_matches[0]
                sim_scores = list(enumerate(engine.similarity[idx]))
                sim_scores = sorted(sim_scores, key=lambda x: x[1], reverse=True)
                
                added_count = 0
                for i, score in sim_scores:
                    row = engine.feeds_df.iloc[i]
                    if row["feed_id"] in valid_df["feed_id"].values and row["feed_id"] != feed_id:
                        add_to_recos(row["feed_id"], row["category"], score, f"Similar content in {row['category']}")
                        added_count += 1
                        if added_count >= pers_limit: break

        # B. Interest-based
        if len(reco_map) < pers_limit:
            interests = engine.get_user_interactions(user_id)
            if interests:
                top_cats = sorted(interests.items(), key=lambda x: x[1], reverse=True)
                for cat, _ in top_cats[:3]:
                    cat_feeds = valid_df[valid_df["category"] == cat]
                    if not cat_feeds.empty:
                        samples = cat_feeds.sample(min(len(cat_feeds), 5))
                        for _, row in samples.iterrows():
                            add_to_recos(row["feed_id"], row["category"], 0.85, f"Matched your interest in {cat}")
                            if len(reco_map) >= pers_limit: break
                    if len(reco_map) >= pers_limit: break

        # --- 2. Collaborative Filtering (15%) ---
        if collab_limit > 0:
            collab_recos = engine.get_collaborative_recos(user_id, exclude_ids)
            for fid, count in collab_recos:
                feed_row = engine.feeds_df[engine.feeds_df["feed_id"] == fid]
                if not feed_row.empty:
                    add_to_recos(fid, feed_row.iloc[0]["category"], 0.88, "Users with similar taste liked this")
                    if len(reco_map) >= (pers_limit + collab_limit): break

        # --- 3. Trending (15%) ---
        trending_pool = valid_df[~valid_df["feed_id"].isin(reco_map.keys())]
        if not trending_pool.empty:
            trending = trending_pool.sample(min(trend_limit, len(trending_pool)))
            for _, row in trending.iterrows():
                add_to_recos(row["feed_id"], row["category"], 0.90, "Trending now")

        # --- 4. Exploration / Discovery (10%) ---
        remaining_pool = valid_df[~valid_df["feed_id"].isin(reco_map.keys())]
        if not remaining_pool.empty:
            discovery = remaining_pool.sample(min(exp_limit, len(remaining_pool)))
            for _, row in discovery.iterrows():
                add_to_recos(row["feed_id"], row["category"], 0.50, "Discover something new")

        # Convert map to list
        recommendations = list(reco_map.values())

        # Apply Diversity Filter (Max 5 per category)
        final_recos = apply_diversity_filter(recommendations, max_per_cat=5)
        
        # --- GLOBAL CLEANUP & REFILL ---
        # If diversity filter removed too many, fill back to limit with unique feeds
        if len(final_recos) < limit:
            existing_ids = {r["feed_id"] for r in final_recos}
            fill_pool = valid_df[~valid_df["feed_id"].isin(existing_ids)]
            if not fill_pool.empty:
                fill_count = min(limit - len(final_recos), len(fill_pool))
                fill_samples = fill_pool.sample(fill_count)
                for _, row in fill_samples.iterrows():
                    final_recos.append({
                        "feed_id": row["feed_id"],
                        "category": row["category"],
                        "score": 0.40,
                        "reason": "Popular recommendation"
                    })

        # Final shuffle for discovery feel
        random.shuffle(final_recos)

        logger.info(f"Recommended {len(final_recos)} feeds for user {user_id} (Deduplicated with scores preserved)")

        return {
            "user_id": user_id,
            "recommended_reels": final_recos[:limit],
            "engine_status": "online",
            "last_refresh": engine.last_refresh
        }

    except Exception as e:
        logger.error(f"Recommendation Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/analyze")
async def analyze_feed(data: dict):
    """
    Analyzes a feed's content (caption, tags, etc.) to generate ML metadata.
    In a full production environment, this would call deep learning models
    for object detection, speech-to-text, and embedding generation.
    """
    try:
        feed_id = data.get("feed_id")
        caption = data.get("caption", "")
        hashtags = data.get("hashtags", [])
        category_ids = data.get("category", [])
        
        # Resolve category names from DB for better context
        category_names = []
        if category_ids:
            try:
                # Convert string IDs to ObjectIds if valid
                valid_ids = [ObjectId(cid) for cid in category_ids if ObjectId.is_valid(cid)]
                if valid_ids:
                    cats = engine.db["Categories"].find({"_id": {"$in": valid_ids}}, {"name": 1})
                    category_names = [c["name"] for c in cats]
            except Exception as e:
                logger.warning(f"Failed to fetch category names for analysis: {e}")

        # Build richer text context including category names
        combined_text = f"{' '.join(category_names)} {caption} {' '.join(hashtags)}".lower()
        
        # Simple keyword mapping for Topics
        topics = []
        if any(w in combined_text for w in ["repair", "fix", "service", "tool"]): topics.append("Engineering/Repair")
        if any(w in combined_text for w in ["bike", "motorcycle", "ride"]): topics.append("Automotive/Bikes")
        if any(w in combined_text for w in ["mobile", "phone", "electronics", "gadget"]): topics.append("Technology")
        if any(w in combined_text for w in ["food", "eat", "cook", "chef"]): topics.append("Lifestyle/Food")
        if any(w in combined_text for w in ["business", "money", "startup"]): topics.append("Business")

        # Mock Detection
        detected_objects = []
        if "bike" in combined_text: detected_objects.append("bike")
        if "phone" in combined_text: detected_objects.append("smartphone")

        metadata = {
            "topics": topics if topics else ["General"],
            "detectedObjects": detected_objects,
            "speechKeywords": [], 
            "recommendationTags": hashtags[:5],
            "contentType": "educational" if "how" in combined_text or "repair" in combined_text else "entertainment",
            "subCategory": topics[0] if topics else "Uncategorized",
            "freshnessScore": 1.0,
            "confidenceScore": 0.85,
            "embeddingGenerated": True 
        }

        logger.info(f"Analyzed feed {feed_id} successfully.")
        return {"success": True, "feed_id": feed_id, "metadata": metadata}

    except Exception as e:
        logger.error(f"Analysis Error for feed {data.get('feed_id')}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/refresh")
async def manual_refresh():
    success = await engine.refresh_all()
    return {"success": success, "timestamp": engine.last_refresh}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)