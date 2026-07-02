"""FastAPI application entrypoint for AutoMind AI Platform."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.admin import router as admin_router
from app.api.auth import router as auth_router
from app.api.billing import router as billing_router
from app.api.dashboard import router as dashboard_router
from app.api.health import router as health_router
from app.api.projects import router as projects_router
from app.api.tours import router as tours_router
from app.api.projects import router as projects_router
from app.api.tours import router as tours_router
from app.api.websocket import router as websocket_router
from app.core.config import settings
from app.core.exceptions import register_exception_handlers
from app.core.logging import setup_logging
from app.core.middleware import RequestIdMiddleware
from app.services.redis_cache import close_redis, init_redis


@asynccontextmanager
async def lifespan(application: FastAPI):
    """Manage application startup and shutdown lifecycle."""
    # Startup
    await init_redis()
    yield
    # Shutdown
    await close_redis()


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    setup_logging(level="DEBUG" if settings.debug else "INFO")

    application = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        docs_url="/docs" if settings.debug else None,
        redoc_url="/redoc" if settings.debug else None,
        lifespan=lifespan,
    )

    # Middleware (order matters — outermost first)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    application.add_middleware(RequestIdMiddleware)

    # Exception handlers
    register_exception_handlers(application)

    # Routers
    application.include_router(health_router)
    application.include_router(auth_router, prefix="/api/v1/auth", tags=["auth"])
    application.include_router(admin_router, prefix="/api/v1/admin", tags=["admin"])
    application.include_router(billing_router, prefix="/api/v1/billing", tags=["billing"])
    application.include_router(dashboard_router, prefix="/api/v1/dashboard", tags=["dashboard"])
    application.include_router(projects_router, prefix="/api/v1/projects", tags=["projects"])
    application.include_router(tours_router, prefix="/api/v1/tours", tags=["tours"])
    application.include_router(websocket_router, prefix="/ws", tags=["websocket"])

    return application


app = create_app()
