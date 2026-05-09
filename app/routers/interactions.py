"""Interactions + comment routes — like/scrap toggle (HTMX) + comment create."""
from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.deps import get_db, require_user
from app.models import Post, User
from app.services import comments as comments_service
from app.services import interactions as interactions_service
from app.templating import templates

router = APIRouter(tags=["interactions"])


def _post_or_404(db: Session, post_id: int) -> Post:
    post = db.get(Post, post_id)
    if post is None or post.deleted_at is not None:
        raise HTTPException(404, "글을 찾을 수 없습니다")
    return post


def _render_like(
    request: Request, post: Post, liked: bool, count: int
) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "partials/like_button.html",
        {"post": post, "liked": liked, "count": count},
    )


def _render_scrap(
    request: Request, post: Post, scrapped: bool, count: int
) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "partials/scrap_button.html",
        {"post": post, "scrapped": scrapped, "count": count},
    )


@router.post("/post/{post_id}/like", response_class=HTMLResponse)
def post_like(
    post_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user),
) -> HTMLResponse:
    post = _post_or_404(db, post_id)
    now_liked = interactions_service.toggle_like(db, post, current_user)
    return _render_like(
        request, post, liked=now_liked, count=interactions_service.like_count(db, post.id)
    )


@router.post("/post/{post_id}/unlike", response_class=HTMLResponse)
def post_unlike(
    post_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user),
) -> HTMLResponse:
    post = _post_or_404(db, post_id)
    now_liked = interactions_service.toggle_like(db, post, current_user)
    return _render_like(
        request, post, liked=now_liked, count=interactions_service.like_count(db, post.id)
    )


@router.post("/post/{post_id}/scrap", response_class=HTMLResponse)
def post_scrap(
    post_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user),
) -> HTMLResponse:
    post = _post_or_404(db, post_id)
    now_scrapped = interactions_service.toggle_scrap(db, post, current_user)
    return _render_scrap(
        request,
        post,
        scrapped=now_scrapped,
        count=interactions_service.scrap_count(db, post.id),
    )


@router.post("/post/{post_id}/unscrap", response_class=HTMLResponse)
def post_unscrap(
    post_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user),
) -> HTMLResponse:
    post = _post_or_404(db, post_id)
    now_scrapped = interactions_service.toggle_scrap(db, post, current_user)
    return _render_scrap(
        request,
        post,
        scrapped=now_scrapped,
        count=interactions_service.scrap_count(db, post.id),
    )


@router.post("/post/{post_id}/comment")
def post_comment(
    post_id: int,
    body: str = Form(...),
    parent_id: int | None = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user),
) -> RedirectResponse:
    post = _post_or_404(db, post_id)
    try:
        comments_service.create_comment(
            db, post, current_user, body, parent_id=parent_id
        )
    except comments_service.CommentValidationError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e)) from e
    # Redirect target is type-aware.
    if post.type.value == "journey_episode":
        target = f"/journey/{post.journey_id}/ep/{post.episode_no}#comments"
    elif post.type.value == "question":
        target = f"/question/{post.id}#comments"
    else:
        target = f"/post/{post.id}#comments"
    return RedirectResponse(target, status_code=status.HTTP_303_SEE_OTHER)
