import secrets

import httpx
from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import get_settings
from app.deps import get_db
from app.schemas.auth import LoginForm, SignupForm
from app.services.auth import (
    create_user_with_password,
    find_user_by_email,
    upsert_user_by_kakao_id,
    verify_password,
)
from app.services.kakao import build_authorize_url, exchange_code_for_profile

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/signup")
async def signup(
    request: Request,
    email: str = Form(...),
    username: str = Form(...),
    display_name: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    form = SignupForm(email=email, username=username, display_name=display_name, password=password)
    try:
        user = create_user_with_password(
            db,
            email=form.email,
            username=form.username,
            display_name=form.display_name,
            password=form.password,
        )
        db.commit()
    except IntegrityError as err:
        db.rollback()
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "가입에 실패했습니다. 다른 이메일/아이디로 시도해주세요.",
        ) from err

    request.session.clear()
    request.session["user_id"] = user.id
    return RedirectResponse("/", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/login")
async def login(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    form = LoginForm(email=email, password=password)
    user = find_user_by_email(db, form.email)
    if user is None or not verify_password(form.password, user.password_hash):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid credentials")

    request.session.clear()
    request.session["user_id"] = user.id
    return RedirectResponse("/", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/logout")
async def logout(request: Request) -> RedirectResponse:
    request.session.clear()
    return RedirectResponse("/", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/kakao/start")
async def kakao_start(request: Request) -> RedirectResponse:
    settings = get_settings()
    state = secrets.token_urlsafe(24)
    request.session["kakao_state"] = state
    url = build_authorize_url(
        client_id=settings.kakao_client_id,
        redirect_uri=settings.kakao_redirect_uri,
        state=state,
    )
    return RedirectResponse(url)


@router.get("/kakao/callback")
async def kakao_callback(
    request: Request,
    code: str,
    state: str,
    db: Session = Depends(get_db),
) -> RedirectResponse:
    settings = get_settings()
    expected = request.session.pop("kakao_state", None)
    if not expected or expected != state:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid state")

    async with httpx.AsyncClient(timeout=10.0) as http:
        profile = await exchange_code_for_profile(
            http,
            code=code,
            client_id=settings.kakao_client_id,
            client_secret=settings.kakao_client_secret,
            redirect_uri=settings.kakao_redirect_uri,
        )

    user = upsert_user_by_kakao_id(
        db, kakao_id=profile.kakao_id, email=profile.email, nickname=profile.nickname
    )
    db.commit()
    request.session.clear()
    request.session["user_id"] = user.id
    return RedirectResponse("/", status_code=status.HTTP_303_SEE_OTHER)
