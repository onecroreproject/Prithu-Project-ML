"""
PRITHU RFRE - Rule-Based Feed Recommendation Engine

Rules:
1. Normal content follows time-slot filtering.
2. Special-day content is available ONLY on its configured date.
3. Special-day content is eligible for the COMPLETE 24 hours of that date.
4. Lifetime viewed content is NEVER recommended again.
5. Interest/relevance scoring is applied after eligibility filtering.
6. Supports both `limit` and `feed_size`.
"""

from __future__ import annotations

import inspect
import re
from datetime import datetime, date, timedelta
from typing import Any, Dict, Iterable, List, Optional, Set

import database

from database import (
    get_active_content,
    get_user_seen_content_ids,
    get_user_interests,
    insert_feed,
    insert_feed_action,
    insert_user_activity,
    insert_user_view,
)


# ============================================================================
# CONFIGURATION
# ============================================================================

DAILY_FEED_SIZE = 25
INITIAL_FEED_SIZE = 7
MAXIMUM_FEED_SIZE = 25

LIFETIME_VIEW_EXCLUSION = True
VIEWED_CONTENT_EXCLUDED = True
CONTENT_REPEAT_DAYS = 0
NEW_USER_FIRST_FEED = True


# ============================================================================
# TIME SLOTS
# ============================================================================

TIME_SLOT_ALIASES = {
    "morning": "morning",
    "good morning": "morning",
    "good_morning": "morning",
    "good-morning": "morning",

    "afternoon": "afternoon",

    "evening": "evening",

    "night": "night",
}


def normalize_time_slot(value: Any) -> str:
    """Normalize different time-slot names to a standard value."""
    if value is None:
        return ""

    value = str(value).strip().lower()
    value = re.sub(r"\s+", " ", value)

    return TIME_SLOT_ALIASES.get(value, value)


def get_current_time_slot(now: Optional[datetime] = None) -> str:
    """
    Return current time slot.

    Morning   : 05:00 - 10:59
    Afternoon : 11:00 - 15:29
    Evening   : 15:30 - 19:29
    Night     : 19:30 - 04:59
    """

    now = now or datetime.now()
    current_time = now.time()

    if current_time >= datetime.strptime("05:00", "%H:%M").time() and \
       current_time < datetime.strptime("11:00", "%H:%M").time():
        return "morning"

    if current_time >= datetime.strptime("11:00", "%H:%M").time() and \
       current_time < datetime.strptime("15:30", "%H:%M").time():
        return "afternoon"

    if current_time >= datetime.strptime("15:30", "%H:%M").time() and \
       current_time < datetime.strptime("19:30", "%H:%M").time():
        return "evening"

    return "night"


def get_current_weekday(now: Optional[datetime] = None) -> str:
    now = now or datetime.now()
    return now.strftime("%A").lower()


def get_current_date(now: Optional[datetime] = None) -> str:
    now = now or datetime.now()
    return now.strftime("%Y-%m-%d")


# ============================================================================
# GENERAL HELPERS
# ============================================================================

