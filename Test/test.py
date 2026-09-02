import sys
from pathlib import Path
import uuid
from datetime import datetime, timezone


# ============================================================
# PROJECT PATH CONFIGURATION
# ============================================================

# Current folder:
# backend/Test/

TEST_DIR = Path(__file__).resolve().parent

# Parent folder:
# backend/

BACKEND_DIR = TEST_DIR.parent

# Add backend directory to Python path
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


# ============================================================
# PROJECT IMPORTS
# ============================================================

import database
import engine


# ============================================================
# TEST CONFIGURATION
# ============================================================

TEST_USER = f"good_morning_test_{uuid.uuid4().hex[:8]}"

VIEW_ACTIONS = {
    "view",
    "viewed",
    "seen",
}

TIME_SLOTS = [
    "morning",
    "afternoon",
    "evening",
    "night",
]


# ============================================================
# HELPERS
# ============================================================

def print_header(title):
    print()
    print("=" * 70)
    print(title)
    print("=" * 70)


def normalize_id(value):
    """
    Convert different ID formats into a string.
    """

    if value is None:
        return None

    if isinstance(value, dict):

        for key in (
            "_id",
            "id",
            "content_id",
            "contentId",
            "targetId",
        ):

            if key in value:
                return normalize_id(value[key])

    return str(value)


def get_content_id(content):
    """
    Extract content ID from different document formats.
    """

    if not isinstance(content, dict):
        return normalize_id(content)

    for key in (
        "_id",
        "id",
        "content_id",
        "contentId",
    ):

        if key in content:

            value = content[key]

            if value is not None:
                return normalize_id(value)

    return None


def get_title(content):
    """
    Extract title from content document.
    """

    if not isinstance(content, dict):
        return "Untitled"

    return (
        content.get("title")
        or content.get("name")
        or content.get("content_title")
        or "Untitled"
    )


def get_time_slot(content):
    """
    Extract time slot from content.
    """

    if not isinstance(content, dict):
        return ""

    value = (
        content.get("time_slot")
        or content.get("timeSlot")
        or content.get("slot")
        or ""
    )

    return str(value).lower().strip()


def get_content_type(content):
    """
    Extract content type.
    """

    if not isinstance(content, dict):
        return "unknown"

    return (
        content.get("content_type")
        or content.get("contentType")
        or content.get("post_type")
        or content.get("postType")
        or "unknown"
    )


def is_good_morning_content(content):
    """
    Detect Good Morning content using:
    1. time_slot
    2. category
    3. title
    """

    if not isinstance(content, dict):
        return False

    category = str(
        content.get("category")
        or content.get("category_name")
        or content.get("categoryName")
        or ""
    ).lower().strip()

    title = str(
        content.get("title")
        or content.get("name")
        or content.get("content_title")
        or ""
    ).lower().strip()

    time_slot = get_time_slot(content)

    # Main rule
    if time_slot == "morning":
        return True

    # Category rule
    if "good morning" in category:
        return True

    # Title rule
    if "good morning" in title:
        return True

    return False


def is_morning_content(content):
    """
    Check whether content belongs to morning slot.
    """

    return get_time_slot(content) == "morning"


# ============================================================
# DATABASE VIEW RECORDING
# ============================================================

def record_view(user_id, content_id):
    """
    Record a permanent content view.

    The view is stored in:
        1. UserViews
        2. UserFeedActions
        3. UserActivities

    Only 'viewed' is used as the action.
    """

    content_id = normalize_id(content_id)

    print()
    print("Recording view")
    print(f"User       : {user_id}")
    print(f"Content ID : {content_id}")

    now = datetime.now(timezone.utc)

    try:

        # ====================================================
        # 1. UserViews
        # ====================================================

        database.insert_user_view(
            user_id=user_id,
            content_id=content_id,
            duration=10,
            completed=True,
        )

        print("UserViews             : PASS")

        # ====================================================
        # 2. UserFeedActions
        # ====================================================

        database.insert_feed_action(
            user_id=user_id,
            content_id=content_id,
            action="viewed",
        )

        print("UserFeedActions       : PASS")

        # ====================================================
        # 3. UserActivities
        # ====================================================

        db = database.get_database()

        if db is None:
            raise RuntimeError(
                "MongoDB database object is None."
            )

        activities = db["UserActivities"]

        # Check existing activity first
        existing_activity = activities.find_one(
            {
                "userId": user_id,
                "actionType": "viewed",
                "targetId": content_id,
                "targetModel": "Feed",
            }
        )

        if existing_activity:

            print(
                "UserActivities       : ALREADY EXISTS"
            )

        else:

            activity_document = {

                # Project fields
                "user_id": user_id,
                "content_id": content_id,
                "action": "viewed",

                # Existing MongoDB index fields
                "userId": user_id,
                "actionType": "viewed",
                "targetId": content_id,
                "targetModel": "Feed",

                # Metadata
                "metadata": {},

                # Timestamps
                "created_at": now,
                "timestamp": now,
            }

            activities.insert_one(
                activity_document
            )

            print(
                "UserActivities       : PASS"
            )

        return True

    except Exception as e:

        print(
            f"Record view failed: {e}"
        )

        return False


