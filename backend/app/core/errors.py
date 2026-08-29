from collections.abc import Awaitable, Callable, Mapping
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict
from starlette.background import BackgroundTask
from starlette.responses import Response


class Utf8JSONResponse(JSONResponse):
    def __init__(
        self,
        content: Any,
        status_code: int = 200,
        headers: Mapping[str, str] | None = None,
        media_type: str | None = None,
        background: BackgroundTask | None = None,
    ) -> None:
        super().__init__(
            content=content,
            status_code=status_code,
            headers=headers,
            media_type=media_type or "application/json; charset=utf-8",
            background=background,
        )


class ErrorBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    message: str
    details: dict[str, Any]
    request_id: str


class ErrorResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    error: ErrorBody


ERROR_DESCRIPTIONS = {
    400: "Invalid state or malformed request",
    401: "Missing, invalid, or expired authentication",
    403: "Authenticated user cannot perform this operation",
    404: "Resource not found",
    409: "Version, idempotency, or resource conflict",
    413: "Uploaded content is too large",
    415: "Unsupported media type",
    422: "Request validation failed",
    429: "Rate limit exceeded",
    500: "Unexpected server error",
    503: "Required provider is unavailable",
}


def error_responses(*status_codes: int) -> dict[int, dict[str, object]]:
    return {
        code: {"model": ErrorResponse, "description": ERROR_DESCRIPTIONS[code]}
        for code in status_codes
    }


class ApiError(Exception):
    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        details: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details or {}
        self.headers = headers


def _request_id(request: Request) -> str:
    return getattr(request.state, "request_id", f"req_{uuid4().hex[:12]}")


def _response(request: Request, error: ApiError) -> JSONResponse:
    return Utf8JSONResponse(
        status_code=error.status_code,
        headers=error.headers,
        content={
            "error": {
                "code": error.code,
                "message": error.message,
                "details": error.details,
                "request_id": _request_id(request),
            }
        },
    )


def install_error_handlers(application: FastAPI) -> None:
    @application.middleware("http")
    async def add_request_id(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        request.state.request_id = request.headers.get("X-Request-ID") or f"req_{uuid4().hex[:12]}"
        response = await call_next(request)
        response.headers["X-Request-ID"] = request.state.request_id
        return response

    @application.exception_handler(ApiError)
    async def handle_api_error(request: Request, error: ApiError) -> JSONResponse:
        return _response(request, error)

    @application.exception_handler(RequestValidationError)
    async def handle_validation_error(
        request: Request, error: RequestValidationError
    ) -> JSONResponse:
        fields: dict[str, str] = {}
        for item in error.errors():
            location = [
                str(part) for part in item["loc"] if part not in {"body", "query", "header"}
            ]
            fields[".".join(location) or "request"] = item["msg"]
        return _response(
            request,
            ApiError(
                422,
                "VALIDATION_ERROR",
                "Some fields need attention.",
                {"fields": fields},
            ),
        )

    @application.exception_handler(HTTPException)
    async def handle_http_error(request: Request, error: HTTPException) -> JSONResponse:
        code = "NOT_FOUND" if error.status_code == 404 else "INVALID_STATE"
        if error.status_code == 401:
            code = "UNAUTHORIZED"
        elif error.status_code == 403:
            code = "FORBIDDEN"
        return _response(
            request,
            ApiError(error.status_code, code, str(error.detail), headers=error.headers),
        )

    @application.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, error: Exception) -> JSONResponse:
        # The exception remains available to server logging without exposing internals to clients.
        return _response(
            request,
            ApiError(500, "INTERNAL_ERROR", "An unexpected error occurred."),
        )
