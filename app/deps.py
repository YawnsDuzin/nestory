from collections.abc import Callable

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.user import BadgeLevel, User, UserRole


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User | None:
    user_id = request.session.get("user_id")
    if not user_id:
        return None
    return db.get(User, user_id)


def require_user(user: User | None = Depends(get_current_user)) -> User:
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Login required")
    return user


def require_admin(user: User = Depends(require_user)) -> User:
    if user.role != UserRole.ADMIN:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Admin only")
    return user


_BADGE_RANK = {
    BadgeLevel.INTERESTED: 0,
    BadgeLevel.REGION_VERIFIED: 1,
    BadgeLevel.RESIDENT: 2,
    BadgeLevel.EX_RESIDENT: -1,  # 작성 권한 박탈 — 어떤 require_badge도 통과 안 함
}


def require_badge(min_level: BadgeLevel) -> Callable[[User], User]:
    """배지 레벨 기반 가드 팩토리.

    `Depends(require_badge(BadgeLevel.RESIDENT))` 형태로 라우트에서 사용.
    EX_RESIDENT 는 모든 require_badge 가드를 통과 못한다 (PRD §5.4.1).
    """
    required_rank = _BADGE_RANK[min_level]

    def _checker(user: User = Depends(require_user)) -> User:
        user_rank = _BADGE_RANK.get(user.badge_level, -1)
        if user_rank < required_rank:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                f"Badge level '{min_level.value}' or higher required",
            )
        return user

    return _checker


def require_resident_in_region(region_id_param: str = "region_id") -> Callable[..., User]:
    """동일 시군의 resident 만 통과 — Pillar V 검증 권한 등에 사용.

    `region_id_param` 은 path/query parameter 이름. 기본값 'region_id'.
    """

    def _checker(
        request: Request,
        user: User = Depends(require_badge(BadgeLevel.RESIDENT)),
    ) -> User:
        path_value = request.path_params.get(region_id_param)
        query_value = request.query_params.get(region_id_param)
        target_region_id = path_value or query_value
        if target_region_id is None:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                f"Missing '{region_id_param}' in request",
            )
        if user.primary_region_id is None or str(user.primary_region_id) != str(target_region_id):
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                "Resident in this region only",
            )
        return user

    return _checker


__all__ = [
    "get_current_user",
    "get_db",
    "require_admin",
    "require_badge",
    "require_resident_in_region",
    "require_user",
]
