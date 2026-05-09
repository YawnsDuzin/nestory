from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.deps import get_current_user, get_db
from app.models.user import User
from app.services import feed as feed_service
from app.templating import templates

router = APIRouter(tags=["pages"])


@router.get("/", response_class=HTMLResponse)
async def home(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_current_user),
) -> HTMLResponse:
    data = feed_service.home_data(db, current_user)
    return templates.TemplateResponse(
        request, "pages/home.html",
        {"data": data, "current_user": current_user},
    )


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


@router.get("/_offline", response_class=HTMLResponse)
def offline_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request, "pages/_offline.html", {"current_user": None}
    )
