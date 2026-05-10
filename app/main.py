import uuid
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from slowapi.errors import RateLimitExceeded
from sqlalchemy import text
from starlette.middleware.sessions import SessionMiddleware

from app.config import get_settings
from app.db.session import SessionLocal
from app.logging_setup import configure_logging, init_sentry
from app.rate_limit import limiter
from app.routers import admin as admin_router
from app.routers import auth as auth_router
from app.routers import content as content_router
from app.routers import feed as feed_router
from app.routers import hub as hub_router
from app.routers import images as images_router
from app.routers import interactions as interactions_router
from app.routers import journey as journey_router
from app.routers import match as match_router
from app.routers import me as me_router
from app.routers import notifications as notifications_router
from app.routers import pages as pages_router
from app.routers import profile as profile_router
from app.routers import search as search_router
from app.services.analytics import _distinct_id
from app.services.kakao_inapp import is_kakao_inapp

settings = get_settings()
configure_logging(env=settings.app_env)
init_sentry(settings.sentry_dsn, settings.app_env)

BASE_DIR = Path(__file__).resolve().parent

app = FastAPI(title="Nestory", debug=settings.app_env == "local")
app.state.limiter = limiter


@app.exception_handler(RateLimitExceeded)
async def _rate_limit_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    return JSONResponse(
        {"detail": f"요청이 너무 많습니다. 잠시 후 다시 시도해주세요. ({exc.detail})"},
        status_code=429,
    )


# NOTE: middleware 등록 순서 — Starlette는 add_middleware/decorator 시 list의
# 0번 위치에 prepend하므로 "마지막에 등록"이 outermost가 됩니다.
# request 처리 순서: SessionMiddleware → analytics → kakao → routes
# 따라서 analytics가 request.session에 접근하려면 SessionMiddleware가
# outermost(마지막 등록)가 되어야 합니다.

@app.middleware("http")
async def kakao_inapp_middleware(request: Request, call_next):
    request.state.kakao_inapp = is_kakao_inapp(request)
    return await call_next(request)


@app.middleware("http")
async def analytics_distinct_id_middleware(request: Request, call_next):
    user_id = request.session.get("user_id")
    anon_id = request.session.get("posthog_anon_id")
    if user_id is None and anon_id is None:
        anon_id = f"anon-{uuid.uuid4()}"
        request.session["posthog_anon_id"] = anon_id
    request.state.distinct_id_hash = _distinct_id(user_id, anon_id)
    return await call_next(request)


# SessionMiddleware는 가장 마지막에 등록 — outermost가 되어야
# 위의 두 미들웨어가 request.session에 접근 가능.
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.app_secret_key,
    session_cookie="nestory_session",
    max_age=60 * 60 * 24 * 30,
    same_site="lax",
    https_only=settings.session_cookie_secure,
)


app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
app.include_router(admin_router.router)
app.include_router(auth_router.router)
app.include_router(content_router.router)
app.include_router(feed_router.router)
app.include_router(hub_router.router)
app.include_router(images_router.router)
app.include_router(interactions_router.router)
app.include_router(journey_router.router)
app.include_router(match_router.router)
app.include_router(me_router.router)
app.include_router(notifications_router.router)
app.include_router(pages_router.router)
app.include_router(profile_router.router)
app.include_router(search_router.router)


@app.get("/healthz")
async def healthz() -> JSONResponse:
    response: dict[str, str] = {"status": "ok", "env": settings.app_env}
    status_code = 200
    try:
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
        response["db"] = "ok"
    except Exception:  # noqa: BLE001 — healthz는 어떤 DB 오류든 degraded 표기
        response["status"] = "degraded"
        response["db"] = "error"
        status_code = 503
    return JSONResponse(response, status_code=status_code)
