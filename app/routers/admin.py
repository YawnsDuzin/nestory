from datetime import UTC, datetime, timedelta
from pathlib import Path

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.deps import get_db, require_admin
from app.models import BadgeApplication, BadgeEvidence, Region, User
from app.models._enums import JobKind
from app.services import badges
from app.templating import templates
from app.workers import queue

router = APIRouter(prefix="/admin", tags=["admin"])

EVIDENCE_RETENTION_DAYS = 30


@router.get("/badge-queue", response_class=HTMLResponse)
def badge_queue(
    request: Request,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    pending = badges.list_pending(db)
    # eager-load applicant + region for display
    rows = []
    for app_obj in pending:
        applicant = db.get(User, app_obj.user_id)
        region = db.get(Region, app_obj.region_id)
        rows.append({"app": app_obj, "applicant": applicant, "region": region})
    return templates.TemplateResponse(
        request,
        "pages/admin_badge_queue.html",
        {"rows": rows, "current_user": current_user},
    )


@router.get("/badge-queue/{application_id}", response_class=HTMLResponse)
def badge_detail(
    request: Request,
    application_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    app_obj = db.get(BadgeApplication, application_id)
    if app_obj is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Application not found")
    applicant = db.get(User, app_obj.user_id)
    region = db.get(Region, app_obj.region_id)
    evidences = badges.evidences_for(db, app_obj.id)
    return templates.TemplateResponse(
        request,
        "pages/admin_badge_detail.html",
        {
            "app": app_obj,
            "applicant": applicant,
            "region": region,
            "evidences": evidences,
            "current_user": current_user,
        },
    )


@router.get("/badge-queue/{application_id}/evidence/{evidence_id}")
def download_evidence(
    application_id: int,
    evidence_id: int,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> FileResponse:
    e = db.get(BadgeEvidence, evidence_id)
    if e is None or e.application_id != application_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Evidence not found")
    p = Path(e.file_path)
    if not p.exists():
        raise HTTPException(status.HTTP_410_GONE, "Evidence file already cleaned up")
    return FileResponse(path=str(p), filename=p.name)


@router.post("/badge-queue/{application_id}/approve")
def approve_application(
    application_id: int,
    note: str | None = Form(default=None),
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    app_obj = db.get(BadgeApplication, application_id)
    if app_obj is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Application not found")
    try:
        badges.approve(db, application=app_obj, reviewer=admin, note=note)
    except ValueError as err:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(err)) from err

    # Schedule evidence cleanup 30 days out
    queue.enqueue(
        db,
        JobKind.EVIDENCE_CLEANUP,
        {"application_id": app_obj.id},
        run_after=datetime.now(UTC) + timedelta(days=EVIDENCE_RETENTION_DAYS),
    )
    db.commit()
    return RedirectResponse("/admin/badge-queue", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/badge-queue/{application_id}/reject")
def reject_application(
    application_id: int,
    note: str = Form(...),
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    app_obj = db.get(BadgeApplication, application_id)
    if app_obj is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Application not found")
    try:
        badges.reject(db, application=app_obj, reviewer=admin, note=note)
    except ValueError as err:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(err)) from err

    # Immediate evidence cleanup
    queue.enqueue(db, JobKind.EVIDENCE_CLEANUP, {"application_id": app_obj.id})
    db.commit()
    return RedirectResponse("/admin/badge-queue", status_code=status.HTTP_303_SEE_OTHER)
