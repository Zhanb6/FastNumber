"""Admin authentication: bcrypt password hash, JWT session cookie."""

from datetime import timedelta

import bcrypt
import jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_config
from app.models import Admin
from app.util import utcnow

COOKIE_NAME = "admin_session"
SESSION_TTL = timedelta(hours=12)
JWT_ALG = "HS256"


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        return False


async def upsert_admin_from_env(session: AsyncSession) -> None:
    """Create/update the admin row from ADMIN_LOGIN/ADMIN_PASSWORD. Does not commit."""
    cfg = get_config()
    admin = (
        await session.execute(select(Admin).where(Admin.login == cfg.admin_login))
    ).scalar_one_or_none()
    if admin is None:
        session.add(Admin(login=cfg.admin_login, password_hash=hash_password(cfg.admin_password)))
    elif not verify_password(cfg.admin_password, admin.password_hash):
        admin.password_hash = hash_password(cfg.admin_password)


async def authenticate(session: AsyncSession, login: str, password: str) -> Admin | None:
    admin = (await session.execute(select(Admin).where(Admin.login == login))).scalar_one_or_none()
    if admin is None or not verify_password(password, admin.password_hash):
        return None
    return admin


def create_session_token(login: str) -> str:
    now = utcnow()
    payload = {"sub": login, "iat": int(now.timestamp()), "exp": now + SESSION_TTL}
    return jwt.encode(payload, get_config().secret_key, algorithm=JWT_ALG)


def decode_session_token(token: str | None) -> str | None:
    """Return the admin login for a valid token, else None."""
    if not token:
        return None
    try:
        payload = jwt.decode(token, get_config().secret_key, algorithms=[JWT_ALG])
    except jwt.PyJWTError:
        return None
    sub = payload.get("sub")
    return sub if isinstance(sub, str) and sub else None
