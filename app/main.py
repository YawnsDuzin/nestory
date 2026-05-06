from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app.config import get_settings
from app.logging_setup import configure_logging, init_sentry
from app.routers import auth as auth_router
from app.routers import me as me_router
from app.routers import pages as pages_router

settings = get_settings()
configure_logging(env=settings.app_env)
init_sentry(settings.sentry_dsn, settings.app_env)

BASE_DIR = Path(__file__).resolve().parent

app = FastAPI(title="Nestory", debug=settings.app_env == "local")

app.add_middleware(
    SessionMiddleware,
    secret_key=settings.app_secret_key,
    session_cookie="nestory_session",
    max_age=60 * 60 * 24 * 30,
    same_site="lax",
    https_only=settings.session_cookie_secure,
)
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
app.include_router(auth_router.router)
app.include_router(me_router.router)
app.include_router(pages_router.router)


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok", "env": settings.app_env}
