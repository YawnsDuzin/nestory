from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.deps import get_db, require_user
from app.models import BadgeApplication, Region, User
from app.models._enums import BadgeApplicationStatus, BadgeRequestedLevel
from app.services import badges
from app.templating import templates

router = APIRouter(prefix="/me", tags=["me"])


@router.get("/badge", response_class=HTMLResponse)
def badge_page(
    request: Request,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    pending = (
        db.query(BadgeApplication)
        .filter(
            BadgeApplication.user_id == user.id,
            BadgeApplication.status == BadgeApplicationStatus.PENDING,
        )
        .order_by(BadgeApplication.applied_at.desc())
        .first()
    )
    regions = db.query(Region).order_by(Region.sigungu).all()
    return templates.TemplateResponse(
        request,
        "pages/me_badge.html",
        {"user": user, "pending": pending, "regions": regions},
    )


@router.post("/badge/region")
def apply_region(
    region_id: int = Form(...),
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    region = db.get(Region, region_id)
    if region is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid region")

    # Block duplicate pending applications
    existing = (
        db.query(BadgeApplication)
        .filter(
            BadgeApplication.user_id == user.id,
            BadgeApplication.status == BadgeApplicationStatus.PENDING,
        )
        .first()
    )
    if existing is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Pending application exists")

    badges.submit_application(
        db,
        user=user,
        requested_level=BadgeRequestedLevel.REGION_VERIFIED,
        region_id=region.id,
    )
    db.commit()
    return RedirectResponse("/me/badge", status_code=status.HTTP_303_SEE_OTHER)
