# ============================================================
# PRITHU RFRE - CONFIGURATION
# ============================================================

import os
from dotenv import load_dotenv


# ============================================================
# LOAD .ENV FILE
# ============================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

ENV_FILE = os.path.join(BASE_DIR, ".env")

load_dotenv(ENV_FILE)


# ============================================================
# MONGODB CONFIGURATION
# ============================================================

PRITHU_DB_URI = os.getenv("PRITHU_DB_URI")

PRITHU_DB_NAME = os.getenv(
    "PRITHU_DB_NAME",
    "Prithu-DB"
)


# ============================================================
# APPLICATION CONFIGURATION
# ============================================================

APP_NAME = "Prithu RFRE API"

APP_VERSION = "1.0.0"

HOST = "0.0.0.0"

PORT = 8001


# ============================================================
# RFRE FEED CONFIGURATION
# ============================================================

# Maximum number of posts stored in a generated daily feed.
DAILY_FEED_SIZE = 25

# Number of posts shown when a new user opens the app.
INITIAL_FEED_SIZE = 7

# Maximum posts returned by feed APIs.
MAX_FEED_SIZE = 25


# ============================================================
# CONTENT REPEAT POLICY
# ============================================================

# IMPORTANT:
#
# Previously viewed content should NOT automatically become
# available again after 30 days.
#
# A post/video such as:
#
#   Good Morning
#   Good Night
#   Festival wishes
#   Devotional wishes
#
# that has already been viewed by a user should be treated
# as LIFETIME VIEWED content unless the application explicitly
# resets the user's history.
#
# Therefore this value is kept as a configuration flag.
CONTENT_REPEAT_DAYS = 0

# 0 = lifetime exclusion
#
# If you later want content to repeat after a certain number
# of days, change this value to the required number of days.
#
# Example:
# CONTENT_REPEAT_DAYS = 30


# ============================================================
# LIFETIME VIEW POLICY
# ============================================================

# If True:
#
# Once a user views a post/video, that content_id is stored
# in the user's history and will NOT be shown again.
#
# This is especially important for:
#
# Good Morning
# Good Afternoon
# Good Evening
# Good Night
# Devotional posts
# Festival posts
# Motivation posts
# Videos
#
LIFETIME_VIEW_EXCLUSION = True


# ============================================================
# NEW USER POLICY
# ============================================================

# A new user has no viewing history.
#
# The first feed should therefore be generated from currently
# eligible active content.
#
# Once the user views content, that content becomes excluded
# from future recommendations for that user.
NEW_USER_USE_HISTORY = True

# Number of initial posts shown to a new user.
NEW_USER_FEED_SIZE = INITIAL_FEED_SIZE


# ============================================================
# OLD USER POLICY
# ============================================================

# Existing users should receive content based on:
#
# 1. Previously viewed content exclusion
# 2. User interests
# 3. Category relevance
# 4. Time relevance
# 5. Day relevance
# 6. Freshness
# 7. Engagement
#
OLD_USER_USE_HISTORY = True

OLD_USER_EXCLUDE_VIEWED = True


# ============================================================
# TIME SLOT CONFIGURATION
# ============================================================

TIME_SLOTS = {

    "morning": {
        "start": 5.0,
        "end": 11.0
    },

    "afternoon": {
        "start": 11.0,
        "end": 15.5
    },

    "evening": {
        "start": 15.5,
        "end": 19.5
    },

    "night": {
        "start": 19.5,
        "end": 24.0
    }
}


# ============================================================
# TIME-BASED CONTENT CATEGORIES
# ============================================================

TIME_CONTENT_RULES = {

    "morning": [
        "good_morning",
        "morning",
        "devotional",
        "motivation",
        "positive"
    ],

    "afternoon": [
        "afternoon",
        "motivation",
        "positive",
        "devotional"
    ],

    "evening": [
        "good_evening",
        "evening",
        "motivation",
        "love",
        "positive"
    ],

    "night": [
        "good_night",
        "night",
        "love",
        "positive",
        "devotional"
    ]
}


# ============================================================
# WEEKDAY DEVOTIONAL RULES
# ============================================================

WEEKDAY_RULES = {

    "Monday": [
        "Shiva",
        "Parvati",
        "Natarajar"
    ],

    "Tuesday": [
        "Murugan",
        "Amman",
        "Karuppasamy"
    ],

    "Wednesday": [
        "Vinayagar",
        "Saraswati",
        "Ayyanar"
    ],

    "Thursday": [
        "Dakshinamurthy",
        "Perumal",
        "Rama"
    ],

    "Friday": [
        "Meenakshi",
        "Mariamman",
        "Mahalakshmi",
        "Andal"
    ],

    "Saturday": [
        "Saneeswaran",
        "Ayyappan",
        "Hanuman"
    ],

    "Sunday": [
        "Surya",
        "Krishna",
        "Perumal",
        "Murugan"
    ]
}


