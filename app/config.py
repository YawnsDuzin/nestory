from functools import lru_cache

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_env: str = "local"
    app_secret_key: str
    database_url: str

    kakao_client_id: str = ""
    kakao_client_secret: str = ""
    kakao_redirect_uri: str = "http://localhost:8000/auth/kakao/callback"

    admin_email: str = ""
    sentry_dsn: str = ""
    nestory_domain: str = "localhost:8000"
    session_cookie_secure: bool = False

    evidence_base_path: str = "./media-private/evidence"

    image_base_path: str = "./media"
    max_upload_size: int = 10 * 1024 * 1024  # 10MB
    image_max_dimension: int = 6000  # px
    anthropic_oauth_token: str = ""
    posthog_api_key: str = ""
    posthog_host: str = "https://us.i.posthog.com"

    @model_validator(mode="after")
    def _enforce_prod_cookie_security(self) -> "Settings":
        # prod 배포 시 session cookie hijack 방지 — Secure 플래그 미설정 사고 차단.
        if self.app_env == "production" and not self.session_cookie_secure:
            raise ValueError(
                "session_cookie_secure must be true when app_env=production "
                "(set SESSION_COOKIE_SECURE=true in .env)"
            )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