def safe_string(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def parse_tags(value: Any) -> List[str]:
    """Convert tags/categories into a normalized list."""
    if value is None:
        return []

    if isinstance(value, list):
        values = value

    elif isinstance(value, tuple):
        values = list(value)

    elif isinstance(value, str):
        text = value.strip()

        if not text:
            return []

        # JSON-like list
        if text.startswith("[") and text.endswith("]"):
            try:
                import json
                parsed = json.loads(text)
                if isinstance(parsed, list):
                    values = parsed
                else:
                    values = [text]
            except Exception:
                values = re.split(r"[,|]", text)

        else:
            values = re.split(r"[,|]", text)

    else:
        values = [value]

    result = []

    for item in values:
        item = safe_string(item).lower()

        if item:
            result.append(item)

    return list(dict.fromkeys(result))


def normalize_interests(value: Any) -> Set[str]:
    return set(parse_tags(value))


def parse_date_value(value: Any) -> Optional[date]:
    """Safely parse MongoDB/date/string values."""
    if value is None:
        return None

    if isinstance(value, datetime):
        return value.date()

    if isinstance(value, date):
        return value

    # MongoDB Object / date-like values
    if hasattr(value, "date") and callable(value.date):
        try:
            return value.date()
        except Exception:
            pass

    text = safe_string(value)

    if not text:
        return None

    # ISO datetime
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
    except Exception:
        pass

    formats = [
        "%Y-%m-%d",
        "%d-%m-%Y",
        "%d/%m/%Y",
        "%Y/%m/%d",
        "%Y-%m-%d %H:%M:%S",
    ]

    for fmt in formats:
        try:
            return datetime.strptime(text, fmt).date()
        except Exception:
            continue

    return None


def get_content_id(content: Dict[str, Any]) -> str:
    """
    Extract content ID from common MongoDB/document fields.
    """

    for field in ("content_id", "contentId", "id", "_id"):
        value = content.get(field)

        if value is not None:
            value = safe_string(value)

            if value:
                return value

    return ""


# ============================================================================
# SPECIAL DAY HELPERS
# ============================================================================

def get_special_date(content: Dict[str, Any]) -> Optional[date]:
    """
    Find the configured special-day date.

    Supported fields:
        special_date
        specialDate
        festival_date
        festivalDate
        event_date
        eventDate
    """

    fields = (
        "special_date",
        "specialDate",
        "festival_date",
        "festivalDate",
        "event_date",
        "eventDate",
    )

    for field in fields:
        if field in content:
            parsed = parse_date_value(content.get(field))

            if parsed:
                return parsed

    return None


def is_special_day_content(content: Dict[str, Any]) -> bool:
    """
    Determine whether content is configured as special-day content.

    The presence of a valid special date is enough to identify it.
    """

    return get_special_date(content) is not None


def is_special_day_today(
    content: Dict[str, Any],
    current_date: Optional[str] = None,
) -> bool:
    """
    Return True ONLY when today's date exactly matches the configured
    special date.

    This gives the content a full 24-hour eligibility window for that day.
    """

    special_date = get_special_date(content)

    if special_date is None:
        return False

    current = parse_date_value(current_date)

    if current is None:
        current = datetime.now().date()

    return special_date == current


def is_special_content_for_today(
    content: Dict[str, Any],
    current_date: Optional[str] = None,
) -> bool:
    return is_special_day_today(content, current_date)


# ============================================================================
# SCORING
# ============================================================================

def calculate_interest_score(
    content: Dict[str, Any],
    user_interests: Set[str],
) -> float:
    if not user_interests:
        return 0.0

    content_values = set()

    for field in (
        "tags",
        "categories",
        "category",
        "interests",
        "keywords",
        "topic",
    ):
        content_values.update(parse_tags(content.get(field)))

    if not content_values:
        return 0.0

    matches = content_values.intersection(user_interests)

    if not matches:
        return 0.0

    return min(40.0, float(len(matches) * 10))


def calculate_time_score(
    content: Dict[str, Any],
    current_slot: str,
) -> float:
    """
    Special-day content receives full time eligibility regardless of
    morning/afternoon/evening/night.

    Normal content gets a score when its time slot matches.
    """

    if is_special_day_content(content):
        return 15.0 if is_special_day_today(content) else 0.0

    content_slot = normalize_time_slot(
        content.get("time_slot", content.get("timeSlot"))
    )

    current_slot = normalize_time_slot(current_slot)

    if not content_slot:
        return 15.0

    if content_slot == current_slot:
        return 15.0

    return 0.0


def calculate_weekday_score(
    content: Dict[str, Any],
    current_day: str,
) -> float:
    configured = content.get(
        "weekday",
        content.get("weekDay", content.get("day")),
    )

    if not configured:
        return 5.0

    configured_days = parse_tags(configured)

    current_day = safe_string(current_day).lower()

    if current_day in configured_days:
        return 10.0

    return 0.0


def calculate_special_day_score(
    content: Dict[str, Any],
    current_date: Optional[str] = None,
) -> float:
    """
    Special-day content gets a high score ONLY on its configured date.
    """

    if not is_special_day_content(content):
        return 0.0

    if is_special_day_today(content, current_date):
        return 25.0

    return 0.0


def calculate_freshness_score(
    content: Dict[str, Any],
    current_date: Optional[str] = None,
) -> float:
    current = parse_date_value(current_date) or datetime.now().date()

    publish_date = parse_date_value(
        content.get(
            "publish_date",
            content.get("publishDate", content.get("created_at")),
        )
    )

    if publish_date is None:
        return 0.0

    age = (current - publish_date).days

    if age < 0:
        return 0.0

    if age <= 1:
        return 10.0

    if age <= 3:
        return 7.0

    if age <= 7:
        return 5.0

    if age <= 30:
        return 2.0

    return 0.0


def calculate_engagement_score(content: Dict[str, Any]) -> float:
    likes = float(content.get("likes", 0) or 0)
    views = float(content.get("views", 0) or 0)
    shares = float(content.get("shares", 0) or 0)
    comments = float(content.get("comments", 0) or 0)

    score = (
        min(likes / 100.0, 5.0)
        + min(views / 1000.0, 5.0)
        + min(shares / 50.0, 5.0)
        + min(comments / 50.0, 5.0)
    )

    return round(score, 2)


def calculate_priority_score(content: Dict[str, Any]) -> float:
    priority = content.get("priority", 0)

    try:
        return min(float(priority), 10.0)
    except Exception:
        return 0.0


def calculate_total_score(
    content: Dict[str, Any],
    user_interests: Set[str],
    current_date: str,
    current_slot: str,
    current_day: str,
) -> float:

    score = 0.0

    score += calculate_interest_score(
        content,
        user_interests,
    )

    score += calculate_time_score(
        content,
        current_slot,
    )

    score += calculate_weekday_score(
        content,
        current_day,
    )

    score += calculate_special_day_score(
        content,
        current_date,
    )

    score += calculate_freshness_score(
        content,
        current_date,
    )

    score += calculate_engagement_score(content)

    score += calculate_priority_score(content)

    return round(score, 2)


# ============================================================================
# CONTENT ELIGIBILITY
# ============================================================================

def is_content_eligible(
    content: Dict[str, Any],
    current_date: Optional[str] = None,
    current_slot: Optional[str] = None,
    current_day: Optional[str] = None,
) -> bool:
    """
    Main eligibility function.

    SPECIAL DAY RULE
    ----------------
    If content has a special_date:

        today == special_date
            -> eligible for FULL 24 HOURS

        today != special_date
            -> NOT eligible

    Normal content continues to use time-slot filtering.
    """

    current_date = current_date or get_current_date()
    current_slot = normalize_time_slot(
        current_slot or get_current_time_slot()
    )
    current_day = safe_string(
        current_day or get_current_weekday()
    ).lower()

    # ----------------------------------------------------------------------
    # SPECIAL DAY CONTENT
    # ----------------------------------------------------------------------
    if is_special_day_content(content):

        # Special content is available ONLY on its configured date.
        if not is_special_day_today(content, current_date):
            return False

        # IMPORTANT:
        # Do NOT check morning/afternoon/evening/night here.
        #
        # Special-day content is eligible:
        # 00:00 -> 23:59
        #
        # of the configured date.
        return True

    # ----------------------------------------------------------------------
    # NORMAL PUBLISH DATE
    # ----------------------------------------------------------------------
    publish_date = parse_date_value(
        content.get(
            "publish_date",
            content.get("publishDate"),
        )
    )

    today = parse_date_value(current_date)

    if publish_date and today:
        if publish_date > today:
            return False

    # ----------------------------------------------------------------------
    # NORMAL EXPIRY DATE
    # ----------------------------------------------------------------------
    expiry_date = parse_date_value(
        content.get(
            "expiry_date",
            content.get("expiryDate"),
        )
    )

    if expiry_date and today:
        if today > expiry_date:
            return False

    # ----------------------------------------------------------------------
    # WEEKDAY FILTER
    # ----------------------------------------------------------------------
    configured_weekday = content.get(
        "weekday",
        content.get(
            "weekDay",
            content.get("day"),
        ),
    )

    if configured_weekday:
        configured_days = parse_tags(configured_weekday)

        if current_day not in configured_days:
            return False

    # ----------------------------------------------------------------------
    # NORMAL TIME-SLOT FILTER
    # ----------------------------------------------------------------------
    configured_slot = normalize_time_slot(
        content.get(
            "time_slot",
            content.get("timeSlot"),
        )
    )

    # Empty slot = unrestricted normal content.
    if configured_slot:
        if configured_slot != current_slot:
            return False

    return True


# ============================================================================
# DUPLICATE REMOVAL
# ============================================================================

def remove_duplicates(
    contents: Iterable[Dict[str, Any]],
) -> List[Dict[str, Any]]:

    result = []
    seen = set()

    for content in contents:
        content_id = get_content_id(content)

        if not content_id:
            continue

        if content_id in seen:
            continue

        seen.add(content_id)
        result.append(content)

    return result


# ============================================================================
# DATABASE COMPATIBILITY HELPERS
# ============================================================================

def _call_function_compat(
    func,
    payload: Dict[str, Any],
    positional_fallbacks: Optional[List[tuple]] = None,
):
    """
    Call existing database functions regardless of whether the current
    database.py expects keyword arguments or positional arguments.
    """

    try:
        signature = inspect.signature(func)

        kwargs = {}

        for name, parameter in signature.parameters.items():

            if name in payload:
                kwargs[name] = payload[name]

        required_missing = []

        for name, parameter in signature.parameters.items():

            if parameter.kind in (
                inspect.Parameter.POSITIONAL_ONLY,
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
            ):
                if parameter.default is inspect.Parameter.empty:
                    if name not in kwargs:
                        required_missing.append(name)

        if not required_missing:
            return func(**kwargs)

    except Exception:
        pass

    # Positional fallback
    if positional_fallbacks:

        for args in positional_fallbacks:

            try:
                return func(*args)
            except TypeError:
                continue

    # Final dictionary fallback
    try:
        return func(payload)
    except TypeError:
        raise


def _store_feed(
    user_id: str,
    current_date: str,
    current_slot: str,
    current_day: str,
    content_ids: List[str],
    initial_count: int,
    daily_limit: int,
):

    payload = {
        "user_id": user_id,
        "userId": user_id,

        "date": current_date,
        "feed_date": current_date,
        "feedDate": current_date,

        "time_slot": current_slot,
        "timeSlot": current_slot,

        "weekday": current_day,
        "weekDay": current_day,

        "content_ids": content_ids,
        "contentIds": content_ids,

        "initial_count": initial_count,
        "initialCount": initial_count,

        "daily_limit": daily_limit,
        "dailyLimit": daily_limit,
    }

    fallbacks = [
        (
            user_id,
            current_date,
            current_slot,
            content_ids,
        ),
        (
            user_id,
            current_date,
            current_slot,
            content_ids,
            initial_count,
            daily_limit,
        ),
    ]

    return _call_function_compat(
        insert_feed,
        payload,
        fallbacks,
    )


def _store_feed_action(
    user_id: str,
    content_id: str,
    action: str,
):

    payload = {
        "user_id": user_id,
        "userId": user_id,

        "content_id": content_id,
        "contentId": content_id,

        "action": action,
        "action_type": action,
        "actionType": action,

        "target_id": content_id,
        "targetId": content_id,

        "target_model": "Content",
        "targetModel": "Content",
    }

    fallbacks = [
        (user_id, content_id, action),
        (user_id, action, content_id),
    ]

    return _call_function_compat(
        insert_feed_action,
        payload,
        fallbacks,
    )


def _store_user_activity(
    user_id: str,
    content_id: str,
    action: str,
):

    payload = {
        "user_id": user_id,
        "userId": user_id,

        "content_id": content_id,
        "contentId": content_id,

        "action": action,
        "action_type": action,
        "actionType": action,

        "target_id": content_id,
        "targetId": content_id,

        "target_model": "Content",
        "targetModel": "Content",
    }

    fallbacks = [
        (user_id, action, content_id),
        (user_id, content_id, action),
    ]

    return _call_function_compat(
        insert_user_activity,
        payload,
        fallbacks,
    )


def _store_user_view(
    user_id: str,
    content_id: str,
):

    payload = {
        "user_id": user_id,
        "userId": user_id,

        "content_id": content_id,
        "contentId": content_id,

        "action": "view",
        "action_type": "view",
        "actionType": "view",

        "target_id": content_id,
        "targetId": content_id,

        "target_model": "Content",
        "targetModel": "Content",
    }

    fallbacks = [
        (user_id, content_id),
        (user_id, content_id, "view"),
    ]

    return _call_function_compat(
        insert_user_view,
        payload,
        fallbacks,
    )


# ============================================================================
# FEED GENERATION
# ============================================================================

def generate_feed(
    user_id: str,
    limit: int = DAILY_FEED_SIZE,
    prefer_short: bool = False,
    exclude_ids: Optional[Iterable[str]] = None,
    feed_size: Optional[int] = None,

    # Optional simulation/testing parameters
    current_date: Optional[str] = None,
    current_slot: Optional[str] = None,
    current_day: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Generate personalized feed.

    `feed_size` is supported as an alias for `limit`.

    Optional current_date/current_slot/current_day allow testing:
        generate_feed(..., current_slot="morning")
        generate_feed(..., current_slot="afternoon")
        generate_feed(..., current_slot="evening")
        generate_feed(..., current_slot="night")
    """

    try:

        # ------------------------------------------------------------------
        # LIMIT
        # ------------------------------------------------------------------
        if feed_size is not None:
            limit = feed_size

        try:
            limit = int(limit)
        except Exception:
            limit = DAILY_FEED_SIZE

        limit = max(1, min(limit, MAXIMUM_FEED_SIZE))

        # ------------------------------------------------------------------
        # CURRENT DATE/TIME
        # ------------------------------------------------------------------
        current_date = current_date or get_current_date()

        current_slot = normalize_time_slot(
            current_slot or get_current_time_slot()
        )

        current_day = safe_string(
            current_day or get_current_weekday()
        ).lower()

        # ------------------------------------------------------------------
        # GET USER HISTORY
        # ------------------------------------------------------------------
        seen_ids: Set[str] = set()

        if LIFETIME_VIEW_EXCLUSION and VIEWED_CONTENT_EXCLUDED:

            try:
                history = get_user_seen_content_ids(user_id)

                if history:
                    seen_ids.update(
                        safe_string(x)
                        for x in history
                        if safe_string(x)
                    )

            except Exception as exc:
                print(
                    f"Warning: Could not read viewed content history: {exc}"
                )

        # Explicit exclusions
        if exclude_ids:

            seen_ids.update(
                safe_string(x)
                for x in exclude_ids
                if safe_string(x)
            )

        # ------------------------------------------------------------------
        # USER INTERESTS
        # ------------------------------------------------------------------
        user_interests: Set[str] = set()

        try:

            interests = get_user_interests(user_id)

            user_interests = normalize_interests(interests)

        except Exception as exc:
            print(
                f"Warning: Could not read user interests: {exc}"
            )

        # ------------------------------------------------------------------
        # ACTIVE CONTENT
        # ------------------------------------------------------------------
        active_content = get_active_content()

        if not active_content:
            return {
                "success": True,
                "user_id": user_id,
                "date": current_date,
                "time_slot": current_slot,
                "weekday": current_day,
                "feed": [],
                "feed_count": 0,
                "initial_count": 0,
            }

        # ------------------------------------------------------------------
        # REMOVE DUPLICATES
        # ------------------------------------------------------------------
        active_content = remove_duplicates(active_content)

        # ------------------------------------------------------------------
        # ELIGIBILITY + LIFETIME EXCLUSION
        # ------------------------------------------------------------------
        eligible_content = []

        for content in active_content:

            content_id = get_content_id(content)

            if not content_id:
                continue

            # IMPORTANT:
            # Lifetime viewed exclusion happens BEFORE scoring.
            if content_id in seen_ids:
                continue

            if not is_content_eligible(
                content,
                current_date=current_date,
                current_slot=current_slot,
                current_day=current_day,
            ):
                continue

            item = dict(content)

            item["_recommendation_score"] = calculate_total_score(
                content=item,
                user_interests=user_interests,
                current_date=current_date,
                current_slot=current_slot,
                current_day=current_day,
            )

            eligible_content.append(item)

        # ------------------------------------------------------------------
        # OPTIONAL SHORT CONTENT PREFERENCE
        # ------------------------------------------------------------------
        if prefer_short:

            def short_score(item):
                duration = item.get(
                    "duration",
                    item.get("duration_seconds", 999999),
                )

                try:
                    return float(duration)
                except Exception:
                    return 999999

            eligible_content.sort(
                key=lambda x: (
                    -x.get("_recommendation_score", 0),
                    short_score(x),
                )
            )

        else:

            eligible_content.sort(
                key=lambda x: (
                    -x.get("_recommendation_score", 0),
                    get_content_id(x),
                )
            )

        # ------------------------------------------------------------------
        # INITIAL FEED
        # ------------------------------------------------------------------
        selected = eligible_content[:limit]

        initial_count = min(
            len(selected),
            INITIAL_FEED_SIZE,
        )

        content_ids = [
            get_content_id(item)
            for item in selected
            if get_content_id(item)
        ]

        # ------------------------------------------------------------------
        # STORE GENERATED FEED
        # ------------------------------------------------------------------
        if content_ids:

            try:

                _store_feed(
                    user_id=user_id,
                    current_date=current_date,
                    current_slot=current_slot,
                    current_day=current_day,
                    content_ids=content_ids,
                    initial_count=initial_count,
                    daily_limit=limit,
                )

            except Exception as exc:

                print(
                    f"Warning: Feed storage failed: {exc}"
                )

        # ------------------------------------------------------------------
        # PREPARE OUTPUT
        # ------------------------------------------------------------------
        feed = []

        for item in selected:

            result = dict(item)

            result["content_id"] = get_content_id(item)
            result["recommendation_score"] = item.get(
                "_recommendation_score",
                0.0,
            )

            # Remove internal field
            result.pop("_recommendation_score", None)

            feed.append(result)

        return {
            "success": True,
            "user_id": user_id,
            "date": current_date,
            "time_slot": current_slot,
            "weekday": current_day,
            "feed": feed,
            "feed_count": len(feed),
            "initial_count": initial_count,
        }

    except Exception as exc:

        print(
            f"Feed generation error: {exc}"
        )

        return {
            "success": False,
            "user_id": user_id,
            "date": current_date or get_current_date(),
            "time_slot": current_slot or get_current_time_slot(),
            "weekday": current_day or get_current_weekday(),
            "feed": [],
            "feed_count": 0,
            "initial_count": 0,
            "error": str(exc),
        }


# ============================================================================
# VIEW RECORDING
# ============================================================================

def mark_viewed(
    user_id: str,
    content_id: str,
) -> bool:
    """
    Permanently mark content as viewed.

    A view is recorded in:
        1. UserViews
        2. UserFeedActions
        3. UserActivities

    After this, get_user_seen_content_ids() must exclude the content
    permanently.
    """

    user_id = safe_string(user_id)
    content_id = safe_string(content_id)

    if not user_id or not content_id:
        return False

    success_count = 0

    # ----------------------------------------------------------------------
    # USER VIEWS
    # ----------------------------------------------------------------------
    try:

        _store_user_view(
            user_id,
            content_id,
        )

        success_count += 1

    except Exception as exc:

        print(
            f"Warning: UserViews insert failed: {exc}"
        )

    # ----------------------------------------------------------------------
    # USER FEED ACTIONS
    # ----------------------------------------------------------------------
    try:

        _store_feed_action(
            user_id,
            content_id,
            "viewed",
        )

        success_count += 1

    except Exception as exc:

        print(
            f"Warning: UserFeedActions insert failed: {exc}"
        )

    # ----------------------------------------------------------------------
    # USER ACTIVITIES
    # ----------------------------------------------------------------------
    try:

        _store_user_activity(
            user_id,
            content_id,
            "viewed",
        )

        success_count += 1

    except Exception as exc:

        print(
            f"Warning: UserActivities insert failed: {exc}"
        )

    return success_count > 0


# ============================================================================
# TEST
# ============================================================================

def run_engine_test():

    print("=" * 70)
    print("PRITHU RFRE - RECOMMENDATION ENGINE TEST")
    print("=" * 70)

    current_date = get_current_date()
    current_day = get_current_weekday()
    current_slot = get_current_time_slot()

    print()
    print(f"Current date: {current_date}")
    print(f"Current weekday: {current_day}")
    print(f"Current time slot: {current_slot}")

    print()
    print("-" * 70)
    print("TIME SLOT TEST")
    print("-" * 70)

    test_slots = [
        "morning",
        "afternoon",
        "evening",
        "night",
    ]

    for slot in test_slots:
        print(
            f"{slot.capitalize():<12} -> eligibility function available"
        )

    print()
    print("-" * 70)
    print("FEED GENERATION TEST")
    print("-" * 70)

    # Test user
    test_user = "engine_test_user"

    result = generate_feed(
        user_id=test_user,
        feed_size=INITIAL_FEED_SIZE,
    )

    print(
        f"Success: {result.get('success')}"
    )

    print(
        f"Time slot: {result.get('time_slot')}"
    )

    print(
        f"Weekday: {result.get('weekday')}"
    )

    print(
        f"Feed count: {result.get('feed_count')}"
    )

    print(
        f"Initial count: {result.get('initial_count')}"
    )

    for index, item in enumerate(
        result.get("feed", []),
        start=1,
    ):

        title = item.get(
            "title",
            item.get("name", "Untitled"),
        )

        slot = item.get(
            "time_slot",
            item.get("timeSlot", ""),
        )

        score = item.get(
            "recommendation_score",
            0,
        )

        print(
            f"{index}. {title} | "
            f"Slot={slot} | "
            f"Score={score}"
        )

    if result.get("success"):
        print()
        print("ENGINE TEST: PASS")
    else:
        print()
        print("ENGINE TEST: FAIL")

    print("=" * 70)


# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    run_engine_test()