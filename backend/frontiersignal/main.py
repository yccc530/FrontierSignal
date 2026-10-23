from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.exc import SQLAlchemyError
from starlette.middleware.trustedhost import TrustedHostMiddleware

from .analysis import seed_categories
from .api import router
from .config import PROJECT_ROOT, Settings, settings
from .db import Database
from .discovery_api import router as discovery_router
from .management_api import router as management_router
from .settings_api import router as settings_router
from .storage import seed_sources
from .tasks import TaskManager


def create_app(config: Settings = settings, db: Database | None = None):
    database = db or Database(config)
    manager = TaskManager(database, config)

    @asynccontextmanager
    async def lifespan(app):
        try:
            await manager.start()
            async with database.sessions() as session:
                await seed_sources(session)
                await seed_categories(session)
            yield
        finally:
            await manager.stop()
            await database.engine.dispose()

    app = FastAPI(title="FrontierSignal", version="0.1.0", lifespan=lifespan)
    app.state.db, app.state.tasks, app.state.settings = database, manager, config

    @app.exception_handler(SQLAlchemyError)
    async def database_error(request, exc):
        return JSONResponse(
            {"detail": "数据库暂不可用，请检查 PostgreSQL 并重启后端"}, status_code=503
        )

    app.add_middleware(
        TrustedHostMiddleware, allowed_hosts=["localhost", "127.0.0.1", "testserver"]
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.allowed_origins,
        allow_methods=["GET", "POST", "PATCH"],
        allow_headers=["Content-Type", "X-FrontierSignal"],
    )

    @app.middleware("http")
    async def local_boundary(request: Request, call_next):
        origin = request.headers.get("origin")
        if origin and origin not in config.allowed_origins:
            return JSONResponse({"detail": "Origin not allowed"}, status_code=403)
        if request.method not in {"GET", "HEAD", "OPTIONS"}:
            if request.headers.get("X-FrontierSignal") != "1":
                return JSONResponse(
                    {"detail": "Management request header required"}, status_code=403
                )
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Frame-Options"] = "DENY"
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        return response

    app.include_router(router)
    app.include_router(settings_router)
    app.include_router(management_router)
    app.include_router(discovery_router)
    dist = PROJECT_ROOT / "frontend" / "dist"
    if dist.exists():
        app.mount("/", StaticFiles(directory=dist, html=True), name="workbench")
    return app


app = create_app()
