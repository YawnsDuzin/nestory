"""Notifications routes — in-app bell + /notifications page.

PRD §9.3 P1 종료 기준 알림 표시 surface.
"""
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.deps import get_db, require_user
from app.models import User
from app.services import notifications as nsvc
from app.services.analytics import EventName, emit
from app.templating import templates

router = APIRouter(tags=["notifications"])


@router.get("/notifications", response_class=HTMLResponse)
def notifications_page(
    request: Request,
    page: int = 1,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user),
) -> HTMLResponse:
    views, total = nsvc.list_paginated(db, current_user, page=page)
    return templates.TemplateResponse(
        request,
        "pages/notifications.html",
        {
            "views": views,
            "total": total,
            "page": page,
            "page_size": nsvc.PAGE_SIZE,
            "current_user": current_user,
        },
    )


@router.get("/notifications/_bell", response_class=HTMLResponse)
def notifications_bell(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user),
) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "components/_bell.html",
        {
            "unread_count": nsvc.unread_count(db, current_user),
            "recent": nsvc.recent_for_dropdown(db, current_user),
            "current_user": current_user,
        },
    )


@router.post("/notifications/{notif_id}/read", response_model=None)
def notification_read(
    notif_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user),
) -> RedirectResponse:
    notif = nsvc.mark_read(db, current_user, notif_id)
    if notif is None:
        raise HTTPException(404, "알림을 찾을 수 없습니다")
    db.commit()
    emit(EventName.NOTIFICATION_OPENED)
    return RedirectResponse(url=nsvc._resolve_link(notif), status_code=303)


@router.post("/notifications/read-all", response_model=None)
def notifications_read_all(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user),
) -> RedirectResponse:
    nsvc.mark_all_read(db, current_user)
    db.commit()
    return RedirectResponse(url="/notifications", status_code=303)