# ============================================================
# RFRE SCORING WEIGHTS
# ============================================================

USER_INTEREST_WEIGHT = 30

TIME_RELEVANCE_WEIGHT = 20

DAY_RELEVANCE_WEIGHT = 15

FRESHNESS_WEIGHT = 15

ENGAGEMENT_WEIGHT = 10

SPECIAL_DAY_WEIGHT = 10


# ============================================================
# LIFETIME VIEW SCORE
# ============================================================

# Viewed content receives an extremely strong exclusion
# penalty.
#
# The actual recommendation engine should normally FILTER
# viewed content before scoring it.
VIEWED_CONTENT_PENALTY = -1000000


# ============================================================
# CONTENT MIX
# ============================================================

CONTENT_MIX = {

    "good_morning": 3,

    "afternoon": 2,

    "good_evening": 2,

    "good_night": 2,

    "devotional": 4,

    "motivation": 4,

    "love": 3,

    "positive": 3,

    "video": 2
}


# ============================================================
# CONTENT TYPE RULES
# ============================================================

CONTENT_TYPES = {

    "image": "image",

    "video": "video",

    "reel": "video",

    "text": "text"
}


# ============================================================
# FEED GENERATION RULES
# ============================================================

# Do not show content that the user has already viewed.
EXCLUDE_VIEWED_CONTENT = True

# Do not show inactive content.
EXCLUDE_INACTIVE_CONTENT = True

# Do not show expired content.
EXCLUDE_EXPIRED_CONTENT = True

# Do not show content before its publish date.
EXCLUDE_UNPUBLISHED_CONTENT = True

# Use current time when calculating time relevance.
USE_TIME_RELEVANCE = True

# Use weekday when calculating devotional relevance.
USE_WEEKDAY_RELEVANCE = True


# ============================================================
# NEW USER FIRST FEED RULE
# ============================================================

# New user:
#
# App opened
#     ↓
# No history
#     ↓
# Generate first feed
#     ↓
# Show INITIAL_FEED_SIZE posts
#     ↓
# User views a post/video
#     ↓
# Store content_id in UserViews/UserActivities
#     ↓
# Same content_id is excluded permanently
#
NEW_USER_FIRST_FEED_ENABLED = True


# ============================================================
# USER VIEW TRACKING
# ============================================================

TRACK_USER_VIEWS = True

TRACK_USER_ACTIONS = True

TRACK_USER_ACTIVITIES = True

TRACK_VIEW_DURATION = True

TRACK_COMPLETED_VIEWS = True


# ============================================================
# IMPORTANT VIEW RULE
# ============================================================

# A VIEW means the content has been seen by the user.
#
# Example:
#
# User sees:
# "Good Morning"
#
# content_id = 123
#
# UserViews:
#
# user_id = user001
# content_id = 123
#
# From that point:
#
# content_id 123 MUST NOT be returned again
# to user001.
#
LIFETIME_VIEW_TRACKING = True


# ============================================================
# DAILY FEED RULES
# ============================================================

DAILY_FEED_ENABLED = True

DAILY_FEED_USE_ACTIVE_CONTENT = True

DAILY_FEED_EXCLUDE_EXPIRED = True

DAILY_FEED_EXCLUDE_INACTIVE = True


# ============================================================
# DAILY POOL
# ============================================================

# Scheduler creates one global pool of active content.
DAILY_POOL_ENABLED = True

DAILY_POOL_USER_ID = "__DAILY_POOL__"


# ============================================================
# PERSONALIZED FEED
# ============================================================

PERSONALIZED_FEED_ENABLED = True

PERSONALIZED_FEED_USE_INTERESTS = True

PERSONALIZED_FEED_USE_HISTORY = True

PERSONALIZED_FEED_EXCLUDE_VIEWED = True


# ============================================================
# FALLBACK FEED
# ============================================================

# If there are not enough personalized posts, use eligible
# active posts as fallback.
FALLBACK_TO_ACTIVE_CONTENT = True

# Never use previously viewed content as fallback.
FALLBACK_EXCLUDE_VIEWED = True


# ============================================================
# DUPLICATE CONTENT RULE
# ============================================================

# Prevent duplicate content IDs in one feed.
REMOVE_DUPLICATE_CONTENT = True


