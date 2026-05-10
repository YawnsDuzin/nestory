from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.deps import get_db, require_user
from app.models import Region, User
from app.models._enums import BadgeRequestedLevel, EvidenceType
from app.services import badges, evidence_storage
from app.services import regions as regions_service
from app.templating import templates

router = APIRouter(prefix="/me", tags=["me"])


@router.get("/badge", response_class=HTMLResponse)
def badge_page(
    request: Request,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    pending = badges.get_user_pending_application(db, user.id)
    regions = regions_service.list_all_for_dropdown(db)
    return templates.TemplateResponse(
        request,
        "pages/me_badge.html",
        {"user": user, "current_user": user, "pending": pending, "regions": regions},
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

    if badges.get_user_pending_application(db, user.id) is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Pending application exists")

    badges.submit_application(
        db,
        user=user,
        requested_level=BadgeRequestedLevel.REGION_VERIFIED,
        region_id=region.id,
    )
    db.commit()
    return RedirectResponse("/me/badge", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/badge/resident", response_class=HTMLResponse)
def resident_form(
    request: Request,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    regions = regions_service.list_all_for_dropdown(db)
    return templates.TemplateResponse(
        request,
        "pages/me_badge_resident.html",
        {
            "user": user,
            "current_user": user,
            "regions": regions,
            "evidence_types": list(EvidenceType),
        },
    )


@router.post("/badge/resident")
async def apply_resident(
    region_id: Annotated[int, Form()],
    utility_bill: Annotated[UploadFile | None, File()] = None,
    contract: Annotated[UploadFile | None, File()] = None,
    building_cert: Annotated[UploadFile | None, File()] = None,
    geo_selfie: Annotated[UploadFile | None, File()] = None,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    uploads: list[tuple[EvidenceType, UploadFile]] = []
    for kind, upload in (
        (EvidenceType.UTILITY_BILL, utility_bill),
        (EvidenceType.CONTRACT, contract),
        (EvidenceType.BUILDING_CERT, building_cert),
        (EvidenceType.GEO_SELFIE, geo_selfie),
    ):
        if upload is not None and upload.filename:
            uploads.append((kind, upload))

    if not uploads:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "At least one evidence file required")

    region = db.get(Region, region_id)
    if region is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid region")

    if badges.get_user_pending_application(db, user.id) is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Pending application exists")

    application = badges.submit_application(
        db,
        user=user,
        requested_level=BadgeRequestedLevel.RESIDENT,
        region_id=region.id,
    )

    now = datetime.now(UTC)
    try:
        for kind, upload in uploads:
            stored_path = evidence_storage.store(
                application_id=application.id,
                filename=upload.filename or "evidence",
                stream=upload.file,
                now_year=now.year,
                now_month=now.month,
            )
            badges.attach_evidence(
                db,
                application=application,
                evidence_type=kind,
                file_path=stored_path,
            )
    except ValueError as err:
        # Rollback both DB & files
        db.rollback()
        evidence_storage.delete_all_for_application(application.id)
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(err)) from err

    db.commit()
    return RedirectResponse("/me/badge", status_code=status.HTTP_303_SEE_OTHER)
