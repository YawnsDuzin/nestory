"""Pydantic schemas for profile read/write — used by HTML form routes today,
JSON API tomorrow. See spec §4.3."""
from pydantic import BaseModel, ConfigDict


class ProfileRead(BaseModel):
    """User profile snapshot. Used by GET /me/profile JSON API in P2+."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    display_name: str
    bio: str | None
    avatar_image_id: int | None
    primary_region_id: int | None
    notify_email_enabled: bool
    notify_kakao_enabled: bool


__all__ = ["ProfileRead"]
