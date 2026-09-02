# ============================================================
# PRITHU RFRE - CONTENT SCHEDULER
# ============================================================
# Purpose:
#   1. Read currently active content from MongoDB
#   2. Apply date/time eligibility through database.py
#   3. Build today's global content pool
#   4. Remove previous daily pool/feed records
#   5. Save the new daily pool in MongoDB
#
# Compatible with:
#   database.py
#   engine.py
#   main.py
#
# ============================================================

from datetime import datetime, timezone
from typing import Any, Dict, List


# ============================================================
# DATABASE IMPORTS
# ============================================================

from database import (
    get_active_content,
    clear_daily_feeds,
    save_daily_feed,
    DAILY_POOL_USER_ID,
)


# ============================================================
# HELPERS
# ============================================================

def utc_now() -> datetime:
    """
    Return current timezone-aware UTC datetime.
    """
    return datetime.now(timezone.utc)


def extract_content_ids(
    active_content: List[Dict[str, Any]]
) -> List[Any]:
    """
    Extract valid content IDs from active content.

    The database layer normally provides a normalized
    'content_id' field.
    """

    content_ids: List[Any] = []

    for item in active_content:

        if not isinstance(item, dict):
            continue

        content_id = item.get("content_id")

        if content_id is None:
            continue

        # Keep numeric IDs as integers.
        if isinstance(content_id, int):
            content_ids.append(content_id)
            continue

        # Handle numeric strings.
        if isinstance(content_id, str):

            value = content_id.strip()

            if not value:
                continue

            if value.isdigit():

                content_ids.append(
                    int(value)
                )

            else:

                # Keep non-numeric IDs as strings.
                content_ids.append(value)

            continue

        # ObjectId or other supported ID type.
        content_ids.append(content_id)

    # --------------------------------------------------------
    # Remove duplicates while preserving order
    # --------------------------------------------------------

    unique_ids = []
    seen = set()

    for content_id in content_ids:

        key = str(content_id)

        if key in seen:
            continue

        seen.add(key)

        unique_ids.append(content_id)

    return unique_ids


# ============================================================
# REFRESH DAILY FEED
# ============================================================

def refresh_daily_feed() -> Dict[str, Any]:
    """
    Refresh the global PRITHU daily content pool.

    Flow:

        MongoDB
            ↓
        Active Content
            ↓
        Content IDs
            ↓
        Remove Old Daily Feed
            ↓
        Save New Daily Pool
            ↓
        RFRE Engine

    Returns a dictionary suitable for the /refresh API.
    """

    now = utc_now()

    try:

        # ====================================================
        # 1. GET ACTIVE CONTENT
        # ====================================================

        active_content = get_active_content(
            now=now
        )

        if active_content is None:
            active_content = []

        # Safety check.
        if not isinstance(
            active_content,
            list
        ):
            active_content = list(
                active_content
            )

        # ====================================================
        # 2. EXTRACT CONTENT IDs
        # ====================================================

        active_ids = extract_content_ids(
            active_content
        )

        # ====================================================
        # 3. CLEAR PREVIOUS DAILY FEEDS
        # ====================================================

        deleted_count = clear_daily_feeds()

        # ====================================================
        # 4. SAVE NEW DAILY POOL
        # ====================================================

        daily_pool_feed_id = None

        if active_ids:

            daily_pool_feed_id = save_daily_feed(
                DAILY_POOL_USER_ID,
                active_ids
            )

        # ====================================================
        # 5. RESULT
        # ====================================================

        return {

            "success": True,

            "message":
                "Daily feed refreshed successfully",

            "refresh_time":
                now.isoformat(),

            "active_content_count":
                len(active_ids),

            "old_feed_records_removed":
                int(deleted_count or 0),

            "active_content_ids":
                active_ids,

            "daily_pool_feed_id":
                daily_pool_feed_id,

        }

    except Exception as e:

        # ====================================================
        # ERROR RESULT
        # ====================================================

        return {

            "success": False,

            "message":
                "Daily feed refresh failed",

            "refresh_time":
                now.isoformat(),

            "active_content_count":
                0,

            "old_feed_records_removed":
                0,

            "active_content_ids":
                [],

            "daily_pool_feed_id":
                None,

            "error":
                str(e),

        }


# ============================================================
# GET CURRENT DAILY POOL
# ============================================================

def get_daily_pool() -> Dict[str, Any]:
    """
    Get the currently active content pool.

    This function does not modify MongoDB.
    """

    try:

        active_content = get_active_content(
            now=utc_now()
        )

        active_ids = extract_content_ids(
            active_content
        )

        return {

            "success": True,

            "count":
                len(active_ids),

            "content_ids":
                active_ids,

        }

    except Exception as e:

        return {

            "success": False,

            "count": 0,

            "content_ids": [],

            "error":
                str(e),

        }


# ============================================================
# RUN SCHEDULER MANUALLY
# ============================================================

def run_scheduler() -> Dict[str, Any]:
    """
    Manual scheduler entry point.

    Useful for:

        python scheduler.py

    or from main.py.
    """

    print()
    print("=" * 60)
    print("PRITHU RFRE - DAILY CONTENT SCHEDULER")
    print("=" * 60)

    result = refresh_daily_feed()

    print()

    if result.get("success"):

        print(
            "Daily feed refresh: SUCCESS"
        )

        print(
            "Active content:",
            result.get(
                "active_content_count",
                0
            )
        )

        print(
            "Old feed records removed:",
            result.get(
                "old_feed_records_removed",
                0
            )
        )

        print(
            "Daily pool feed ID:",
            result.get(
                "daily_pool_feed_id"
            )
        )

    else:

        print(
            "Daily feed refresh: FAILED"
        )

        print(
            "Error:",
            result.get(
                "error",
                "Unknown error"
            )
        )

    print("=" * 60)

    return result


# ============================================================
# SCRIPT ENTRY
# ============================================================

if __name__ == "__main__":

    run_scheduler()

