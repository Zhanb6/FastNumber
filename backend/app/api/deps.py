"""Request-level dependencies: client IP, admin session, CSRF, draw-screen key."""

from urllib.parse import urlparse

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_config
from app.db import get_session
from app.errors import ApiError
from app.services.auth import COOKIE_NAME, decode_session_token

MUTATING = {"POST", "PUT", "PATCH", "DELETE"}


def client_ip(request: Request) -> str | None:
    """Real client IP, counting X-Forwarded-For from the right.

    Every proxy appends the peer it saw, so the last entry is the closest proxy
    and the client is `TRUSTED_PROXY_DEPTH` entries from the end. Entries to the
    left of that are supplied by the client and must never be trusted: taking
    the first one lets anyone forge the IP used for rate limiting and audit.
    """
    depth = max(1, get_config().trusted_proxy_depth)
    xff = request.headers.get("x-forwarded-for")
    if xff:
        parts = [p.strip() for p in xff.split(",") if p.strip()]
        if parts:
            return parts[-min(len(parts), depth)]
    real = request.headers.get("x-real-ip")
    if real:
        return real.strip()
    return request.client.host if request.client else None


def user_agent(request: Request) -> str | None:
    return request.headers.get("user-agent")


def admin_from_cookie(cookie: str | None) -> str | None:
    login = decode_session_token(cookie)
    if login is None or login != get_config().admin_login:
        return None
    return login


def require_admin(request: Request) -> str:
    login = admin_from_cookie(request.cookies.get(COOKIE_NAME))
    if login is None:
        raise ApiError(401, "UNAUTHORIZED", "Admin session required")
    return login


def origin_allowed(origin: str, host_header: str | None) -> bool:
    cfg = get_config()
    origin = origin.strip().rstrip("/").lower()
    parsed = urlparse(origin)
    if not parsed.scheme or not parsed.netloc:
        return False
    host = (host_header or "").strip().lower()
    if host and (parsed.netloc == host or parsed.hostname == host.split(":")[0]):
        return True
    if origin == cfg.public_origin:
        return True
    return origin in [o.lower() for o in cfg.allowed_origins_list]


def csrf_check(request: Request) -> None:
    if request.method not in MUTATING:
        return
    origin = request.headers.get("origin")
    if origin is None:
        return
    if not origin_allowed(origin, request.headers.get("host")):
        raise ApiError(403, "CSRF_ORIGIN_MISMATCH", "Origin header does not match host")


def live_access_ok(key: str | None, cookie: str | None) -> bool:
    cfg = get_config()
    if not cfg.draw_screen_key:
        return True
    if key is not None and key == cfg.draw_screen_key:
        return True
    return admin_from_cookie(cookie) is not None


def require_live_key(request: Request) -> None:
    if not live_access_ok(request.query_params.get("key"), request.cookies.get(COOKIE_NAME)):
        raise ApiError(403, "DRAW_KEY_REQUIRED", "Draw screen key required")


SessionDep = Depends(get_session)
AsyncSessionT = AsyncSession
