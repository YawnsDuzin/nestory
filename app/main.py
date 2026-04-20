from fastapi import FastAPI

from app.config import get_settings

settings = get_settings()

app = FastAPI(title="Nestory", debug=settings.app_env == "local")


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok", "env": settings.app_env}
