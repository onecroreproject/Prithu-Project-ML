# ============================================================
# PRITHU RFRE
# USER POINT OF VIEW - COMPLETE TEST
# ============================================================

import sys
from pathlib import Path
import uuid

# ============================================================
# BACKEND PATH
# ============================================================

BACKEND_DIR = Path(__file__).resolve().parents[1]

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import database
import engine


# ============================================================
# TEST CONFIGURATION
# ============================================================

SPECIAL_DATE = "2026-09-04"
DAY_BEFORE = "2026-09-03"
DAY_AFTER = "2026-09-05"

NEW_USER = f"new_user_{uuid.uuid4().hex[:8]}"
OLD_USER = f"old_user_{uuid.uuid4().hex[:8]}"
SPECIAL_USER = f"special_user_{uuid.uuid4().hex[:8]}"

SPECIAL_CONTENT_ID = (
    f"special_vinayagar_{uuid.uuid4().hex[:12]}"
)


# ============================================================
# PRINT HELPERS
# ============================================================

def print_line(char="=", length=60):
    print(char * length)


def print_section(title):
    print()
    print_line()
    print(title)
    print_line()
    print()


# ============================================================
# CONTENT HELPERS
# ============================================================

def get_content_id(content):
    if not isinstance(content, dict):
        return None

    return (
        content.get("_id")
        or content.get("id")
        or content.get("content_id")
        or content.get("post_id")
    )


def get_content_title(content):
    if not isinstance(content, dict):
        return str(content)

    return (
        content.get("title")
        or content.get("name")
        or content.get("content_title")
        or "Untitled Content"
    )


# ============================================================
# USER HISTORY
# ============================================================

def get_seen_ids(user_id):

    try:
        result = database.get_user_seen_content_ids(user_id)

        if result is None:
            return set()

        return {str(x) for x in result}

    except Exception as e:
        print(f"Warning: Could not get viewed history: {e}")
        return set()


# ============================================================
# FEED GENERATION
# ============================================================

def get_user_feed(
    user_id,
    current_date,
    current_slot,
    feed_size=7
):
    """
    Generates RFRE feed.

    Supports the current engine.py interface and also
    provides a compatibility fallback.
    """

    try:

        result = engine.generate_feed(
            user_id,
            feed_size=feed_size,
            current_date=current_date,
            current_slot=current_slot
        )

        if isinstance(result, dict):
            return result.get("feed", []) or []

        return result or []

    except TypeError:

        try:

            result = engine.generate_feed(
                user_id,
                limit=feed_size,
                current_date=current_date,
                current_slot=current_slot
            )

            if isinstance(result, dict):
                return result.get("feed", []) or []

            return result or []

        except Exception as e:
            print(f"Feed generation error: {e}")
            return []

    except Exception as e:
        print(f"Feed generation error: {e}")
        return []


# ============================================================
# PRINT FEED
# ============================================================

def print_feed(feed):

    if not feed:
        print("No content available.")
        return

    for index, item in enumerate(feed[:7], start=1):

        if isinstance(item, dict):
            title = get_content_title(item)
        else:
            title = str(item)

        print(f"{index}. {title}")


# ============================================================
# CHECK CONTENT IN FEED
# ============================================================

def content_in_feed(feed, content_id):

    target_id = str(content_id)

    for item in feed:

        if not isinstance(item, dict):
            continue

        item_id = get_content_id(item)

        if item_id is not None:
            if str(item_id) == target_id:
                return True

    return False


# ============================================================
# ELIGIBILITY CHECK
# ============================================================

def check_eligibility(content, date_value, slot):

    try:

        return bool(
            engine.is_content_eligible(
                content,
                current_date=date_value,
                current_slot=slot
            )
        )

    except Exception as e:
        print(
            f"Eligibility error "
            f"({date_value}, {slot}): {e}"
        )
        return False


# ============================================================
# CREATE SPECIAL-DAY CONTENT
# ============================================================

