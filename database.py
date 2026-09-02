# ============================================================
# PRITHU RFRE - DATABASE LAYER
# MongoDB Atlas
# Complete Corrected Compatible database.py
# ============================================================

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from bson import ObjectId
from pymongo import MongoClient, ASCENDING, DESCENDING

from config import PRITHU_DB_URI, PRITHU_DB_NAME


# ============================================================
# MONGODB GLOBALS
# ============================================================

client: Optional[MongoClient] = None
db = None


# ============================================================
# COLLECTION NAMES
# ============================================================

FEEDS = "Feeds"
RECOMMENDATION_SCORES = "RecommendationScores"
USER_FEED_ANALYTICS = "UserFeedAnalytics"
USER_FEED_ACTIONS = "UserFeedActions"
USER_ACTIVITIES = "UserActivities"
USER_VIEWS = "UserViews"

BLOGS = "Blogs"
CATEGORIES = "Categories"
LOWER_CATEGORIES = "categories"

# User collection
USERS = "Users"


# ============================================================
# DAILY FEED CONFIGURATION
# ============================================================

DAILY_POOL_USER_ID = "__DAILY_POOL__"


# ============================================================
# VALID VIEW ACTIONS
# ============================================================

# IMPORTANT:
# Only these actions count as permanently viewed content.
# Likes, shares, clicks, saves, skips, recommendations, etc.
# must NOT automatically mark content as viewed.

VIEW_ACTIONS = {
    "view",
    "viewed",
    "seen",
}


# ============================================================
# TIME HELPER
# ============================================================

def utc_now() -> datetime:
    """
    Return current timezone-aware UTC datetime.
    """
    return datetime.now(timezone.utc)


# ============================================================
# DATETIME PARSER
# ============================================================

def parse_datetime(value: Any) -> Optional[datetime]:
    """
    Convert MongoDB/string datetime to timezone-aware datetime.
    """

    if value is None:
        return None

    if isinstance(value, datetime):

        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)

        return value

    if isinstance(value, str):

        try:

            text = value.strip()

            if text.endswith("Z"):
                text = text[:-1] + "+00:00"

            parsed = datetime.fromisoformat(text)

            if parsed.tzinfo is None:
                parsed = parsed.replace(
                    tzinfo=timezone.utc
                )

            return parsed

        except Exception:
            return None

    return None


# ============================================================
# MONGODB CLIENT
# ============================================================

def get_client() -> MongoClient:
    """
    Return MongoDB client.
    Creates it if necessary.
    """

    global client

    if client is None:

        if not PRITHU_DB_URI:
            raise RuntimeError(
                "PRITHU_DB_URI is not configured."
            )

        client = MongoClient(
            PRITHU_DB_URI,
            serverSelectionTimeoutMS=10000,
            connectTimeoutMS=10000,
            socketTimeoutMS=20000,
        )

    return client


# ============================================================
# GET DATABASE
# ============================================================

def get_database():
    """
    Return Prithu MongoDB database.
    """

    global db

    if db is None:
        db = get_client()[PRITHU_DB_NAME]

    return db


# ============================================================
# COLLECTION HELPER
# ============================================================

def collection(name: str):
    """
    Return MongoDB collection.
    """

    return get_database()[name]


# ============================================================
# INITIALIZE DATABASE
# ============================================================

