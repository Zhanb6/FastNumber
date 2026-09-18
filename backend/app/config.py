"""Application configuration from environment variables (pydantic-settings)."""

from functools import lru_cache
from urllib.parse import urlparse

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppConfig(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore", case_sensitive=False)

    database_url: str = "postgresql+asyncpg://eventdraw:eventdraw@localhost:5432/eventdraw"
    secret_key: str = "dev-secret-change-me"
    admin_login: str = "admin"
    admin_password: str = "admin"
    public_base_url: str = "http://localhost"
    draw_screen_key: str = ""
    cookie_secure: bool | None = None
    allowed_origins: str = ""

    # Event defaults (used on first run to populate the settings table)
    event_name: str = "Kazakhstan Travel Forum 2026"
    event_slug: str = "ktf-2026"
    event_timezone: str = "Asia/Almaty"
    start_number: int = 1000
    max_number: int = 2000
    on_max_reached: str = "continue"
    name_mode: str = "full"
    allow_previous_winners: bool = False
    registration_open: bool = True
    animation_duration_ms: int = 8000

    register_rate_limit_per_min: int = 30
    seed_demo: bool = False

    @field_validator("cookie_secure", "seed_demo", "allow_previous_winners", mode="before")
    @classmethod
    def _empty_bool_is_none(cls, v: object) -> object:
        if isinstance(v, str) and v.strip() == "":
            return None
        return v

    @field_validator("name_mode")
    @classmethod
    def _check_name_mode(cls, v: str) -> str:
        v = v.strip().lower()
        if v not in ("split", "full"):
            raise ValueError("NAME_MODE must be 'split' or 'full'")
        return v

    @field_validator("on_max_reached")
    @classmethod
    def _check_on_max(cls, v: str) -> str:
        v = v.strip().lower()
        if v not in ("continue", "close"):
            raise ValueError("ON_MAX_REACHED must be 'continue' or 'close'")
        return v

    @property
    def cookie_secure_effective(self) -> bool:
        if self.cookie_secure is not None:
            return self.cookie_secure
        return self.public_base_url.lower().startswith("https")

    @property
    def allowed_origins_list(self) -> list[str]:
        return [o.strip().rstrip("/") for o in self.allowed_origins.split(",") if o.strip()]

    @property
    def public_origin(self) -> str:
        p = urlparse(self.public_base_url)
        return f"{p.scheme}://{p.netloc}".lower()

    @property
    def asyncpg_dsn(self) -> str:
        """DSN for a raw asyncpg connection (LISTEN/NOTIFY)."""
        return self.database_url.replace("postgresql+asyncpg://", "postgresql://", 1)


@lru_cache
def get_config() -> AppConfig:
    return AppConfig()