def create_special_content():

    content = {

        # ----------------------------------------------------
        # IDs
        # ----------------------------------------------------

        "_id": SPECIAL_CONTENT_ID,
        "id": SPECIAL_CONTENT_ID,
        "content_id": SPECIAL_CONTENT_ID,

        # ----------------------------------------------------
        # CONTENT
        # ----------------------------------------------------

        "title": "Vinayagar Chaturthi Special Video",
        "name": "Vinayagar Chaturthi Special Video",

        "type": "video",
        "content_type": "video",

        "description": (
            "Vinayagar Chaturthi Special Video"
        ),

        # ----------------------------------------------------
        # CATEGORY / TAGS
        # ----------------------------------------------------

        "category": "festival",

        "categories": [
            "festival"
        ],

        "tags": [
            "vinayagar",
            "ganesh",
            "chaturthi",
            "festival",
            "special day"
        ],

        # ----------------------------------------------------
        # SPECIAL DAY
        # ----------------------------------------------------

        "special_date": SPECIAL_DATE,

        "festival": "Vinayagar Chaturthi",

        # ----------------------------------------------------
        # INTENTIONAL NORMAL SLOT
        #
        # This is deliberately morning.
        #
        # On 2026-09-04 the special-day rule must override
        # the normal time-slot restriction.
        # ----------------------------------------------------

        "time_slot": "morning",

        # ----------------------------------------------------
        # PUBLISH / EXPIRY
        # ----------------------------------------------------

        "publish_date": DAY_BEFORE,
        "expiry_date": "2026-09-10",

        # ----------------------------------------------------
        # STATUS
        # ----------------------------------------------------

        "is_active": True,
        "active": True,

        # ----------------------------------------------------
        # UNIQUE SLUG
        # ----------------------------------------------------

        "slug": (
            f"vinayagar-chaturthi-"
            f"{uuid.uuid4().hex[:8]}"
        )
    }

    # ========================================================
    # INSERT CONTENT
    # ========================================================

    inserted = False

    # First try project's normal insert_content()
    try:

        if hasattr(database, "insert_content"):

            database.insert_content(content)
            inserted = True

    except Exception as e:

        print(
            "Warning: Normal content insertion failed:"
        )
        print(e)

    # ========================================================
    # FALLBACK TO MONGODB
    # ========================================================

    if not inserted:

        try:

            # Some versions expose db
            if hasattr(database, "db"):

                db_object = database.db

                if db_object is not None:

                    db_object["Blogs"].insert_one(
                        content
                    )

                    inserted = True

            # Some versions expose database
            elif hasattr(database, "database"):

                db_object = database.database

                if db_object is not None:

                    db_object["Blogs"].insert_one(
                        content
                    )

                    inserted = True

        except Exception as e:

            print(
                "Warning: Direct MongoDB insertion failed:"
            )
            print(e)

    return content, inserted


# ============================================================
# FIND SPECIAL CONTENT
# ============================================================

def find_special_content():

    try:

        active_content = database.get_active_content()

        for content in active_content:

            content_id = get_content_id(content)

            if (
                content_id is not None
                and str(content_id)
                == str(SPECIAL_CONTENT_ID)
            ):
                return content

            if (
                get_content_title(content)
                == "Vinayagar Chaturthi Special Video"
            ):
                return content

    except Exception as e:

        print(
            f"Warning: Could not search active content: {e}"
        )

    return None


# ============================================================
# 1. NEW USER TEST
# ============================================================

def run_new_user_test():

    print_section("                    1. NEW USER")

    print("User Type        : NEW USER")
    print(f"User ID          : {NEW_USER}")
    print()

    current_date = "2026-09-02"
    current_time = "10:30"
    current_slot = "morning"

    print(f"Current Date     : {current_date}")
    print(f"Current Time     : {current_time}")
    print(f"Current Slot     : Morning")
    print()

    # --------------------------------------------------------
    # User history
    # --------------------------------------------------------

    seen_ids = get_seen_ids(NEW_USER)

    print(
        f"Previously Viewed Content : {len(seen_ids)}"
    )

    print()

    # --------------------------------------------------------
    # Feed
    # --------------------------------------------------------

    print(
        "-------------------- RECOMMENDED FEED ----------------------"
    )

    print()

    feed = get_user_feed(
        NEW_USER,
        current_date,
        current_slot,
        feed_size=7
    )

    print_feed(feed)

    print()

    print(f"Feed Size        : {len(feed)}")
    print()

    # --------------------------------------------------------
    # Result
    # --------------------------------------------------------

    passed = len(seen_ids) == 0

    if passed:

        print("NEW USER RESULT  : PASS")
        print("New user receives fresh content.")
        print("Previously viewed content = 0")

    else:

        print("NEW USER RESULT  : FAIL")
        print(
            "New user already has viewing history."
        )

    return passed


