# ============================================================
# PRITHU RFRE - API MODELS
# ============================================================

from typing import List, Optional

from pydantic import BaseModel, Field


# ============================================================
# RECOMMEND REQUEST
# ============================================================

class RecommendRequest(BaseModel):

    userId: str = Field(
        ...,
        min_length=1
    )

    feedId: Optional[str] = None

    excludeIds: List[int] = []

    limit: int = Field(
        default=20,
        ge=1,
        le=100
    )

    preferShort: bool = False

    diversityBoost: bool = False


# ============================================================
# SEEN REQUEST
# ============================================================

class SeenRequest(BaseModel):

    userId: str = Field(
        ...,
        min_length=1
    )

    contentId: int


# ============================================================
# CONTENT CREATE REQUEST
# ============================================================

class ContentCreateRequest(BaseModel):

    title: str = Field(
        ...,
        min_length=1
    )

    category: str = Field(
        ...,
        min_length=1
    )

    tags: Optional[str] = None

    post_type: str = "image"

    media_url: Optional[str] = None

    publish_date: Optional[str] = None

    expiry_date: Optional[str] = None

    weekday: Optional[str] = None

    time_slot: Optional[str] = None

    festival: Optional[str] = None

    priority: Optional[str] = "Medium"

    duration: Optional[int] = 0

