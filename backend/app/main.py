"""FastAPI application: routers, error format, CORS, lifespan (startup + realtime)."""

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api import admin, live, public
from app.config import get_config
from app.db import async_session, engine
from app.errors import ApiError
from app.realtime.listener import PgListener
from app.realtime.manager import manager
from app.startup import run_startup
from app.util import now_ms

log = logging.getLogger("app")
PING_INTERVAL_S = 15

HTTP_CODES = {
    400: "BAD_REQUEST",
    401: "UNAUTHORIZED",
    403: "FORBIDDEN",
    404: "NOT_FOUND",
    405: "METHOD_NOT_ALLOWED",
    409: "CONFLICT",
    413: "PAYLOAD_TOO_LARGE",
    415: "UNSUPPORTED_MEDIA_TYPE",
    422: "VALIDATION_ERROR",
    429: "RATE_LIMITED",
}


async def _ping_loop() -> None:
    while True:
        await asyncio.sleep(PING_INTERVAL_S)
        await manager.broadcast({"type": "ping", "server_time": now_ms()})


@asynccontextmanager
async def lifespan(app: FastAPI):
    logging.basicConfig(level=logging.INFO)
    async with async_session() as session:
        await run_startup(session)
    listener = PgListener(manager, get_config().asyncpg_dsn)
    await listener.start()
    ping_task = asyncio.create_task(_ping_loop(), name="ws-ping")
    app.state.listener = listener
    try:
        yield
    finally:
        ping_task.cancel()
        await listener.stop()
        await engine.dispose()


def create_app() -> FastAPI:
    cfg = get_config()
    app = FastAPI(title="KTF Live Draw API", version="1.0.0", lifespan=lifespan, docs_url=None)

    if cfg.allowed_origins_list:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=cfg.allowed_origins_list,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    app.include_router(public.router)
    app.include_router(live.router)
    app.include_router(admin.auth_router)
    app.include_router(admin.router)

    @app.exception_handler(ApiError)
    async def api_error_handler(_: Request, exc: ApiError) -> JSONResponse:
        return JSONResponse(status_code=exc.status, content=exc.to_body())

    @app.exception_handler(RequestValidationError)
    async def validation_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
        fields: dict[str, str] = {}
        for err in exc.errors():
            loc = [str(p) for p in err.get("loc", ()) if p not in ("body", "query", "path")]
            fields.setdefault(".".join(loc) or "body", err.get("msg", "invalid"))
        body = ApiError(422, "VALIDATION_ERROR", "Validation failed", {"fields": fields}).to_body()
        return JSONResponse(status_code=422, content=body)

    @app.exception_handler(StarletteHTTPException)
    async def http_error_handler(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = HTTP_CODES.get(exc.status_code, "HTTP_ERROR")
        message = exc.detail if isinstance(exc.detail, str) else code
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": code, "message": message}},
            headers=getattr(exc, "headers", None),
        )

    @app.exception_handler(Exception)
    async def unhandled_handler(_: Request, exc: Exception) -> JSONResponse:
        log.exception("unhandled error: %r", exc)
        return JSONResponse(
            status_code=500,
            content={"error": {"code": "INTERNAL_ERROR", "message": "Internal server error"}},
        )

    return app


app = create_app()
