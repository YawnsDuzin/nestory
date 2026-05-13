from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.deps import get_db, require_user
from app.models import Region, User
from app.models._enums import BadgeRequestedLevel, EvidenceType
from app.services import badges, evidence_storage, profile
from app.services import images as images_service
from app.services import regions as regions_service
from app.services.profile import (
    AvatarOwnershipError,
    PasswordChangeNotAllowed,
    ProfileError,
    UsernameTakenError,
    UsernameThrottledError,
)
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


@router.get("/profile", response_class=HTMLResponse)
def profile_edit_page(
    request: Request,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    regions = regions_service.list_all_for_dropdown(db)
    return templates.TemplateResponse(
        request,
        "pages/me/profile/edit.html",
        {"current_user": user, "regions": regions},
    )


@router.get("/profile/username", response_class=HTMLResponse)
def profile_username_page(
    request: Request,
    user: User = Depends(require_user),
) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "pages/me/profile/username.html",
        {"current_user": user},
    )


@router.get("/profile/password", response_class=HTMLResponse)
def profile_password_page(
    request: Request,
    user: User = Depends(require_user),
) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "pages/me/profile/password.html",
        {"current_user": user},
    )


@router.post("/profile")
def profile_save(
    request: Request,
    display_name: Annotated[str, Form()],
    bio: Annotated[str, Form()] = "",
    primary_region_id: Annotated[str, Form()] = "",
    notify_email_enabled: Annotated[str, Form()] = "",
    notify_kakao_enabled: Annotated[str, Form()] = "",
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    region_id_int: int | None = None
    if primary_region_id.strip():
        try:
            region_id_int = int(primary_region_id)
        except ValueError:
            request.session["flash"] = "유효하지 않은 지역"
            return RedirectResponse("/me/profile", status_code=status.HTTP_303_SEE_OTHER)
    try:
        profile.update_profile_basic(
            db, user,
            display_name=display_name,
            bio=bio if bio.strip() else None,
            primary_region_id=region_id_int,
            notify_email_enabled=bool(notify_email_enabled),
            notify_kakao_enabled=bool(notify_kakao_enabled),
        )
        db.commit()
    except ProfileError as e:
        request.session["flash"] = str(e)
        return RedirectResponse("/me/profile", status_code=status.HTTP_303_SEE_OTHER)
    request.session["flash"] = "저장되었습니다"
    return RedirectResponse("/me/profile", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/profile/avatar")
async def profile_avatar_upload(
    request: Request,
    image: Annotated[UploadFile, File()],
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    try:
        img = images_service.upload_image(db, user, image)
        profile.set_avatar(db, user, img)
        db.commit()
    except HTTPException:
        # images_service가 던지는 HTTPException은 그대로 raise — 글로벌 핸들러
        db.rollback()
        raise
    except (AvatarOwnershipError, ProfileError) as e:
        db.rollback()
        request.session["flash"] = str(e)
        return RedirectResponse("/me/profile", status_code=status.HTTP_303_SEE_OTHER)
    request.session["flash"] = "사진이 변경되었습니다"
    return RedirectResponse("/me/profile", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/profile/avatar/delete")
def profile_avatar_delete(
    request: Request,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    profile.clear_avatar(db, user)
    db.commit()
    request.session["flash"] = "사진이 제거되었습니다"
    return RedirectResponse("/me/profile", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/profile/username")
def profile_username_change(
    request: Request,
    new_username: Annotated[str, Form()],
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    try:
        profile.change_username(db, user, new_username=new_username)
        db.commit()
    except UsernameThrottledError as e:
        request.session["flash"] = f"사용자명 변경은 {e.days_remaining}일 후 가능합니다"
        return RedirectResponse("/me/profile/username", status_code=status.HTTP_303_SEE_OTHER)
    except UsernameTakenError:
        request.session["flash"] = "이미 사용 중인 사용자명입니다"
        return RedirectResponse("/me/profile/username", status_code=status.HTTP_303_SEE_OTHER)
    except ProfileError as e:
        request.session["flash"] = str(e)
        return RedirectResponse("/me/profile/username", status_code=status.HTTP_303_SEE_OTHER)
    request.session["flash"] = "사용자명이 변경되었습니다"
    return RedirectResponse("/me/profile", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/profile/password")
def profile_password_change(
    request: Request,
    current_password: Annotated[str, Form()],
    new_password: Annotated[str, Form()],
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    try:
        profile.change_password(
            db, user,
            current_password=current_password,
            new_password=new_password,
        )
        db.commit()
    except PasswordChangeNotAllowed:
        # 카카오 가입자 — UI에서 폼 미노출이지만 직접 POST 시도 방어
        raise HTTPException(status.HTTP_403_FORBIDDEN, "카카오 계정은 비밀번호 변경 불가") from None
    except ProfileError as e:
        request.session["flash"] = str(e)
        return RedirectResponse("/me/profile/password", status_code=status.HTTP_303_SEE_OTHER)
    request.session["flash"] = "비밀번호가 변경되었습니다"
    return RedirectResponse("/me/profile", status_code=status.HTTP_303_SEE_OTHER)
