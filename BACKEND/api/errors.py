"""Consistent, request-correlated API error responses."""

import logging
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder

logger = logging.getLogger(__name__)


def _request_id(request: Request) -> str:
    return getattr(request.state, "request_id", None) or request.headers.get("x-request-id") or str(uuid4())


def _response(request: Request, status_code: int, code: str, detail, details=None, headers=None) -> JSONResponse:
    message = detail if isinstance(detail, str) else "Request could not be completed"
    request_id = _request_id(request)
    response_headers = dict(headers or {})
    response_headers["X-Request-ID"] = request_id
    return JSONResponse(
        status_code=status_code,
        content=jsonable_encoder({
            "detail": detail,
            "error": {"code": code, "message": message, "details": details},
            "request_id": request_id,
        }),
        headers=response_headers,
    )


def install_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        return _response(request, exc.status_code, f"http_{exc.status_code}", exc.detail, headers=exc.headers)

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        return _response(request, 422, "validation_error", "Request validation failed", exc.errors())

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        logger.error("Unhandled API error; request_id=%s", _request_id(request), exc_info=(type(exc), exc, exc.__traceback__))
        return _response(request, 500, "internal_error", "An unexpected server error occurred")