# ============================================================
# GET SEEN CONTENT
# ============================================================

def get_seen_content(user_id):
    """
    Get all content permanently viewed by the user.
    """

    try:

        seen = database.get_user_seen_content_ids(
            user_id
        )

        if seen is None:
            return set()

        return {
            normalize_id(content_id)
            for content_id in seen
            if content_id is not None
        }

    except Exception as e:

        print(
            f"Could not get viewed content: {e}"
        )

        return set()


# ============================================================
# GET GENERATED FEED
# ============================================================

def get_feed(user_id, feed_size=25):
    """
    Generate user feed.

    Supports different versions of generate_feed().
    """

    try:

        # ====================================================
        # Current engine version
        # ====================================================

        result = engine.generate_feed(
            user_id=user_id,
            feed_size=feed_size,
        )

        if result is None:
            return []

        # ====================================================
        # Dictionary response
        # ====================================================

        if isinstance(result, dict):

            for key in (
                "feed",
                "items",
                "contents",
                "recommendations",
                "data",
            ):

                if key in result:

                    value = result[key]

                    if isinstance(value, list):
                        return value

            return []

        # ====================================================
        # List response
        # ====================================================

        if isinstance(result, list):
            return result

        return []

    except TypeError:

        # ====================================================
        # Compatibility fallback
        # ====================================================

        try:

            result = engine.generate_feed(
                user_id
            )

            if isinstance(result, list):
                return result

            if isinstance(result, dict):

                for key in (
                    "feed",
                    "items",
                    "contents",
                    "recommendations",
                    "data",
                ):

                    value = result.get(key)

                    if isinstance(value, list):
                        return value

            return []

        except Exception as e:

            print(
                f"Feed generation failed: {e}"
            )

            return []

    except Exception as e:

        print(
            f"Feed generation failed: {e}"
        )

        return []


# ============================================================
# GET FEED IDS
# ============================================================

def get_feed_ids(feed):
    """
    Extract content IDs from generated feed.
    """

    feed_ids = set()

    if not isinstance(feed, list):
        return feed_ids

    for item in feed:

        if isinstance(item, dict):

            content_id = get_content_id(item)

        else:

            content_id = normalize_id(item)

        if content_id:
            feed_ids.add(content_id)

    return feed_ids


# ============================================================
# TEST MAIN
# ============================================================

