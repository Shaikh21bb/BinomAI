from fastapi import Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from app.core.config import settings
import structlog

logger = structlog.get_logger(__name__)

def _cors_headers(request: Request) -> dict:
    """Ensure CORS headers are present even on error responses."""
    origin = request.headers.get("origin")
    if not origin or not settings.parsed_cors_origins:
        return {}
    if origin in settings.parsed_cors_origins or "*" in settings.parsed_cors_origins:
        return {
            "Access-Control-Allow-Origin": origin,
            "Access-Control-Allow-Credentials": "true",
            "Vary": "Origin",
        }
    return {}

async def custom_http_exception_handler(request: Request, exc: Exception, status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR, code: str = "INTERNAL_ERROR"):
    """
    Base exception handler formatting errors according to the API Specification.
    """
    message = str(exc)
    logger.error(
        "http_exception",
        path=request.url.path,
        method=request.method,
        status_code=status_code,
        error_code=code,
        error_message=message
    )
    
    return JSONResponse(
        status_code=status_code,
        content={
            "success": False,
            "error": {
                "code": code,
                "message": message,
                "details": []
            },
            "meta": {}
        },
        headers=_cors_headers(request)
    )

async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """
    Handles standard HTTP exceptions (e.g. 404, 401) and formats them.
    Dict details (e.g. {"code": "...", "message": "..."}) are passed through as-is.
    """
    logger.warning(
        "http_error",
        path=request.url.path,
        method=request.method,
        status_code=exc.status_code,
        detail=exc.detail
    )

    detail = exc.detail
    error_block = {
        "code": f"HTTP_{exc.status_code}",
        "message": str(detail),
        "details": [],
    }
    if isinstance(detail, dict):
        custom = {**detail}
        if "message" in custom and isinstance(custom["message"], str):
            error_block["message"] = custom["message"]
        error_block.update({k: v for k, v in custom.items() if k != "message"})

    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error": error_block,
            "meta": {}
        },
        headers=_cors_headers(request)
    )

async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """
    Handles Pydantic validation errors and formats them into the standard error schema.
    """
    details = exc.errors()
    logger.warning(
        "validation_error",
        path=request.url.path,
        method=request.method,
        details=details
    )
    
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "success": False,
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "Request validation failed.",
                "details": details
            },
            "meta": {}
        },
        headers=_cors_headers(request)
    )