def init_database():
    """
    Connect to MongoDB Atlas and initialize indexes.
    """

    global client
    global db

    try:

        client = get_client()

        # ----------------------------------------------------
        # TEST CONNECTION
        # ----------------------------------------------------

        client.admin.command("ping")

        db = client[PRITHU_DB_NAME]

        # ----------------------------------------------------
        # FEEDS INDEXES
        # ----------------------------------------------------

        try:

            db[FEEDS].create_index(
                [
                    ("user_id", ASCENDING),
                    ("created_at", DESCENDING),
                ]
            )

            db[FEEDS].create_index(
                [
                    ("feed_date", ASCENDING),
                    ("user_id", ASCENDING),
                ]
            )

            # ------------------------------------------------
            # RECOMMENDATION SCORES
            # ------------------------------------------------

            db[RECOMMENDATION_SCORES].create_index(
                [
                    ("user_id", ASCENDING),
                    ("score", DESCENDING),
                ]
            )

            db[RECOMMENDATION_SCORES].create_index(
                [
                    ("content_id", ASCENDING),
                ]
            )

            # ------------------------------------------------
            # USER FEED ANALYTICS
            # ------------------------------------------------

            db[USER_FEED_ANALYTICS].create_index(
                [
                    ("user_id", ASCENDING),
                    ("created_at", DESCENDING),
                ]
            )

            # ------------------------------------------------
            # USER FEED ACTIONS
            # ------------------------------------------------

            db[USER_FEED_ACTIONS].create_index(
                [
                    ("user_id", ASCENDING),
                    ("content_id", ASCENDING),
                ]
            )

            db[USER_FEED_ACTIONS].create_index(
                [
                    ("user_id", ASCENDING),
                    ("action", ASCENDING),
                ]
            )

            # ------------------------------------------------
            # USER ACTIVITIES
            # ------------------------------------------------

            db[USER_ACTIVITIES].create_index(
                [
                    ("user_id", ASCENDING),
                    ("created_at", DESCENDING),
                ]
            )

            db[USER_ACTIVITIES].create_index(
                [
                    ("user_id", ASCENDING),
                    ("action", ASCENDING),
                ]
            )

            # ------------------------------------------------
            # USER VIEWS
            # ------------------------------------------------

            db[USER_VIEWS].create_index(
                [
                    ("user_id", ASCENDING),
                    ("content_id", ASCENDING),
                ]
            )

            db[USER_VIEWS].create_index(
                [
                    ("user_id", ASCENDING),
                    ("created_at", DESCENDING),
                ]
            )

            # ------------------------------------------------
            # USERS
            # ------------------------------------------------

            db[USERS].create_index(
                [
                    ("user_id", ASCENDING),
                ],
                unique=True,
            )

            # ------------------------------------------------
            # BLOGS
            # ------------------------------------------------

            db[BLOGS].create_index(
                [
                    ("publish_date", ASCENDING),
                    ("expiry_date", ASCENDING),
                ]
            )

            db[BLOGS].create_index(
                [
                    ("active", ASCENDING),
                ]
            )

            print("MongoDB indexes initialized")

        except Exception as index_error:

            print(
                "Index warning:",
                index_error
            )

        print(
            "MongoDB Atlas connection successful"
        )

        print(
            f"Database: {PRITHU_DB_NAME}"
        )

        return True

    except Exception as e:

        print(
            "MongoDB initialization failed:",
            e
        )

        raise


# ============================================================
# COMPATIBILITY ALIAS
# ============================================================

def initialize_database():
    """
    Compatibility wrapper.
    Some test files may call initialize_database().
    """

    return init_database()


# ============================================================
# DATABASE CONNECTION TEST
# ============================================================

def is_database_connected() -> bool:
    """
    Return True when MongoDB Atlas is reachable.
    """

    try:

        get_client().admin.command("ping")

        return True

    except Exception:

        return False


# ============================================================
# DATABASE HEALTH
# ============================================================

def database_health() -> Dict[str, Any]:
    """
    Return MongoDB health information.
    """

    try:

        get_client().admin.command("ping")

        return {
            "connected": True,
            "database": PRITHU_DB_NAME,
            "status": "healthy",
        }

    except Exception as e:

        return {
            "connected": False,
            "database": PRITHU_DB_NAME,
            "status": "unhealthy",
            "error": str(e),
        }


# ============================================================
# DATABASE STATUS
# ============================================================

def database_status() -> Dict[str, Any]:
    """
    Backward-compatible database status.
    """

    return database_health()


# ============================================================
# CLOSE DATABASE
# ============================================================

def close_database():
    """
    Close MongoDB connection.
    """

    global client
    global db

    try:

        if client is not None:
            client.close()

        client = None
        db = None

        print(
            "MongoDB connection closed"
        )

    except Exception as e:

        print(
            "MongoDB close warning:",
            e
        )


# ============================================================
# NORMALIZE CONTENT ID
# ============================================================

def normalize_content_id(value: Any) -> Any:
    """
    Normalize content ID while supporting:
    - integer IDs
    - ObjectId
    - string IDs
    """

    if value is None:
        return None

    if isinstance(value, ObjectId):
        return value

    if isinstance(value, int):
        return value

    if isinstance(value, str):

        value = value.strip()

        if value.isdigit():
            return int(value)

        try:
            return ObjectId(value)

        except Exception:
            return value

    return value


