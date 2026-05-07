"""Feed routes — /feed (global published feed)."""
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.deps import get_current_user, get_db
from app.models import User
from app.services import feed as feed_service
from app.templating import templates

router = APIRouter(tags=["feed"])


@router.get("/feed", response_class=HTMLResponse)
def feed(
    request: Request,
    page: int = 1,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_current_user),
) -> HTMLResponse:
    posts, total = feed_service.global_feed(db, page=page)
    return templates.TemplateResponse(
        request,
        "pages/feed.html",
        {
            "posts": posts,
            "total": total,
            "page": page,
            "page_size": feed_service.PAGE_SIZE,
            "current_user": current_user,
        },
    )