def main():

    print()
    print("=" * 70)
    print("PRITHU RFRE - GOOD MORNING CONTENT TEST")
    print("=" * 70)

    print()
    print(f"Test User: {TEST_USER}")


    # ========================================================
    # 1. DATABASE CONNECTION
    # ========================================================

    print_header(
        "1. DATABASE CONNECTION"
    )

    try:

        database.initialize_database()

        connected = (
            database.is_database_connected()
        )

        if not connected:

            print(
                "MongoDB Atlas connection: FAIL"
            )

            return

        print(
            "MongoDB Atlas connection: PASS"
        )

    except Exception as e:

        print(
            "MongoDB Atlas connection: FAIL"
        )

        print(
            f"Error: {e}"
        )

        return


    # ========================================================
    # 2. NEW USER
    # ========================================================

    print_header(
        "2. NEW USER"
    )

    try:

        database.create_user_if_not_exists(
            TEST_USER
        )

        seen_before = get_seen_content(
            TEST_USER
        )

        print(
            f"User: {TEST_USER}"
        )

        print(
            f"Previously viewed content: "
            f"{len(seen_before)}"
        )

        if len(seen_before) == 0:

            print(
                "New user verification: PASS"
            )

        else:

            print(
                "New user verification: FAIL"
            )

            print(
                "Unexpected existing view history."
            )

            return

    except Exception as e:

        print(
            "New user verification: FAIL"
        )

        print(
            f"Error: {e}"
        )

        return


    # ========================================================
    # 3. FIND GOOD MORNING CONTENT
    # ========================================================

    print_header(
        "3. GOOD MORNING CONTENT"
    )

    try:

        active_content = (
            database.get_active_content()
        )

        if active_content is None:
            active_content = []

        print(
            f"Active content: "
            f"{len(active_content)}"
        )

        good_morning = [
            item
            for item in active_content
            if is_good_morning_content(item)
        ]

        print(
            f"Good Morning content found: "
            f"{len(good_morning)}"
        )

        if len(good_morning) == 0:

            print()
            print(
                "WARNING: No Good Morning content found."
            )

            print()
            print(
                "MongoDB should contain content similar to:"
            )

            print()

            print(
                {
                    "title": "Good Morning Video A",
                    "category": "Good Morning",
                    "time_slot": "morning",
                    "content_type": "video",
                    "is_active": True,
                }
            )

            print()
            print(
                "Good Morning content test: STOPPED"
            )

            return

        print()
        print(
            "Good Morning content:"
        )

        print(
            "-" * 70
        )

        for index, item in enumerate(
            good_morning,
            start=1
        ):

            content_id = get_content_id(
                item
            )

            title = get_title(
                item
            )

            slot = get_time_slot(
                item
            )

            content_type = get_content_type(
                item
            )

            print(
                f"{index}. "
                f"ID={content_id} | "
                f"Title={title} | "
                f"Time Slot={slot} | "
                f"Type={content_type}"
            )

        print()

        print(
            "Good Morning content detection: PASS"
        )

    except Exception as e:

        print(
            "Good Morning content test: FAIL"
        )

        print(
            f"Error: {e}"
        )

        return


    # ========================================================
    # 4. MORNING TIME-SLOT FILTER
    # ========================================================

    print_header(
        "4. MORNING TIME-SLOT FILTER"
    )

    morning_items = [
        item
        for item in good_morning
        if is_morning_content(item)
    ]

    print(
        "Good Morning items with "
        f"time_slot='morning': "
        f"{len(morning_items)}"
    )

    if len(morning_items) == 0:

        print(
            "Morning time-slot filtering: FAIL"
        )

        print(
            "No content has time_slot='morning'."
        )

        return

    print(
        "Morning time-slot filtering: PASS"
    )


    # ========================================================
    # 5. SELECT CONTENT
    # ========================================================

    print_header(
        "5. SELECT CONTENT"
    )

    selected_content = (
        morning_items[0]
    )

    selected_id = get_content_id(
        selected_content
    )

    selected_title = get_title(
        selected_content
    )

    selected_type = get_content_type(
        selected_content
    )

    print(
        f"Selected Content ID: "
        f"{selected_id}"
    )

    print(
        f"Title: {selected_title}"
    )

    print(
        f"Content Type: {selected_type}"
    )

    if selected_id is None:

        print(
            "Selected Good Morning content: FAIL"
        )

        print(
            "Content does not have a valid ID."
        )

        return

    print(
        "Selected Good Morning content: PASS"
    )


    # ========================================================
    # 6. BEFORE VIEW CHECK
    # ========================================================

    print_header(
        "6. BEFORE VIEW CHECK"
    )

    seen_before = get_seen_content(
        TEST_USER
    )

    if selected_id not in seen_before:

        print(
            "Content has not been viewed before: PASS"
        )

    else:

        print(
            "Content has already been viewed: FAIL"
        )

        return


    # ========================================================
    # 7. RECORD VIEW
    # ========================================================

    print_header(
        "7. RECORD GOOD MORNING CONTENT VIEW"
    )

    view_success = record_view(
        TEST_USER,
        selected_id
    )

    if not view_success:

        print()
        print(
            "Record Good Morning content view: FAIL"
        )

        return

    print()
    print(
        "Record Good Morning content view: PASS"
    )


    # ========================================================
    # 8. VERIFY VIEW HISTORY
    # ========================================================

    print_header(
        "8. VERIFY PERMANENT VIEW HISTORY"
    )

    seen_after = get_seen_content(
        TEST_USER
    )

    print(
        f"Viewed content count: "
        f"{len(seen_after)}"
    )

    if selected_id in seen_after:

        print(
            "Viewed content stored: PASS"
        )

    else:

        print(
            "Viewed content stored: FAIL"
        )

        print()
        print(
            f"Expected content ID: "
            f"{selected_id}"
        )

        print()
        print(
            "Actual viewed IDs:"
        )

        for item_id in seen_after:

            print(
                item_id
            )

        return


    # ========================================================
    # 9. TIME-SLOT ELIGIBILITY
    # ========================================================

    print_header(
        "9. TIME-SLOT ELIGIBILITY"
    )

    print(
        f"Testing content: "
        f"{selected_title}"
    )

    print(
        f"Content time slot: "
        f"{get_time_slot(selected_content)}"
    )

    slot_results = {}

    for slot in TIME_SLOTS:

        try:

            eligible = (
                engine.is_content_eligible(
                    selected_content,
                    current_slot=slot,
                )
            )

            slot_results[slot] = bool(
                eligible
            )

            print(
                f"{slot.capitalize():12} -> "
                f"{'ELIGIBLE' if eligible else 'NOT ELIGIBLE'}"
            )

        except TypeError:

            # Compatibility fallback
            try:

                eligible = (
                    engine.is_content_eligible(
                        selected_content,
                        slot,
                    )
                )

                slot_results[slot] = bool(
                    eligible
                )

                print(
                    f"{slot.capitalize():12} -> "
                    f"{'ELIGIBLE' if eligible else 'NOT ELIGIBLE'}"
                )

            except Exception as e:

                slot_results[slot] = False

                print(
                    f"{slot.capitalize():12} -> "
                    f"ERROR: {e}"
                )

        except Exception as e:

            slot_results[slot] = False

            print(
                f"{slot.capitalize():12} -> "
                f"ERROR: {e}"
            )


    # Morning must be eligible
    if slot_results.get("morning") is True:

        print()
        print(
            "Morning eligibility: PASS"
        )

    else:

        print()
        print(
            "Morning eligibility: FAIL"
        )

        return


    # ========================================================
    # 10. LIFETIME VIEW EXCLUSION
    # ========================================================

    print_header(
        "10. LIFETIME VIEW EXCLUSION"
    )

    print()
    print(
        "The viewed content must NEVER return "
        "after being viewed."
    )

    print()

    print(
        "Testing generated feed..."
    )

    feed = get_feed(
        TEST_USER,
        25
    )

    print()
    print(
        f"Generated feed size: "
        f"{len(feed)}"
    )

    feed_ids = get_feed_ids(
        feed
    )

    if selected_id in feed_ids:

        print()
        print(
            "Lifetime exclusion: FAIL"
        )

        print(
            "ERROR: Previously viewed content "
            "appeared in the generated feed."
        )

        print()
        print(
            f"Viewed Content ID: "
            f"{selected_id}"
        )

        return

    print()
    print(
        "Viewed Good Morning content "
        "excluded from feed: PASS"
    )


    # ========================================================
    # 11. AFTERNOON
    # ========================================================

    print_header(
        "11. AFTERNOON"
    )

    try:

        afternoon_eligible = (
            engine.is_content_eligible(
                selected_content,
                current_slot="afternoon",
            )
        )

        print(
            "Content eligibility in afternoon: "
            f"{afternoon_eligible}"
        )

        if not afternoon_eligible:

            print(
                "Morning content blocked "
                "in afternoon: PASS"
            )

        else:

            print(
                "Morning content blocked "
                "in afternoon: FAIL"
            )

            return

    except Exception as e:

        print(
            f"Afternoon eligibility check error: {e}"
        )

        return


    seen_now = get_seen_content(
        TEST_USER
    )

    if selected_id in seen_now:

        print(
            "Lifetime view history retained "
            "in afternoon: PASS"
        )

    else:

        print(
            "Lifetime view history retained "
            "in afternoon: FAIL"
        )

        return


    # ========================================================
    # 12. EVENING
    # ========================================================

    print_header(
        "12. EVENING"
    )

    try:

        evening_eligible = (
            engine.is_content_eligible(
                selected_content,
                current_slot="evening",
            )
        )

        print(
            "Content eligibility in evening: "
            f"{evening_eligible}"
        )

        if not evening_eligible:

            print(
                "Morning content blocked "
                "in evening: PASS"
            )

        else:

            print(
                "Morning content blocked "
                "in evening: FAIL"
            )

            return

    except Exception as e:

        print(
            f"Evening eligibility check error: {e}"
        )

        return


    seen_now = get_seen_content(
        TEST_USER
    )

    if selected_id in seen_now:

        print(
            "Lifetime view history retained "
            "in evening: PASS"
        )

    else:

        print(
            "Lifetime view history retained "
            "in evening: FAIL"
        )

        return


    # ========================================================
    # 13. NIGHT
    # ========================================================

    print_header(
        "13. NIGHT"
    )

    try:

        night_eligible = (
            engine.is_content_eligible(
                selected_content,
                current_slot="night",
            )
        )

        print(
            "Content eligibility in night: "
            f"{night_eligible}"
        )

        if not night_eligible:

            print(
                "Morning content blocked "
                "in night: PASS"
            )

        else:

            print(
                "Morning content blocked "
                "in night: FAIL"
            )

            return

    except Exception as e:

        print(
            f"Night eligibility check error: {e}"
        )

        return


    seen_now = get_seen_content(
        TEST_USER
    )

    if selected_id in seen_now:

        print(
            "Lifetime view history retained "
            "at night: PASS"
        )

    else:

        print(
            "Lifetime view history retained "
            "at night: FAIL"
        )

        return


    # ========================================================
    # 14. NEXT MORNING
    # ========================================================

    print_header(
        "14. NEXT MORNING"
    )

    print(
        "Checking permanent view history..."
    )

    next_morning_seen = (
        get_seen_content(TEST_USER)
    )

    if selected_id in next_morning_seen:

        print(
            "Previously viewed content remains "
            "excluded next morning: PASS"
        )

    else:

        print(
            "Previously viewed content returned "
            "next morning: FAIL"
        )

        return


    # ========================================================
    # 15. FINAL FEED CHECK
    # ========================================================

    print_header(
        "15. FINAL FEED CHECK"
    )

    final_feed = get_feed(
        TEST_USER,
        25
    )

    final_feed_ids = get_feed_ids(
        final_feed
    )

    print(
        f"Final feed size: "
        f"{len(final_feed_ids)}"
    )

    if selected_id not in final_feed_ids:

        print(
            "Viewed Good Morning content "
            "permanently excluded: PASS"
        )

    else:

        print(
            "Viewed Good Morning content "
            "permanently excluded: FAIL"
        )

        return


    # ========================================================
    # FINAL RESULT
    # ========================================================

    print()
    print("=" * 70)
    print(
        "GOOD MORNING CONTENT TEST COMPLETED"
    )
    print("=" * 70)

    print()
    print("RESULTS:")
    print("-" * 70)

    print(
        "MongoDB connection                  : PASS"
    )

    print(
        "New user verification               : PASS"
    )

    print(
        "Good Morning content detection      : PASS"
    )

    print(
        "Morning time-slot filtering         : PASS"
    )

    print(
        "Content selection                   : PASS"
    )

    print(
        "Before-view check                   : PASS"
    )

    print(
        "View recording                      : PASS"
    )

    print(
        "Permanent view history              : PASS"
    )

    print(
        "Feed exclusion                      : PASS"
    )

    print(
        "Afternoon history                   : PASS"
    )

    print(
        "Evening history                     : PASS"
    )

    print(
        "Night history                       : PASS"
    )

    print(
        "Next morning history                : PASS"
    )

    print(
        "Final permanent exclusion           : PASS"
    )

    print()
    print("=" * 70)
    print(
        "ALL GOOD MORNING TESTS PASSED"
    )
    print("=" * 70)

    print()
    print(
        f"Test User: {TEST_USER}"
    )

    print(
        f"Viewed Content ID: {selected_id}"
    )

    print(
        f"Viewed Content: {selected_title}"
    )

    print()
    print(
        "Required behavior verified:"
    )

    print(
        "Once Good Morning content is viewed, "
        "it remains excluded permanently."
    )

    print(
        "Changing the time slot does NOT reset "
        "the user's view history."
    )

    # ========================================================
    # CLOSE DATABASE
    # ========================================================

    try:

        database.close_database()

    except Exception:

        pass


# ============================================================
# RUN TEST
# ============================================================

if __name__ == "__main__":
    main()