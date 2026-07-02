"""Custom exception classes and global exception handlers."""

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.logging import get_logger, request_id_ctx

logger = get_logger(__name__)


class AppException(Exception):
    """Base application exception."""

    def __init__(
        self,
        code: str,
        message: str,
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        details: list | None = None,
    ):
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or []
        super().__init__(message)


class NotFoundException(AppException):
    """Resource not found."""

    def __init__(self, message: str = "Resource not found", details: list | None = None):
        super().__init__(
            code="not_found",
            message=message,
            status_code=status.HTTP_404_NOT_FOUND,
            details=details,
        )


class ForbiddenException(AppException):
    """Access denied."""

    def __init__(self, message: str = "Access denied", details: list | None = None):
        super().__init__(
            code="forbidden",
            message=message,
            status_code=status.HTTP_403_FORBIDDEN,
            details=details,
        )


class ValidationException(AppException):
    """Validation error."""

    def __init__(self, message: str = "Validation error", details: list | None = None):
        super().__init__(
            code="validation_error",
            message=message,
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            details=details,
        )


def _error_response(
    code: str, message: str, details: list, status_code: int
) -> JSONResponse:
    """Build a standardized error response."""
    return JSONResponse(
        status_code=status_code,
        content={
            "error": {
                "code": code,
                "message": message,
                "details": details,
                "request_id": request_id_ctx.get(""),
            }
        },
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Register all global exception handlers on the FastAPI app."""

    @app.exception_handler(AppException)
    async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
        logger.warning(
            "app_exception",
            extra={"code": exc.code, "error_message": exc.message, "path": request.url.path},
        )
        return _error_response(exc.code, exc.message, exc.details, exc.status_code)

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        details = [
            {"field": ".".join(str(loc) for loc in err["loc"]), "message": err["msg"]}
            for err in exc.errors()
        ]
        logger.warning(
            "validation_error",
            extra={"path": request.url.path, "errors": details},
        )
        return _error_response(
            "validation_error", "Request validation failed", details, 422
        )

    @app.exception_handler(404)
    async def not_found_handler(request: Request, exc: Exception) -> JSONResponse:
        return _error_response(
            "not_found", f"Path {request.url.path} not found", [], 404
        )

    @app.exception_handler(500)
    async def internal_error_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.error(
            "unhandled_exception",
            extra={"path": request.url.path, "error": str(exc)},
            exc_info=True,
        )
        return _error_response(
            "internal_error", "An unexpected error occurred", [], 500
        )