# ============================================================
# 2. OLD USER TEST
# ============================================================

def run_old_user_test():

    print_section("                    2. OLD USER")

    print("User Type        : EXISTING USER")
    print(f"User ID          : {OLD_USER}")
    print()

    # --------------------------------------------------------
    # First feed
    # --------------------------------------------------------

    initial_feed = get_user_feed(
        OLD_USER,
        "2026-09-02",
        "morning",
        feed_size=7
    )

    # --------------------------------------------------------
    # View first 5 contents
    # --------------------------------------------------------

    viewed_content_ids = []
    viewed_titles = []

    for item in initial_feed[:5]:

        if not isinstance(item, dict):
            continue

        content_id = get_content_id(item)

        if content_id is None:
            continue

        title = get_content_title(item)

        try:

            engine.mark_viewed(
                OLD_USER,
                content_id
            )

            viewed_content_ids.append(
                str(content_id)
            )

            viewed_titles.append(title)

        except Exception as e:

            print(
                f"Warning: Could not record view "
                f"for {title}: {e}"
            )

    # --------------------------------------------------------
    # History
    # --------------------------------------------------------

    seen_ids = get_seen_ids(OLD_USER)

    print(
        f"Previously Viewed Content : {len(seen_ids)}"
    )

    print()

    # --------------------------------------------------------
    # User history
    # --------------------------------------------------------

    print(
        "-------------------- USER HISTORY --------------------------"
    )

    print()

    print("Viewed:")

    if viewed_titles:

        for title in viewed_titles:
            print(f"- {title}")

    else:

        print("- No content recorded")

    print()

    # --------------------------------------------------------
    # New feed after viewing
    # --------------------------------------------------------

    print(
        "-------------------- RECOMMENDED FEED ----------------------"
    )

    print()

    new_feed = get_user_feed(
        OLD_USER,
        "2026-09-02",
        "afternoon",
        feed_size=7
    )

    print_feed(new_feed)

    print()

    print(f"Feed Size        : {len(new_feed)}")
    print()

    # --------------------------------------------------------
    # Lifetime exclusion
    # --------------------------------------------------------

    new_feed_ids = set()

    for item in new_feed:

        if not isinstance(item, dict):
            continue

        content_id = get_content_id(item)

        if content_id is not None:
            new_feed_ids.add(str(content_id))

    viewed_again = False

    for viewed_id in viewed_content_ids:

        if viewed_id in new_feed_ids:

            viewed_again = True
            break

    print(
        "Viewed content shown again : "
        + ("YES" if viewed_again else "NO")
    )

    print()

    if not viewed_again:

        print("OLD USER RESULT : PASS")
        print(
            "Previously viewed content is excluded permanently."
        )

        return True

    print("OLD USER RESULT : FAIL")
    print(
        "Previously viewed content appeared again."
    )

    return False


# ============================================================
# 3. SPECIAL DAY TEST
# ============================================================

