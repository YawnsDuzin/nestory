from collections.abc import Callable

from fastapi import Depends, Header, HTTPException, Path, Request, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import Post
from app.models.user import BadgeLevel, User, UserRole


def get_current_user(
    request: Request,
    db: Session = Depends(get_db),
    authorization: str | None = Header(None),
) -> User | None:
    # P2 네이티브 클라이언트 Bearer 토큰 분기 placeholder — 현재 미사용.
    # CLAUDE.md "네이티브 확장 대비 > 인증 가드 dual 시그니처" 참조.
    _ = authorization
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


def require_author(post_id_param: str = "post_id") -> Callable[..., Post]:
    """Factory dependency — path param의 post_id로 Post를 로드해 본인 소유인지 검증.

    동작:
    - Post 존재 안 함 OR deleted_at != None → 404
    - author_id != user.id → 403
    - 통과 시 Post ORM 인스턴스를 라우트에 주입 (재조회 불필요)

    Usage:
        @router.post("/post/{post_id}/delete")
        def delete(post: Post = Depends(require_author("post_id")), ...):
    """

    def dependency(
        user: User = Depends(require_user),
        db: Session = Depends(get_db),
        post_id: int = Path(..., alias=post_id_param),
    ) -> Post:
        post = db.get(Post, post_id)
        if post is None or post.deleted_at is not None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Post not found")
        if post.author_id != user.id:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Not the author")
        return post

    return dependency


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
    "require_author",
    "require_badge",
    "require_resident_in_region",
    "require_user",
]
