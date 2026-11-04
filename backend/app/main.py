from contextlib import asynccontextmanager

import redis
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .config import Settings, get_settings
from .database import create_session_factory
from .routers import auth, game


def create_app(settings: Settings | None = None) -> FastAPI:
    app_settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        yield
        app.state.redis.close()

    app = FastAPI(
        title="Crypto Go API",
        version="1.0.0",
        docs_url="/api/docs" if app_settings.app_env != "production" else None,
        redoc_url=None,
        lifespan=lifespan,
    )
    app.state.settings = app_settings
    app.state.session_factory = create_session_factory(app_settings.database_url)
    app.state.redis = redis.Redis.from_url(app_settings.redis_url, socket_timeout=2)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=app_settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type", "Idempotency-Key"],
    )

    @app.middleware("http")
    async def validate_mutation_origin(request: Request, call_next):
        if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
            origin = request.headers.get("origin")
            if origin and origin not in app_settings.allowed_origins:
                return JSONResponse(status_code=403, content={"detail": "Origen no permitido."})
        return await call_next(request)

    @app.get("/health/live", include_in_schema=False)
    def root_liveness():
        return {"status": "ok"}

    app.include_router(auth.router, prefix="/api/v1")
    app.include_router(game.router, prefix="/api/v1")
    return app


app = create_app()
