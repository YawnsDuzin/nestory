"""Profile routes — /u/{username}, /u/{username}/{posts|journeys|scraps}."""
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.deps import get_current_user, get_db, require_user
from app.models import User
from app.models._enums import PostType
from app.services import profile as profile_service
from app.templating import templates

router = APIRouter(tags=["profile"])


def _user_or_404(db: Session, username: str) -> User:
    u = profile_service.get_by_username(db, username)
    if u is None:
        raise HTTPException(404, "사용자를 찾을 수 없습니다")
    return u


@router.get("/u/{username}", response_class=HTMLResponse)
def profile_home(
    username: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_current_user),
) -> HTMLResponse:
    u = _user_or_404(db, username)
    data = profile_service.profile_data(db, u)
    return templates.TemplateResponse(
        request,
        "pages/profile/home.html",
        {"profile_user": u, "data": data, "current_user": current_user},
    )


@router.get("/u/{username}/posts", response_class=HTMLResponse)
def profile_posts(
    username: str,
    request: Request,
    page: int = 1,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_current_user),
) -> HTMLResponse:
    u = _user_or_404(db, username)
    posts = profile_service.author_posts(db, u, PostType.REVIEW, page=page)
    return templates.TemplateResponse(
        request,
        "pages/profile/posts.html",
        {
            "profile_user": u,
            "posts": posts,
            "page": page,
            "page_size": profile_service.PAGE_SIZE,
            "current_user": current_user,
        },
    )


@router.get("/u/{username}/journeys", response_class=HTMLResponse)
def profile_journeys(
    username: str,
    request: Request,
    page: int = 1,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_current_user),
) -> HTMLResponse:
    u = _user_or_404(db, username)
    posts = profile_service.author_posts(db, u, PostType.JOURNEY_EPISODE, page=page)
    return templates.TemplateResponse(
        request,
        "pages/profile/journeys.html",
        {
            "profile_user": u,
            "posts": posts,
            "page": page,
            "page_size": profile_service.PAGE_SIZE,
            "current_user": current_user,
        },
    )


@router.get("/u/{username}/scraps", response_class=HTMLResponse)
def profile_scraps(
    username: str,
    request: Request,
    page: int = 1,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user),  # logged-in only
) -> HTMLResponse:
    u = _user_or_404(db, username)
    if current_user.id != u.id:
        raise HTTPException(403, "본인의 스크랩만 볼 수 있습니다")
    posts = profile_service.user_scraps(db, u, page=page)
    return templates.TemplateResponse(
        request,
        "pages/profile/scraps.html",
        {
            "profile_user": u,
            "posts": posts,
            "page": page,
            "page_size": profile_service.PAGE_SIZE,
            "current_user": current_user,
        },
    )