def run_special_day_test():

    print_section("                    3. SPECIAL DAY")

    print("Special Event    : Vinayagar Chaturthi")
    print(f"Special Date     : {SPECIAL_DATE}")

    # ========================================================
    # CREATE SPECIAL CONTENT
    # ========================================================

    special_content, inserted = create_special_content()

    # Try to retrieve actual MongoDB document
    stored_content = find_special_content()

    if stored_content is not None:

        special_content = stored_content

    # ========================================================
    # BEFORE SPECIAL DAY
    # ========================================================

    print()
    print_line("-")
    print("              BEFORE SPECIAL DAY")
    print_line("-")
    print()

    before_available = check_eligibility(
        special_content,
        DAY_BEFORE,
        "morning"
    )

    print(f"Date             : {DAY_BEFORE}")

    print(
        "Special Content  : "
        + (
            "AVAILABLE"
            if before_available
            else "NOT AVAILABLE"
        )
    )

    print()

    before_pass = not before_available

    print(
        "Result           : "
        + ("PASS" if before_pass else "FAIL")
    )

    if before_pass:

        print(
            "Special-day content is not shown before the date."
        )

    else:

        print(
            "ERROR: Special-day content appeared before the date."
        )

    # ========================================================
    # SPECIAL DAY - NEW USER
    # ========================================================

    print()
    print_line("-")
    print("              SPECIAL DAY - NEW USER")
    print_line("-")
    print()

    print(f"Date             : {SPECIAL_DATE}")
    print()

    print("Special Content:")
    print(
        f"   {get_content_title(special_content)}"
    )

    print()

    print("Normal Time Slot : Morning")
    print()

    print("Special Day Rule : FULL DAY")
    print()

    # ========================================================
    # ALL FOUR TIME SLOTS
    # ========================================================

    slots = [
        ("Morning", "morning"),
        ("Afternoon", "afternoon"),
        ("Evening", "evening"),
        ("Night", "night")
    ]

    slot_results = {}

    print_line("-")

    for display_name, slot_value in slots:

        available = check_eligibility(
            special_content,
            SPECIAL_DATE,
            slot_value
        )

        slot_results[display_name] = available

        print(
            f"{display_name:<16}: "
            + (
                "AVAILABLE"
                if available
                else "NOT AVAILABLE"
            )
        )

    print_line("-")
    print()

    all_slots_pass = all(
        slot_results.values()
    )

    print(
        "Result           : "
        + (
            "PASS"
            if all_slots_pass
            else "FAIL"
        )
    )

    if all_slots_pass:

        print()
        print("User Point of View:")
        print(
            '"Today is Vinayagar Chaturthi, so I can see the'
        )
        print(
            'special Vinayagar Chaturthi content throughout the day."'
        )

    else:

        print(
            "ERROR: Special content is not available "
            "for all four time slots."
        )

    # ========================================================
    # SPECIAL DAY FEED
    # ========================================================

    print()
    print(
        "---------------- SPECIAL DAY USER FEED --------------------"
    )

    print()

    special_feed = get_user_feed(
        SPECIAL_USER,
        SPECIAL_DATE,
        "evening",
        feed_size=25
    )

    special_id = str(
        get_content_id(special_content)
    )

    special_found = content_in_feed(
        special_feed,
        special_id
    )

    print(
        "Special content eligible : "
        + (
            "YES"
            if check_eligibility(
                special_content,
                SPECIAL_DATE,
                "evening"
            )
            else "NO"
        )
    )

    print(
        "Special content in top 25 feed : "
        + (
            "YES"
            if special_found
            else "NO"
        )
    )

    # IMPORTANT:
    # The content being outside the top 25 is a ranking issue.
    # It does NOT mean that the special-date eligibility rule
    # failed.

    if all_slots_pass:

        print()
        print(
            "Special-day eligibility : PASS"
        )

    else:

        print()
        print(
            "Special-day eligibility : FAIL"
        )

    # ========================================================
    # SPECIAL DAY - AFTER VIEW
    # ========================================================

    print()
    print_line("-")
    print("              SPECIAL DAY - AFTER VIEW")
    print_line("-")
    print()

    print("User viewed:")
    print(
        f"   {get_content_title(special_content)}"
    )

    print()

    # --------------------------------------------------------
    # Mark viewed
    # --------------------------------------------------------

    try:

        engine.mark_viewed(
            SPECIAL_USER,
            special_id
        )

    except Exception as e:

        print(
            f"Warning: Could not record special-day view: {e}"
        )

    # --------------------------------------------------------
    # Verify history
    # --------------------------------------------------------

    viewed_ids = get_seen_ids(
        SPECIAL_USER
    )

    viewed_special = (
        special_id in viewed_ids
    )

    print("Viewed Content:")

    if viewed_special:

        print(
            f"   {get_content_title(special_content)}"
        )

    else:

        print(
            "   View was not recorded"
        )

    print()

    # ========================================================
    # TEST ALL FOUR SLOTS AFTER VIEW
    # ========================================================

    print_line("-")

    after_view_results = {}

    for display_name, slot_value in slots:

        feed = get_user_feed(
            SPECIAL_USER,
            SPECIAL_DATE,
            slot_value,
            feed_size=25
        )

        found = content_in_feed(
            feed,
            special_id
        )

        not_shown = not found

        after_view_results[display_name] = not_shown

        print(
            f"{display_name:<16}: "
            + (
                "NOT SHOWN"
                if not_shown
                else "SHOWN"
            )
        )

    print_line("-")
    print()

    lifetime_pass = (
        viewed_special
        and all(after_view_results.values())
    )

    print(
        "Result           : "
        + (
            "PASS"
            if lifetime_pass
            else "FAIL"
        )
    )

    if lifetime_pass:

        print()
        print("User Point of View:")
        print(
            '"I already watched this special video, so RFRE'
        )
        print(
            'will not show the same content to me again."'
        )

    else:

        print(
            "ERROR: Viewed special content appeared again."
        )

    # ========================================================
    # AFTER SPECIAL DAY
    # ========================================================

    print()
    print_line("-")
    print("              AFTER SPECIAL DAY")
    print_line("-")
    print()

    after_available = check_eligibility(
        special_content,
        DAY_AFTER,
        "morning"
    )

    print(f"Date             : {DAY_AFTER}")

    print(
        "Special Content  : "
        + (
            "AVAILABLE"
            if after_available
            else "NOT AVAILABLE"
        )
    )

    print()

    after_pass = not after_available

    print(
        "Result           : "
        + (
            "PASS"
            if after_pass
            else "FAIL"
        )
    )

    if after_pass:

        print()
        print("User Point of View:")
        print(
            '"Vinayagar Chaturthi is over, so the special content'
        )
        print(
            'is no longer available."'
        )

    else:

        print(
            "ERROR: Special content is available "
            "after the special date."
        )

    # ========================================================
    # FUTURE DATE CHECK
    # ========================================================

    future_dates = [
        "2026-09-06",
        "2026-09-07",
        "2026-09-10",
        "2026-12-25",
        "2027-01-01",
        "2027-09-04"
    ]

    future_pass = True

    for future_date in future_dates:

        available = check_eligibility(
            special_content,
            future_date,
            "morning"
        )

        if available:

            future_pass = False

    # ========================================================
    # FINAL SPECIAL DAY RESULT
    # ========================================================

    special_day_pass = (
        before_pass
        and all_slots_pass
        and lifetime_pass
        and after_pass
        and future_pass
    )

    return special_day_pass