# ============================================================
# CATEGORY CONFIGURATION
# ============================================================

DEFAULT_CATEGORY = "General"

CATEGORY_FIELD_NAMES = [
    "category",
    "Category",
    "category_name",
    "categoryName"
]


# ============================================================
# CONTENT ID CONFIGURATION
# ============================================================

CONTENT_ID_FIELD_NAMES = [
    "content_id",
    "contentId",
    "id",
    "_id",
    "post_id",
    "postId",
    "blog_id",
    "blogId"
]


# ============================================================
# MONGODB COLLECTION NAMES
# ============================================================

COLLECTION_FEEDS = "Feeds"

COLLECTION_RECOMMENDATION_SCORES = "RecommendationScores"

COLLECTION_USER_FEED_ANALYTICS = "UserFeedAnalytics"

COLLECTION_USER_FEED_ACTIONS = "UserFeedActions"

COLLECTION_USER_ACTIVITIES = "UserActivities"

COLLECTION_USER_VIEWS = "UserViews"

COLLECTION_BLOGS = "Blogs"

COLLECTION_CATEGORIES = "Categories"

COLLECTION_CATEGORIES_LOWER = "categories"


# ============================================================
# API CONFIGURATION
# ============================================================

API_PREFIX = "/api"

FEED_ENDPOINT = "/feed"

CONTENT_ENDPOINT = "/content"

USER_ACTIVITY_ENDPOINT = "/activity"

USER_VIEW_ENDPOINT = "/view"

HEALTH_ENDPOINT = "/health"


# ============================================================
# PAGINATION
# ============================================================

DEFAULT_PAGE_SIZE = INITIAL_FEED_SIZE

MAX_PAGE_SIZE = MAX_FEED_SIZE


# ============================================================
# DATABASE VALIDATION
# ============================================================

if not PRITHU_DB_URI:

    raise RuntimeError(
        "PRITHU_DB_URI is not configured.\n"
        f"Please check the .env file at:\n{ENV_FILE}\n\n"
        "Required format:\n"
        "PRITHU_DB_URI=mongodb+srv://USERNAME:PASSWORD@cluster.mongodb.net/Prithu-DB\n"
        "PRITHU_DB_NAME=Prithu-DB"
    )


# ============================================================
# MONGODB URI VALIDATION
# ============================================================

if not (
    PRITHU_DB_URI.startswith("mongodb://")
    or
    PRITHU_DB_URI.startswith("mongodb+srv://")
):

    raise RuntimeError(
        "Invalid PRITHU_DB_URI.\n"
        "MongoDB URI must begin with "
        "'mongodb://' or 'mongodb+srv://'."
    )


# ============================================================
# CONFIGURATION VALIDATION
# ============================================================

if DAILY_FEED_SIZE <= 0:

    raise RuntimeError(
        "DAILY_FEED_SIZE must be greater than 0."
    )


if INITIAL_FEED_SIZE <= 0:

    raise RuntimeError(
        "INITIAL_FEED_SIZE must be greater than 0."
    )


if INITIAL_FEED_SIZE > MAX_FEED_SIZE:

    raise RuntimeError(
        "INITIAL_FEED_SIZE cannot be greater than "
        "MAX_FEED_SIZE."
    )


if CONTENT_REPEAT_DAYS < 0:

    raise RuntimeError(
        "CONTENT_REPEAT_DAYS cannot be negative."
    )


# ============================================================
# RFRE POLICY VALIDATION
# ============================================================

if LIFETIME_VIEW_EXCLUSION:

    CONTENT_REPEAT_DAYS = 0


# ============================================================
# CONFIGURATION STATUS
# ============================================================

print("====================================")
print("Prithu RFRE Configuration Loaded")
print(f"Database: {PRITHU_DB_NAME}")
print("MongoDB URI: Configured")
print(f"Daily Feed Size: {DAILY_FEED_SIZE}")
print(f"Initial Feed Size: {INITIAL_FEED_SIZE}")
print(f"Maximum Feed Size: {MAX_FEED_SIZE}")
print(
    f"Lifetime View Exclusion: "
    f"{LIFETIME_VIEW_EXCLUSION}"
)
print(
    f"Content Repeat Days: "
    f"{CONTENT_REPEAT_DAYS}"
)
print(
    f"New User First Feed: "
    f"{NEW_USER_FIRST_FEED_ENABLED}"
)
print(
    f"Viewed Content Excluded: "
    f"{EXCLUDE_VIEWED_CONTENT}"
)
print("====================================")