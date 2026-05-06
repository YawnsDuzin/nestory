from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse

from app.deps import get_current_user
from app.models.user import User
from app.templating import templates

router = APIRouter(tags=["pages"])


@router.get("/", response_class=HTMLResponse)
async def home(
    request: Request, current_user: User | None = Depends(get_current_user)
) -> HTMLResponse:
    return templates.TemplateResponse(request, "pages/home.html", {"current_user": current_user})


@router.get("/auth/login", response_class=HTMLResponse)
async def login_page(
    request: Request, current_user: User | None = Depends(get_current_user)
) -> HTMLResponse:
    return templates.TemplateResponse(request, "pages/login.html", {"current_user": current_user})


@router.get("/auth/signup", response_class=HTMLResponse)
async def signup_page(
    request: Request, current_user: User | None = Depends(get_current_user)
) -> HTMLResponse:
    return templates.TemplateResponse(request, "pages/signup.html", {"current_user": current_user})
