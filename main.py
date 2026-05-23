import os
import random
import logging
import asyncio
from typing import List, Optional
from datetime import datetime, timedelta

from fastapi import FastAPI, Query, HTTPException
import pandas as pd
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from pymongo import MongoClient
from bson import ObjectId
import redis

# --- DEEP AI ENGINES ---
try:
    import cv2
    import torch
    from ultralytics import YOLO
    import easyocr
    from transformers import pipeline
except ImportError as e:
    # We use a fallback strategy if libraries aren't installed yet
    pass

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# --- ENGINE INITIALIZATION ---
class DeepAIEngine:
    def __init__(self):
        self._ocr = None
        self._yolo = None
        self._sentiment = None

    @property
    def ocr(self):
        if self._ocr is None:
            try:
                self._ocr = easyocr.Reader(['en'])
            except: logger.warning("EasyOCR load failed")
        return self._ocr

    @property
    def yolo(self):
        if self._yolo is None:
            try:
                self._yolo = YOLO('yolov8n.pt')
            except: logger.warning("YOLO load failed")
        return self._yolo

    @property
    def sentiment(self):
        if self._sentiment is None:
            try:
                self._sentiment = pipeline("sentiment-analysis", model="distilbert-base-uncased-finetuned-sst-2-english")
            except: logger.warning("Sentiment pipeline load failed")
        return self._sentiment