# ============================================================
# EXTRACT CONTENT ID
# ============================================================

def extract_content_id(
    document: Dict[str, Any]
) -> Any:
    """
    Extract content ID from different schemas.
    """

    fields = [
        "content_id",
        "contentId",
        "id",
        "_id",
        "post_id",
        "postId",
        "blog_id",
        "blogId",
    ]

    for field in fields:

        if field in document:

            value = document[field]

            if value is not None:
                return value

    return None


# ============================================================
# NORMALIZE CONTENT
# ============================================================

def normalize_content(
    document: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Convert existing Blogs document into RFRE format.
    """

    item = dict(document)

    # --------------------------------------------------------
    # CONTENT ID
    # --------------------------------------------------------

    content_id = extract_content_id(item)

    # --------------------------------------------------------
    # CATEGORY
    # --------------------------------------------------------

    category = (
        item.get("category")
        or item.get("Category")
        or item.get("category_name")
        or item.get("categoryName")
        or "General"
    )

    # --------------------------------------------------------
    # TAGS
    # --------------------------------------------------------

    tags = (
        item.get("tags")
        or item.get("Tags")
        or item.get("hashtags")
        or []
    )

    if isinstance(tags, str):

        tags = [
            x.strip()
            for x in tags.split(",")
            if x.strip()
        ]

    elif not isinstance(tags, list):

        tags = [str(tags)]

    # --------------------------------------------------------
    # TITLE
    # --------------------------------------------------------

    title = (
        item.get("title")
        or item.get("Title")
        or item.get("name")
        or item.get("Name")
        or ""
    )

    # --------------------------------------------------------
    # POST TYPE
    # --------------------------------------------------------

    post_type = (
        item.get("post_type")
        or item.get("postType")
        or item.get("type")
        or item.get("content_type")
        or "image"
    )

    # --------------------------------------------------------
    # LANGUAGE
    # --------------------------------------------------------

    language = (
        item.get("language")
        or item.get("lang")
        or "all"
    )

    # --------------------------------------------------------
    # PRIORITY
    # --------------------------------------------------------

    priority = item.get(
        "priority",
        item.get("Priority", 0)
    )

    try:

        priority = float(priority)

    except Exception:

        priority = 0.0

    # --------------------------------------------------------
    # DURATION
    # --------------------------------------------------------

    duration = item.get(
        "duration",
        item.get("duration_seconds", 0)
    )

    try:

        duration = float(duration)

    except Exception:

        duration = 0.0

    # --------------------------------------------------------
    # TIME SLOT
    # --------------------------------------------------------

    time_slot = (
        item.get("time_slot")
        or item.get("timeSlot")
        or item.get("content_time_slot")
        or item.get("contentTimeSlot")
        or ""
    )

    # --------------------------------------------------------
    # WEEKDAY
    # --------------------------------------------------------

    weekday = (
        item.get("weekday")
        or item.get("week_day")
        or item.get("weekDay")
        or ""
    )

    # --------------------------------------------------------
    # FESTIVAL
    # --------------------------------------------------------

    festival = (
        item.get("festival")
        or item.get("festival_name")
        or item.get("festivalName")
        or ""
    )

    # --------------------------------------------------------
    # NORMALIZED FIELDS
    # --------------------------------------------------------

    item["content_id"] = content_id
    item["category"] = category
    item["tags"] = tags
    item["title"] = title
    item["post_type"] = post_type
    item["language"] = language
    item["priority"] = priority
    item["duration"] = duration
    item["time_slot"] = time_slot
    item["weekday"] = weekday
    item["festival"] = festival

    return item


# ============================================================
# INSERT CONTENT
# ============================================================

def insert_content(
    content: Dict[str, Any]
) -> str:
    """
    Insert content into Blogs.
    """

    if not isinstance(content, dict):
        raise TypeError(
            "content must be a dictionary"
        )

    db = get_database()

    document = dict(content)

    # --------------------------------------------------------
    # TAGS
    # --------------------------------------------------------

    tags = document.get("tags", [])

    if isinstance(tags, list):

        document["tags"] = [
            str(x).strip()
            for x in tags
            if str(x).strip()
        ]

    elif tags is None:

        document["tags"] = []

    else:

        document["tags"] = [
            str(tags)
        ]

    # --------------------------------------------------------
    # PRIORITY
    # --------------------------------------------------------

    try:

        document["priority"] = float(
            document.get(
                "priority",
                0
            )
        )

    except Exception:

        document["priority"] = 0.0

    # --------------------------------------------------------
    # DEFAULT VALUES
    # --------------------------------------------------------

    document.setdefault(
        "created_at",
        utc_now()
    )

    document.setdefault(
        "active",
        True
    )

    document.setdefault(
        "is_active",
        True
    )

    document.setdefault(
        "status",
        "active"
    )

    # --------------------------------------------------------
    # INSERT
    # --------------------------------------------------------

    result = db[BLOGS].insert_one(
        document
    )

    return str(
        result.inserted_id
    )


# ============================================================
# GET ACTIVE CONTENT
# ============================================================

def get_active_content(
    now: Optional[datetime] = None,
    limit: int = 1000,
) -> List[Dict[str, Any]]:
    """
    Return active content from Blogs.
    """

    db = get_database()

    if now is None:
        now = utc_now()

    results: List[Dict[str, Any]] = []

    cursor = db[BLOGS].find({})

    for raw in cursor:

        if len(results) >= limit:
            break

        try:

            item = normalize_content(raw)

            # ------------------------------------------------
            # ACTIVE
            # ------------------------------------------------

            if item.get("active") is False:
                continue

            if item.get("is_active") is False:
                continue

            status = str(
                item.get("status", "")
            ).lower()

            if status in [
                "inactive",
                "deleted",
                "disabled",
                "expired",
            ]:
                continue

            # ------------------------------------------------
            # PUBLISH DATE
            # ------------------------------------------------

            publish_date = (
                item.get("publish_date")
                or item.get("publishDate")
                or item.get("start_date")
                or item.get("startDate")
            )

            if publish_date:

                parsed_publish = parse_datetime(
                    publish_date
                )

                if (
                    parsed_publish is not None
                    and parsed_publish > now
                ):
                    continue

            # ------------------------------------------------
            # EXPIRY DATE
            # ------------------------------------------------

            expiry_date = (
                item.get("expiry_date")
                or item.get("expiryDate")
                or item.get("end_date")
                or item.get("endDate")
            )

            if expiry_date:

                parsed_expiry = parse_datetime(
                    expiry_date
                )

                if (
                    parsed_expiry is not None
                    and parsed_expiry < now
                ):
                    continue

            results.append(item)

        except Exception as e:

            print(
                "Content normalization warning:",
                e
            )

    return results


# ============================================================
# CREATE USER
# ============================================================

def create_user_if_not_exists(
    user_id: str,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Create a user if the user does not already exist.
    """

    db = get_database()

    existing = db[USERS].find_one(
        {
            "user_id": user_id
        }
    )

    if existing:
        return existing

    document = {
        "user_id": user_id,
        "created_at": utc_now(),
        "updated_at": utc_now(),
        "is_new_user": True,
    }

    if metadata:
        document["metadata"] = metadata

    try:

        db[USERS].insert_one(
            document
        )

    except Exception:

        # Another request may have created the user
        # at the same time.
        pass

    return (
        db[USERS].find_one(
            {
                "user_id": user_id
            }
        )
        or document
    )


# ============================================================
# GET USER
# ============================================================

def get_user(
    user_id: str,
) -> Optional[Dict[str, Any]]:
    """
    Get user document.
    """

    db = get_database()

    return db[USERS].find_one(
        {
            "user_id": user_id
        }
    )


# ============================================================
# USER SEEN CONTENT IDS
# ============================================================

def get_user_seen_content_ids(
    user_id: str,
) -> List[Any]:
    """
    Return ONLY content IDs that the user has actually viewed.

    IMPORTANT:
    - view
    - viewed
    - seen

    count as permanent viewed history.

    Other actions such as:
    - like
    - share
    - save
    - click
    - skip

    do NOT count as viewed content.
    """

    db = get_database()

    seen = set()

    # --------------------------------------------------------
    # USER VIEWS
    # --------------------------------------------------------

    try:

        cursor = db[
            USER_VIEWS
        ].find(
            {
                "user_id": user_id
            }
        )

        for doc in cursor:

            content_id = (
                doc.get("content_id")
                if doc.get("content_id") is not None
                else doc.get("contentId")
            )

            if content_id is not None:

                seen.add(
                    str(content_id)
                )

    except Exception as e:

        print(
            "User views warning:",
            e
        )

    # --------------------------------------------------------
    # USER FEED ACTIONS
    # ONLY ACTUAL VIEW ACTIONS
    # --------------------------------------------------------

    try:

        cursor = db[
            USER_FEED_ACTIONS
        ].find(
            {
                "user_id": user_id,
                "action": {
                    "$in": list(VIEW_ACTIONS)
                },
            }
        )

        for doc in cursor:

            content_id = (
                doc.get("content_id")
                if doc.get("content_id") is not None
                else doc.get("contentId")
            )

            if content_id is not None:

                seen.add(
                    str(content_id)
                )

    except Exception as e:

        print(
            "Seen action warning:",
            e
        )

    # --------------------------------------------------------
    # USER ACTIVITIES
    # ONLY ACTUAL VIEW ACTIONS
    # --------------------------------------------------------

    try:

        cursor = db[
            USER_ACTIVITIES
        ].find(
            {
                "user_id": user_id,
                "action": {
                    "$in": list(VIEW_ACTIONS)
                },
            }
        )

        for doc in cursor:

            content_id = (
                doc.get("content_id")
                if doc.get("content_id") is not None
                else doc.get("contentId")
            )

            if content_id is not None:

                seen.add(
                    str(content_id)
                )

    except Exception as e:

        print(
            "Activity warning:",
            e
        )

    return list(seen)


# ============================================================
# COMPATIBILITY ALIAS
# ============================================================

def get_user_seen_content(
    user_id: str
) -> List[Any]:

    return get_user_seen_content_ids(
        user_id
    )


# ============================================================
# USER INTERESTS
# ============================================================

def get_user_interests(
    user_id: str
) -> Dict[str, float]:
    """
    Calculate category interest from user activity.
    """

    db = get_database()

    interests: Dict[str, float] = {}

    weights = {
        "like": 3.0,
        "liked": 3.0,
        "share": 4.0,
        "shared": 4.0,
        "save": 3.5,
        "saved": 3.5,
        "view": 1.0,
        "viewed": 1.0,
        "seen": 1.0,
        "click": 2.0,
        "open": 2.0,
        "skip": -1.0,
        "skipped": -1.0,
    }

    # --------------------------------------------------------
    # ACTIVITIES
    # --------------------------------------------------------

    try:

        cursor = db[
            USER_ACTIVITIES
        ].find(
            {
                "user_id": user_id
            }
        )

        for doc in cursor:

            category = (
                doc.get("category")
                or doc.get("category_name")
                or doc.get("categoryName")
            )

            if not category:
                continue

            action = (
                doc.get("action")
                or doc.get("activity")
                or doc.get("event")
                or "view"
            )

            weight = weights.get(
                str(action).lower(),
                1.0
            )

            interests[category] = (
                interests.get(
                    category,
                    0.0
                )
                + weight
            )

    except Exception as e:

        print(
            "Activity interest warning:",
            e
        )

    # --------------------------------------------------------
    # FEED ACTIONS
    # --------------------------------------------------------

    try:

        cursor = db[
            USER_FEED_ACTIONS
        ].find(
            {
                "user_id": user_id
            }
        )

        for doc in cursor:

            category = (
                doc.get("category")
                or doc.get("category_name")
                or doc.get("categoryName")
            )

            if not category:
                continue

            action = (
                doc.get("action")
                or doc.get("action_type")
                or "view"
            )

            weight = weights.get(
                str(action).lower(),
                1.0
            )

            interests[category] = (
                interests.get(
                    category,
                    0.0
                )
                + weight
            )

    except Exception as e:

        print(
            "Feed interest warning:",
            e
        )

    return dict(
        sorted(
            interests.items(),
            key=lambda x: x[1],
            reverse=True
        )
    )


# ============================================================
# SAVE DAILY FEED
# ============================================================

def save_daily_feed(
    user_id: str,
    content_ids: List[Any],
    feed_date: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Save a daily feed.
    """

    db = get_database()

    if feed_date is None:
        feed_date = (
            utc_now()
            .date()
            .isoformat()
        )

    document = {
        "user_id": user_id,

        "content_ids": [
            str(x)
            for x in content_ids
        ],

        "feed_date": feed_date,

        "created_at": utc_now(),

        "engine": "RFRE",

        "feed_size": len(
            content_ids
        ),
    }

    if metadata:
        document["metadata"] = metadata

    result = db[
        FEEDS
    ].insert_one(
        document
    )

    return str(
        result.inserted_id
    )


# ============================================================
# INSERT FEED
# ============================================================

def insert_feed(
    user_id: str,
    content_ids: List[Any],
    feed_id: Optional[str] = None,
    feed_date: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Backward-compatible feed insertion.
    """

    db = get_database()

    if feed_date is None:
        feed_date = (
            utc_now()
            .date()
            .isoformat()
        )

    document = {
        "user_id": user_id,

        "content_ids": [
            str(x)
            for x in content_ids
        ],

        "feed_date": feed_date,

        "created_at": utc_now(),

        "engine": "RFRE",

        "feed_size": len(
            content_ids
        ),
    }

    if feed_id:
        document["feed_id"] = feed_id

    if metadata:
        document["metadata"] = metadata

    result = db[
        FEEDS
    ].insert_one(
        document
    )

    return str(
        result.inserted_id
    )


# ============================================================
# GET DAILY FEED
# ============================================================

def get_daily_feed(
    user_id: str,
    feed_date: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """
    Get daily feed for a user.
    """

    db = get_database()

    if feed_date is None:
        feed_date = (
            utc_now()
            .date()
            .isoformat()
        )

    return db[
        FEEDS
    ].find_one(
        {
            "user_id": user_id,
            "feed_date": feed_date,
        },
        sort=[
            ("created_at", DESCENDING)
        ],
    )


# ============================================================
# GET LATEST USER FEED
# ============================================================

def get_latest_user_feed(
    user_id: str
) -> Optional[Dict[str, Any]]:

    db = get_database()

    return db[
        FEEDS
    ].find_one(
        {
            "user_id": user_id
        },
        sort=[
            ("created_at", DESCENDING)
        ],
    )


# ============================================================
# CLEAR DAILY FEEDS
# ============================================================

def clear_daily_feeds(
    feed_date: Optional[str] = None,
) -> int:
    """
    Delete daily feed records.

    Does NOT delete:
    - Blogs
    - User history
    - UserViews
    """

    db = get_database()

    if feed_date is None:
        feed_date = (
            utc_now()
            .date()
            .isoformat()
        )

    result = db[
        FEEDS
    ].delete_many(
        {
            "feed_date": feed_date
        }
    )

    return result.deleted_count


# ============================================================
# INSERT FEED ACTION
# ============================================================

def insert_feed_action(
    user_id: str,
    content_id: Any,
    action: str = "view",
    category: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> str:

    db = get_database()

    document = {
        "user_id": user_id,

        "content_id": normalize_content_id(
            content_id
        ),

        "action": str(action).lower(),

        "created_at": utc_now(),
    }

    if category:
        document["category"] = category

    if metadata:
        document["metadata"] = metadata

    result = db[
        USER_FEED_ACTIONS
    ].insert_one(
        document
    )

    return str(
        result.inserted_id
    )


# ============================================================
# INSERT USER ACTIVITY
# ============================================================

def insert_user_activity(
    user_id: str,
    content_id: Optional[Any] = None,
    action: str = "view",
    category: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> str:

    db = get_database()

    document = {
        "user_id": user_id,

        "action": str(action).lower(),

        "created_at": utc_now(),
    }

    if content_id is not None:

        document["content_id"] = (
            normalize_content_id(
                content_id
            )
        )

    if category:
        document["category"] = category

    if metadata:
        document["metadata"] = metadata

    result = db[
        USER_ACTIVITIES
    ].insert_one(
        document
    )

    return str(
        result.inserted_id
    )


# ============================================================
# INSERT USER VIEW
# ============================================================

def insert_user_view(
    user_id: str,
    content_id: Any,
    duration: float = 0,
    completed: bool = False,
) -> str:
    """
    Record an actual content view.

    This is the primary permanent view-history
    collection used by the recommendation engine.
    """

    db = get_database()

    try:

        duration = float(
            duration
        )

    except Exception:

        duration = 0.0

    document = {
        "user_id": user_id,

        "content_id": normalize_content_id(
            content_id
        ),

        "duration": duration,

        "completed": bool(
            completed
        ),

        "action": "viewed",

        "created_at": utc_now(),
    }

    result = db[
        USER_VIEWS
    ].insert_one(
        document
    )

    return str(
        result.inserted_id
    )


# ============================================================
# INSERT RECOMMENDATION SCORE
# ============================================================

def insert_recommendation_score(
    user_id: str,
    content_id: Any,
    score: float,
    factors: Optional[
        Dict[str, Any]
    ] = None,
) -> str:

    db = get_database()

    try:

        score = float(
            score
        )

    except Exception:

        score = 0.0

    document = {
        "user_id": user_id,

        "content_id": normalize_content_id(
            content_id
        ),

        "score": score,

        "created_at": utc_now(),
    }

    if factors:
        document["factors"] = factors

    result = db[
        RECOMMENDATION_SCORES
    ].insert_one(
        document
    )

    return str(
        result.inserted_id
    )


# ============================================================
# GET COLLECTION COUNTS
# ============================================================

def get_collection_counts() -> Dict[str, int]:
    """
    Return counts of existing RFRE collections.
    """

    db = get_database()

    names = [
        FEEDS,
        RECOMMENDATION_SCORES,
        USER_FEED_ANALYTICS,
        USER_FEED_ACTIONS,
        USER_ACTIVITIES,
        USER_VIEWS,
        BLOGS,
        LOWER_CATEGORIES,
        CATEGORIES,
        USERS,
    ]

    result: Dict[str, int] = {}

    for name in names:

        try:

            result[name] = (
                db[name].count_documents({})
            )

        except Exception:

            result[name] = 0

    return result


# ============================================================
# DATABASE TEST
# ============================================================

def test_database():
    """
    Test MongoDB connection and CRUD.
    """

    print("=" * 60)
    print("PRITHU RFRE - DATABASE TEST")
    print("=" * 60)

    try:

        init_database()

        print(
            "MongoDB Atlas connection successful"
        )

        print(
            f"Database: {PRITHU_DB_NAME}"
        )

        print()
        print("Collection counts:")

        counts = get_collection_counts()

        for name, count in counts.items():

            print(
                f"{name}: {count}"
            )

        # ----------------------------------------------------
        # WRITE TEST
        # ----------------------------------------------------

        test_document = {
            "user_id":
                "RFRE_DATABASE_TEST_USER",

            "action":
                "database_test",

            "test":
                True,

            "created_at":
                utc_now(),
        }

        result = db[
            USER_ACTIVITIES
        ].insert_one(
            test_document
        )

        print()
        print(
            "Write test: SUCCESS"
        )

        print(
            "Inserted ID:",
            result.inserted_id
        )

        # ----------------------------------------------------
        # READ TEST
        # ----------------------------------------------------

        found = db[
            USER_ACTIVITIES
        ].find_one(
            {
                "_id":
                    result.inserted_id
            }
        )

        if found:

            print(
                "Read test: SUCCESS"
            )

        else:

            print(
                "Read test: FAILED"
            )

        # ----------------------------------------------------
        # DELETE TEST
        # ----------------------------------------------------

        deleted = db[
            USER_ACTIVITIES
        ].delete_one(
            {
                "_id":
                    result.inserted_id
            }
        )

        if deleted.deleted_count == 1:

            print(
                "Delete test: SUCCESS"
            )

        else:

            print(
                "Delete test: FAILED"
            )

        print()
        print(
            "Database test completed successfully."
        )

        return True

    except Exception as e:

        print()
        print(
            "DATABASE TEST FAILED"
        )

        print(
            "Error:",
            e
        )

        return False


# ============================================================
# SCRIPT ENTRY
# ============================================================

if __name__ == "__main__":

    try:

        test_database()

    finally:

        close_database()