from fastapi import FastAPI
from starlette.middleware.sessions import SessionMiddleware

from app.config import get_settings

settings = get_settings()

app = FastAPI(title="Nestory", debug=settings.app_env == "local")

app.add_middleware(
    SessionMiddleware,
    secret_key=settings.app_secret_key,
    session_cookie="nestory_session",
    max_age=60 * 60 * 24 * 30,
    same_site="lax",
    https_only=settings.session_cookie_secure,
)


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok", "env": settings.app_env}


from app.routers import auth as auth_router

app.include_router(auth_router.router)