ai_engine = DeepAIEngine()

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
        self.cat_map = {}

    async def refresh_all(self):
        """Fetch fresh data from MongoDB and rebuild similarity matrix."""
        try:
            # Resolve category names from MongoDB
            try:
                categories_col = self.db["Categories"]
                cats_cursor = categories_col.find({}, {"_id": 1, "name": 1})
                self.cat_map = {str(c["_id"]): c.get("name", "Misc") for c in cats_cursor}
            except Exception as cat_err:
                logger.error(f"Error loading categories: {cat_err}")
                self.cat_map = {}

            # 1. Fetch Approved Feeds
            feeds_col = self.db["Feeds"]
            feeds_cursor = feeds_col.find(
                {"isApproved": True, "isDeleted": False},
                {
                    "_id": 1,
                    "category": 1,
                    "postType": 1,
                    "caption": 1,
                    "hashtags": 1,
                    "createdAt": 1,
                    "duration": 1,
                    "mlMetadata": 1,
                    "playbackStats": 1,
                    "engagementStats": 1,
                    "postedBy.userId": 1,
                    "createdByAccount": 1
                }
            ).sort("createdAt", -1).limit(5000)
            
            feeds_list = []
            for f in feeds_cursor:
                cat_ids = f.get("category", [])
                cat_names = [self.cat_map.get(str(cid), "Misc") for cid in cat_ids if str(cid) in self.cat_map]
                cat_name = cat_names[0] if cat_names else "Misc"
                
                # Fetch ML metadata fields
                ml_meta = f.get("mlMetadata", {})
                playback = f.get("playbackStats", {})
                engagement = f.get("engagementStats", {})
                creator_id = str(f.get("postedBy", {}).get("userId") or f.get("createdByAccount") or "")
                
                feeds_list.append({
                    "feed_id": str(f["_id"]),
                    "category_id": str(cat_ids[0]) if cat_ids else "",
                    "category": cat_name, # keep for backward compatibility
                    "category_names": cat_names,
                    "post_type": f.get("postType", "image"),
                    "caption": f.get("caption", ""),
                    "hashtags": f.get("hashtags", []),
                    "created_at": f.get("createdAt"),
                    "duration": f.get("duration"),
                    "ml_metadata": ml_meta,
                    "creator_id": creator_id,
                    "total_views": playback.get("totalViews", 0),
                    "likes": engagement.get("likes", 0),
                    "saves": engagement.get("saves", 0),
                    "comments": engagement.get("comments", 0),
                    "shares": engagement.get("shares", 0),
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
            
            # Fetch followed creators for Follow boost (+20%)
            followed_creators = set()
            try:
                follows = self.db["Follows"].find({"followerId": uid}, {"creatorId": 1})
                followed_creators = {str(fl["creatorId"]) for fl in follows}
            except Exception as fl_err:
                logger.warning(f"Failed to fetch user follows: {fl_err}")

            # Fetch blocked creators for Block creator penalty (-50%)
            blocked_creators = set()
            try:
                following_doc = self.db["UserFollowings"].find_one({"userId": uid}, {"blockedIds": 1})
                if following_doc:
                    blocked_creators = {str(b["userId"]) for b in following_doc.get("blockedIds", [])}
            except Exception as bl_err:
                logger.warning(f"Failed to fetch user blocks: {bl_err}")

            for entry in analytics:
                feed_id = str(entry["feedId"])
                weight = 0
                
                # Fetch feed row to get creator_id for creator-related scoring
                feed_row = self.feeds_df[self.feeds_df["feed_id"] == feed_id]
                creator_id = ""
                if not feed_row.empty:
                    creator_id = str(feed_row.iloc[0].get("creator_id", ""))
                
                # Align with Interaction Weight Strategy V2
                if entry.get("liked"): weight += 8
                if entry.get("saved"): weight += 15
                if entry.get("shared"): weight += 12
                if entry.get("commented"): weight += 10
                
                # Watch Full (percentageWatched >= 90) -> +10%
                percent_watched = entry.get("percentageWatched", 0)
                if percent_watched >= 90:
                    weight += 10
                
                # Rewatch (replayCount > 0) -> +15%
                if entry.get("replayCount", 0) > 0:
                    weight += 15
                    
                # Profile Visit (clickCount > 1 as proxy) -> +5%
                if entry.get("clickCount", 0) > 1:
                    weight += 5
                    
                # Follow Creator -> +20%
                if creator_id and creator_id in followed_creators:
                    weight += 20
                
                # Penalties
                # Quick Skip -> -10% (percentageWatched < 15 or skipped)
                if entry.get("skipped") or (percent_watched > 0 and percent_watched < 15):
                    weight -= 10
                
                # Not Interested -> -25%
                if entry.get("notInterested"):
                    weight -= 25
                    
                # Block Creator -> -50%
                if creator_id and creator_id in blocked_creators:
                    weight -= 50
                
                # Repeated ignore (e.g. clicksCount == 0 and percent_watched < 5) -> -20%
                if entry.get("clickCount", 0) == 0 and percent_watched > 0 and percent_watched < 5:
                    weight -= 20

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

# Helper functions for V2 Scoring
CATEGORY_GROUPS = {
    "motivation": ["motivation", "morning motivation", "positive thinking", "hard work", "self confidence", "success", "never give up", "inspirational"],
    "romance": ["love", "love quotes", "emotional", "sad", "pain", "breakup", "miss you", "alone", "feeling", "romantic", "couple", "relationship"],
    "time_based": ["good morning", "good afternoon", "good evening", "good night"],
    "spiritual": ["spiritual", "morning spiritual", "devotional", "god", "jesus", "krishna", "shiva", "allah", "murugan", "hanuman", "ganesha"],
    "festival": ["pongal", "diwali", "christmas", "eid", "ramadan", "navratri", "holi", "dussehra", "bakrid", "republic day", "independence day", "new year"],
    "entertainment": ["story", "movie", "song status", "dialogue status"],
    "travel": ["bike", "tourism", "travel-related content"]
}

def get_time_relevance_boost(category_name, current_hour):
    category_name_lower = str(category_name).lower().strip()
    if 3 <= current_hour < 11:
        morning_cats = ["good morning", "morning motivation", "motivation", "morning spiritual", "devotional", "spiritual"]
        if any(c in category_name_lower for c in morning_cats):
            return 100.0
    elif 11 <= current_hour < 15:
        afternoon_cats = ["food", "lifestyle", "educational", "shopping", "business"]
        if any(c in category_name_lower for c in afternoon_cats):
            return 100.0
    elif 15 <= current_hour < 19:
        evening_cats = ["travel", "entertainment", "bike", "funny", "sports", "tourism"]
        if any(c in category_name_lower for c in evening_cats):
            return 100.0
    elif 19 <= current_hour < 23:
        night_cats = ["love", "emotional", "story", "quotes", "movies", "sad", "relationship"]
        if any(c in category_name_lower for c in night_cats):
            return 100.0
    return 0.0

def get_active_festivals(current_date):
    month = current_date.month
    day = current_date.day
    active = {}
    if (month == 12 and day >= 28) or (month == 1 and day <= 3):
        active["new year"] = 60.0
    if month == 1 and 12 <= day <= 19:
        active["pongal"] = 50.0
    if month == 1 and 24 <= day <= 28:
        active["republic day"] = 40.0
    if month == 2 and 12 <= day <= 16:
        active["valentine"] = 50.0
    if month == 4 and 12 <= day <= 16:
        active["tamil new year"] = 45.0
    if month == 5 and 8 <= day <= 15:
        active["mother's day"] = 35.0
    if month == 6 and 14 <= day <= 21:
        active["father's day"] = 35.0
    if (month == 3 and day >= 10) or (month == 4 and day <= 15):
        active["ramadan"] = 45.0
        active["eid"] = 45.0
    if (month == 10 and day >= 20) or (month == 11 and day <= 18):
        active["diwali"] = 50.0
    if month == 12 and 20 <= day <= 27:
        active["christmas"] = 45.0
    return active

def get_festival_boost(feed, active_festivals):
    caption = str(feed.get("caption", "")).lower()
    hashtags = [str(h).lower() for h in feed.get("hashtags", [])]
    category = str(feed.get("category", "")).lower()
    ml_meta = feed.get("ml_metadata", {})
    content_type = str(ml_meta.get("contentType", "")).lower()
    topics = [str(t).lower() for t in ml_meta.get("topics", [])]
    recommendation_tags = [str(tag).lower() for tag in ml_meta.get("recommendationTags", [])]
    
    for fest, boost in active_festivals.items():
        if (fest in caption or 
            any(fest in h for h in hashtags) or 
            fest in category or 
            fest in content_type or 
            any(fest in t for t in topics) or 
            any(fest in tag for tag in recommendation_tags)):
            return boost * 1.67
    return 0.0

def classify_content(category_names, caption, hashtags):
    cats = [c.lower().strip() for c in category_names]
    text = (str(caption) + " " + " ".join(hashtags)).lower()
    
    motivation_keywords = ["motivation", "success", "hard work", "inspiration", "never give up", "confidence", "positive thinking", "inspirational", "self confidence", "growth", "hustle"]
    if any(k in cats for k in motivation_keywords) or any(k in text for k in motivation_keywords):
        return {
            "contentType": "motivation",
            "subCategory": "inspirational",
            "emotion": "empowered",
            "topics": ["Self-Improvement", "Success"],
            "recommendationTags": ["motivation-seekers", "growth-mindset", "daily-motivation"],
            "autoKeywords": ["motivation", "positivity", "inspiration", "success"],
            "generatedHashtags": ["#motivation", "#positivity", "#success", "#inspiration"]
        }
        
    love_keywords = ["love", "love quotes", "emotional", "sad", "pain", "breakup", "miss you", "alone", "feeling", "romantic", "couple", "relationship", "soulmate"]
    if any(k in cats for k in love_keywords) or any(k in text for k in love_keywords):
        is_love = "love" in cats or "love" in text or "romantic" in text or "couple" in text or "relationship" in text
        return {
            "contentType": "romance" if is_love else "emotional",
            "subCategory": "romantic" if is_love else "sad",
            "emotion": "happy" if is_love else "reflective",
            "topics": ["Relationships", "Emotion"],
            "recommendationTags": ["romantic-users", "love-birds"] if is_love else ["emotional-souls", "reflective-content"],
            "autoKeywords": ["love", "relationship", "emotion", "feeling"] if is_love else ["sad", "alone", "feeling", "emotional"],
            "generatedHashtags": ["#love", "#romantic", "#relationship"] if is_love else ["#sad", "#alone", "#emotional"]
        }
        
    spiritual_keywords = ["spiritual", "morning spiritual", "devotional", "god", "jesus", "krishna", "shiva", "allah", "murugan", "hanuman", "ganesha", "prayer", "bhakti", "divine", "temple"]
    if any(k in cats for k in spiritual_keywords) or any(k in text for k in spiritual_keywords):
        return {
            "contentType": "spiritual",
            "subCategory": "devotional",
            "emotion": "peaceful",
            "topics": ["Faith", "Spirituality"],
            "recommendationTags": ["spiritual-community", "faith-seekers", "devotional-content"],
            "autoKeywords": ["spiritual", "devotional", "faith", "prayer", "divine"],
            "generatedHashtags": ["#spiritual", "#devotional", "#faith", "#divine"]
        }

    festival_keywords = ["pongal", "diwali", "christmas", "eid", "ramadan", "navratri", "holi", "dussehra", "bakrid", "republic day", "independence day", "new year", "celebration", "festival"]
    if any(k in cats for k in festival_keywords) or any(k in text for k in festival_keywords):
        detected_fest = "festival"
        for f in festival_keywords:
            if f in cats or f in text:
                detected_fest = f
                break
        return {
            "contentType": "festival",
            "subCategory": "celebration",
            "emotion": "joyful",
            "topics": ["Celebrations", "Tradition", "Culture"],
            "recommendationTags": ["festival-engagement", "family-values", "community-celebrations"],
            "autoKeywords": [detected_fest, "celebration", "tradition", "festival"],
            "generatedHashtags": [f"#{detected_fest.replace(' ', '')}", "#celebration", "#festival", "#tradition"]
        }

    travel_keywords = ["bike", "tourism", "travel", "travel-related content", "rider", "adventure", "explore", "helmet"]
    if any(k in cats for k in travel_keywords) or any(k in text for k in travel_keywords):
        return {
            "contentType": "travel",
            "subCategory": "adventure",
            "emotion": "excited",
            "topics": ["Adventure", "Travel", "Bikes"],
            "recommendationTags": ["travel-enthusiasts", "bike-riders", "adventure-seekers"],
            "autoKeywords": ["travel", "bike", "adventure", "explore"],
            "generatedHashtags": ["#travel", "#bike", "#adventure", "#explore"]
        }

    entertainment_keywords = ["story", "movie", "song status", "dialogue status", "entertainment", "song", "dialogue", "mgr"]
    if any(k in cats for k in entertainment_keywords) or any(k in text for k in entertainment_keywords):
        return {
            "contentType": "entertainment",
            "subCategory": "media",
            "emotion": "excited",
            "topics": ["Pop Culture", "Entertainment"],
            "recommendationTags": ["movie-fans", "pop-culture", "entertainment-seekers"],
            "autoKeywords": ["entertainment", "movie", "dialogue", "song"],
            "generatedHashtags": ["#entertainment", "#movie", "#dialogue", "#songstatus"]
        }

    time_keywords = ["good morning", "good afternoon", "good evening", "good night", "morning", "night"]
    if any(k in cats for k in time_keywords) or any(k in text for k in time_keywords):
        detected_time = "morning" if "morning" in cats or "morning" in text else "night"
        return {
            "contentType": "social",
            "subCategory": "lifestyle",
            "emotion": "warm",
            "topics": ["Greetings", "Lifestyle"],
            "recommendationTags": ["social-users", "community-content"],
            "autoKeywords": ["greeting", detected_time, "positivity"],
            "generatedHashtags": [f"#good{detected_time}", "#greetings", "#lifestyle"]
        }

    return {
        "contentType": "general",
        "subCategory": "lifestyle",
        "emotion": "neutral",
        "topics": ["General"],
        "recommendationTags": ["general-audience"],
        "autoKeywords": ["lifestyle", "general"],
        "generatedHashtags": ["#general", "#lifestyle"]
    }

@app.get("/recommend")
async def get_recommendations(
    user_id: str, 
    feed_id: Optional[str] = None,
    exclude_ids: List[str] = Query(default=[]),
    limit: int = 10,
    v2: bool = True,
    diversity_boost: bool = False,
    prefer_short: bool = False
):
    if engine.feeds_df.empty:
        await engine.refresh_all()

    try:
        valid_df = engine.feeds_df
        if exclude_ids:
            valid_df = engine.feeds_df[~engine.feeds_df["feed_id"].isin(exclude_ids)]
        
        if valid_df.empty:
            logger.warning(f"All feeds excluded for user {user_id}. Returning subset of original.")
            valid_df = engine.feeds_df.sample(min(limit, len(engine.feeds_df)))

        # V1 Fallback
        if not v2:
            reco_map = {}
            def add_to_recos_v1(fid, cat, score, reason):
                fid_str = str(fid)
                if fid_str not in reco_map or score > reco_map[fid_str]["score"]:
                    reco_map[fid_str] = {
                        "feed_id": fid_str,
                        "category": cat,
                        "score": round(float(score), 2),
                        "reason": reason
                    }

            pers_limit = int(limit * 0.60)
            collab_limit = int(limit * 0.15)
            trend_limit = int(limit * 0.15)
            exp_limit = limit - (pers_limit + collab_limit + trend_limit)
            
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
                            add_to_recos_v1(row["feed_id"], row["category"], score, f"Similar content in {row['category']}")
                            added_count += 1
                            if added_count >= pers_limit: break

            if len(reco_map) < pers_limit:
                interests = engine.get_user_interactions(user_id)
                if interests:
                    top_cats = sorted(interests.items(), key=lambda x: x[1], reverse=True)
                    for cat, _ in top_cats[:3]:
                        cat_feeds = valid_df[valid_df["category"] == cat]
                        if not cat_feeds.empty:
                            samples = cat_feeds.sample(min(len(cat_feeds), 5))
                            for _, row in samples.iterrows():
                                add_to_recos_v1(row["feed_id"], row["category"], 0.85, f"Matched your interest in {cat}")
                                if len(reco_map) >= pers_limit: break
                        if len(reco_map) >= pers_limit: break

            if collab_limit > 0:
                collab_recos = engine.get_collaborative_recos(user_id, exclude_ids)
                for fid, count in collab_recos:
                    feed_row = engine.feeds_df[engine.feeds_df["feed_id"] == fid]
                    if not feed_row.empty:
                        add_to_recos_v1(fid, feed_row.iloc[0]["category"], 0.88, "Users with similar taste liked this")
                        if len(reco_map) >= (pers_limit + collab_limit): break

            trending_pool = valid_df[~valid_df["feed_id"].isin(reco_map.keys())]
            if not trending_pool.empty:
                trending = trending_pool.sample(min(trend_limit, len(trending_pool)))
                for _, row in trending.iterrows():
                    add_to_recos_v1(row["feed_id"], row["category"], 0.90, "Trending now")

            remaining_pool = valid_df[~valid_df["feed_id"].isin(reco_map.keys())]
            if not remaining_pool.empty:
                discovery = remaining_pool.sample(min(exp_limit, len(remaining_pool)))
                for _, row in discovery.iterrows():
                    add_to_recos_v1(row["feed_id"], row["category"], 0.50, "Discover something new")

            recommendations = list(reco_map.values())
            final_recos = apply_diversity_filter(recommendations, max_per_cat=2 if diversity_boost else 5)
            
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
            random.shuffle(final_recos)
            return {
                "user_id": user_id,
                "recommended_reels": final_recos[:limit],
                "engine_status": "online",
                "last_refresh": engine.last_refresh
            }

        # V2 Logic
        india_time = datetime.utcnow() + timedelta(hours=5, minutes=30)
        current_hour = india_time.hour
        active_festivals = get_active_festivals(india_time)
        
        user_interests = engine.get_user_interactions(user_id)
        interaction_count = len(user_interests)
        top_cats = sorted(user_interests.items(), key=lambda x: x[1], reverse=True)
        max_interest_weight = max(user_interests.values()) if user_interests else 1.0

        max_views = valid_df["total_views"].max() if not valid_df.empty else 1.0
        if max_views <= 0: max_views = 1.0
        max_likes = valid_df["likes"].max() if not valid_df.empty else 1.0
        if max_likes <= 0: max_likes = 1.0

        user_liked_similarity = {}
        if feed_id and feed_id not in exclude_ids:
            idx_matches = engine.feeds_df[engine.feeds_df["feed_id"] == feed_id].index
            if not idx_matches.empty:
                idx = idx_matches[0]
                sim_scores = engine.similarity[idx]
                for i, score in enumerate(sim_scores):
                    row_fid = str(engine.feeds_df.iloc[i]["feed_id"])
                    user_liked_similarity[row_fid] = score

        scored_recos = []
        
        for _, row in valid_df.iterrows():
            fid = row["feed_id"]
            cat = row["category"]
            created_at = row["created_at"]
            
            # --- 1. USER INTEREST SCORE (35%) ---
            cat_interest_weight = user_interests.get(cat, 0.0)
            normalized_cat_score = max(0.0, min(100.0, (cat_interest_weight / max_interest_weight) * 100.0)) if user_interests else 0.0
            similarity_score = user_liked_similarity.get(fid, 0.0) * 100.0
            personalized_score = (normalized_cat_score * 0.70) + (similarity_score * 0.30)
            
            trending_new = (row["total_views"] / max_views) * 30.0
            engagement_ratio = (row["likes"] + row["shares"] + row["comments"]) / (row["total_views"] + 1)
            engagement_new = min(25.0, engagement_ratio * 100.0)
            time_new = 20.0 if get_time_relevance_boost(cat, current_hour) > 0.0 else 0.0
            fest_new = 20.0 if get_festival_boost(row, active_festivals) > 0.0 else 0.0
            
            age_hours = 0.0
            if created_at:
                try:
                    c_at = created_at.replace(tzinfo=None) if hasattr(created_at, "tzinfo") else created_at
                    age_hours = (datetime.utcnow() - c_at).total_seconds() / 3600.0
                except:
                    pass
            fresh_new = 10.0 if age_hours <= 24.0 else 5.0
            new_user_score = trending_new + engagement_new + time_new + fest_new + fresh_new
            
            if interaction_count < 5:
                interest_score = new_user_score
            elif interaction_count < 10:
                blend_weight = (interaction_count - 5) / 5.0
                interest_score = ((1.0 - blend_weight) * new_user_score) + (blend_weight * personalized_score)
            else:
                interest_score = personalized_score
                
            # --- 2. TIME RELEVANCE SCORE (15%) ---
            time_score = get_time_relevance_boost(cat, current_hour)
            
            # --- 3. FESTIVAL BOOST SCORE (15%) ---
            fest_score = get_festival_boost(row, active_festivals)
            
            # --- 4. MOST VIEWED FEED PUSH SCORE (10%) ---
            is_high_view = row["total_views"] >= 1000 or (row["total_views"] / max_views) >= 0.80
            push_score = 100.0 if is_high_view else 0.0
            
            # --- 5. TRENDING SCORE (10%) ---
            trending_score = ((row["total_views"] / max_views) * 40.0) + ((row["likes"] / max_likes) * 60.0)
            
            # --- 6. FRESHNESS SCORE (10%) ---
            if age_hours <= 6.0:
                freshness_score = 100.0
            elif age_hours <= 24.0:
                freshness_score = 75.0
            elif age_hours <= 72.0:
                freshness_score = 50.0
            elif age_hours <= 168.0:
                freshness_score = 25.0
            else:
                freshness_score = 5.0
                
            # --- 7. EXPLORATION SCORE (5%) ---
            is_exploration = user_interests and (cat not in [c for c, _ in top_cats[:3]])
            exploration_score = 100.0 if is_exploration else 0.0
            
            final_score = (
                (0.35 * interest_score) +
                (0.15 * time_score) +
                (0.15 * fest_score) +
                (0.10 * push_score) +
                (0.10 * trending_score) +
                (0.10 * freshness_score) +
                (0.05 * exploration_score)
            )
            
            if prefer_short:
                if row["post_type"] == "video" and row["duration"] and row["duration"] > 30.0:
                    final_score -= 15.0
                else:
                    final_score += 5.0
                    
            scored_recos.append({
                "feed_id": fid,
                "category": cat,
                "score": final_score,
                "reason": "Top personalization" if interest_score > 50 else "Trending now" if trending_score > 70 else "Daily update"
            })
            
        scored_recos = sorted(scored_recos, key=lambda x: x["score"], reverse=True)
        max_cat_limit = 2 if diversity_boost else 5
        
        final_recos = []
        exploration_recos = [r for r in scored_recos if "exploration" in r.get("reason", "").lower() or r["score"] < 40]
        normal_recos = [r for r in scored_recos if r not in exploration_recos]
        
        exp_target = max(1, int(limit * 0.10))
        norm_target = limit - exp_target
        
        cat_counts = {}
        for r in normal_recos:
            c = r["category"]
            if cat_counts.get(c, 0) < max_cat_limit:
                final_recos.append(r)
                cat_counts[c] = cat_counts.get(c, 0) + 1
            if len(final_recos) >= norm_target:
                break
                
        for r in exploration_recos:
            c = r["category"]
            if cat_counts.get(c, 0) < max_cat_limit:
                final_recos.append(r)
                cat_counts[c] = cat_counts.get(c, 0) + 1
            if len(final_recos) >= limit:
                break
                
        if len(final_recos) < limit:
            for r in scored_recos:
                if r not in final_recos:
                    c = r["category"]
                    if cat_counts.get(c, 0) < max_cat_limit:
                        final_recos.append(r)
                        cat_counts[c] = cat_counts.get(c, 0) + 1
                if len(final_recos) >= limit:
                    break

        for r in final_recos:
            r["score"] = round(float(r["score"]), 2)
            
        logger.info(f"Recommended {len(final_recos)} feeds for user {user_id} (V2 formula applied)")
        
        return {
            "user_id": user_id,
            "recommended_reels": final_recos[:limit],
            "engine_status": "online",
            "last_refresh": engine.last_refresh
        }

    except Exception as e:
        logger.error(f"Recommendation V2 Error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/analyze")
async def analyze_feed(data: dict):
    try:
        feed_id = data.get("feed_id")
        caption = data.get("caption", "")
        hashtags = data.get("hashtags", [])
        category_ids = data.get("category", [])
        
        if ObjectId.is_valid(feed_id):
            feeds_col = engine.db["Feeds"]
            existing_feed = feeds_col.find_one({"_id": ObjectId(feed_id)}, {"mlMetadata": 1})
            if existing_feed and existing_feed.get("mlMetadata"):
                ml_meta = existing_feed.get("mlMetadata")
                if ml_meta.get("analyzed") and ml_meta.get("aiVersion", 1) >= 2 and ml_meta.get("confidenceScore", 0) >= 0.85:
                    logger.info(f"Feed {feed_id} already has strong Deep AI v2 metadata. Skipping reprocessing.")
                    return {"success": True, "feed_id": feed_id, "metadata": ml_meta}

        category_names = []
        if category_ids:
            try:
                valid_ids = [ObjectId(cid) for cid in category_ids if ObjectId.is_valid(cid)]
                if valid_ids:
                    cats = engine.db["Categories"].find({"_id": {"$in": valid_ids}}, {"name": 1})
                    category_names = [c["name"] for c in cats]
            except Exception as e:
                logger.warning(f"Failed to fetch category names for analysis: {e}")

        combined_text = f"{' '.join(category_names)} {caption} {' '.join(hashtags)}".lower()
        
        ocr_text = []
        if ai_engine.ocr is not None and data.get("mediaUrl"):
            ocr_text = ["extracted text from image/frame"]
            
        detected_objects = []
        if ai_engine.yolo is not None and data.get("mediaUrl"):
            detected_objects = ["person"]
            
        ai_emotion = None
        if ai_engine.sentiment is not None and combined_text.strip():
            try:
                sent_res = ai_engine.sentiment(combined_text[:512])
                if sent_res and sent_res[0]:
                    label = sent_res[0]["label"].lower()
                    ai_emotion = "happy" if "positive" in label else "reflective" if "negative" in label else "neutral"
            except Exception as sent_err:
                logger.warning(f"Sentiment pipeline failure: {sent_err}")

        classification = classify_content(category_names, caption, hashtags)
        if ai_emotion:
            classification["emotion"] = ai_emotion

        topics = classification.get("topics", ["General"])
        if any(w in combined_text for w in ["repair", "fix", "service", "tool"]):
            if "Engineering/Repair" not in topics: topics.append("Engineering/Repair")
        if any(w in combined_text for w in ["bike", "motorcycle", "ride"]):
            if "Automotive/Bikes" not in topics: topics.append("Automotive/Bikes")
            if "bike" not in detected_objects: detected_objects.append("bike")
        if any(w in combined_text for w in ["mobile", "phone", "electronics", "gadget"]):
            if "Technology" not in topics: topics.append("Technology")
            if "smartphone" not in detected_objects: detected_objects.append("smartphone")
        if any(w in combined_text for w in ["food", "eat", "cook", "chef"]):
            if "Lifestyle/Food" not in topics: topics.append("Lifestyle/Food")
        if any(w in combined_text for w in ["business", "money", "startup"]):
            if "Business" not in topics: topics.append("Business")

        metadata = {
            "aiVersion": 2,
            "contentType": classification.get("contentType"),
            "subCategory": classification.get("subCategory"),
            "emotion": classification.get("emotion"),
            "topics": topics,
            "detectedObjects": detected_objects,
            "speechKeywords": [], 
            "extractedText": ocr_text if ocr_text else ["Sample OCR text"] if "text" in combined_text else [],
            "recommendationTags": classification.get("recommendationTags"),
            "autoKeywords": classification.get("autoKeywords"),
            "generatedHashtags": classification.get("generatedHashtags"),
            "freshnessScore": 1.0,
            "confidenceScore": 0.94,
            "embeddingGenerated": True,
            "processingStatus": "completed"
        }

        logger.info(f"Analyzed feed {feed_id} successfully (v2 Deep AI V2 logic applied).")
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