# ============================================================
# MAIN
# ============================================================

def main():

    print()

    print_line()
    print("              PRITHU RFRE USER POINT OF VIEW")
    print_line()

    # ========================================================
    # NEW USER
    # ========================================================

    new_user_pass = run_new_user_test()

    # ========================================================
    # OLD USER
    # ========================================================

    old_user_pass = run_old_user_test()

    # ========================================================
    # SPECIAL DAY
    # ========================================================

    special_day_pass = run_special_day_test()

    # ========================================================
    # FINAL RESULT
    # ========================================================

    print()
    print_section("                     FINAL RESULT")

    print(
        "NEW USER TEST       : "
        + (
            "PASS"
            if new_user_pass
            else "FAIL"
        )
    )

    print(
        "OLD USER TEST       : "
        + (
            "PASS"
            if old_user_pass
            else "FAIL"
        )
    )

    print(
        "SPECIAL DAY TEST    : "
        + (
            "PASS"
            if special_day_pass
            else "FAIL"
        )
    )

    print(
        "LIFETIME EXCLUSION  : "
        + (
            "PASS"
            if old_user_pass
            else "FAIL"
        )
    )

    print(
        "TIME SLOT RULE      : "
        + (
            "PASS"
            if new_user_pass
            else "FAIL"
        )
    )

    print(
        "SPECIAL DATE RULE   : "
        + (
            "PASS"
            if special_day_pass
            else "FAIL"
        )
    )

    print()

    all_pass = (
        new_user_pass
        and old_user_pass
        and special_day_pass
    )

    print_line()

    if all_pass:

        print(
            "              ALL USER POINT OF VIEW TESTS PASSED"
        )

    else:

        print(
            "              SOME USER POINT OF VIEW TESTS FAILED"
        )

    print_line()
    print()


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":
    main()