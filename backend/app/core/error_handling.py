"""Global exception handlers and request-id middleware for FastAPI."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Any, Final, cast
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError, ResponseValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.responses import Response

if TYPE_CHECKING:
    from starlette.types import ASGIApp, Message, Receive, Scope, Send

logger = logging.getLogger(__name__)

REQUEST_ID_HEADER: Final[str] = "X-Request-Id"

ExceptionHandler = Callable[[Request, Exception], Response | Awaitable[Response]]


class RequestIdMiddleware:
    """ASGI middleware that ensures every request has a request-id."""

    def __init__(self, app: ASGIApp, *, header_name: str = REQUEST_ID_HEADER) -> None:
        """Initialize middleware with app instance and header name."""
        self._app = app
        self._header_name = header_name
        self._header_name_bytes = header_name.lower().encode("latin-1")

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Inject request-id into request state and response headers."""
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return

        request_id = self._get_or_create_request_id(scope)

        async def send_with_request_id(message: Message) -> None:
            if message["type"] == "http.response.start":
                # Starlette uses `list[tuple[bytes, bytes]]` here.
                headers: list[tuple[bytes, bytes]] = message.setdefault("headers", [])
                if not any(
                    key.lower() == self._header_name_bytes for key, _ in headers
                ):
                    request_id_bytes = request_id.encode("latin-1")
                    headers.append((self._header_name_bytes, request_id_bytes))
            await send(message)

        await self._app(scope, receive, send_with_request_id)

    def _get_or_create_request_id(self, scope: Scope) -> str:
        # Accept a client-provided request id if present.
        request_id: str | None = None
        for key, value in scope.get("headers", []):
            if key.lower() == self._header_name_bytes:
                candidate = value.decode("latin-1").strip()
                if candidate:
                    request_id = candidate
                break

        if request_id is None:
            request_id = uuid4().hex

        # `Request.state` is backed by `scope["state"]`.
        state = scope.setdefault("state", {})
        state["request_id"] = request_id
        return request_id


def install_error_handling(app: FastAPI) -> None:
    """Install middleware and exception handlers on the FastAPI app."""
    # Important: add request-id middleware last so it's the outermost middleware.
    # This ensures it still runs even if another middleware
    # (e.g. CORS preflight) returns early.
    app.add_middleware(RequestIdMiddleware)

    app.add_exception_handler(
        RequestValidationError,
        cast(ExceptionHandler, _request_validation_handler),
    )
    app.add_exception_handler(
        ResponseValidationError,
        cast(ExceptionHandler, _response_validation_handler),
    )
    app.add_exception_handler(
        StarletteHTTPException,
        cast(ExceptionHandler, _http_exception_handler),
    )
    app.add_exception_handler(Exception, _unhandled_exception_handler)


def _get_request_id(request: Request) -> str | None:
    request_id = getattr(request.state, "request_id", None)
    if isinstance(request_id, str) and request_id:
        return request_id
    return None


def _error_payload(*, detail: object, request_id: str | None) -> dict[str, object]:
    payload: dict[str, Any] = {"detail": detail}
    if request_id:
        payload["request_id"] = request_id
    return payload


async def _request_validation_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    # `RequestValidationError` is expected user input; don't log at ERROR.
    request_id = _get_request_id(request)
    return JSONResponse(
        status_code=422,
        content=_error_payload(detail=exc.errors(), request_id=request_id),
    )


async def _response_validation_handler(
    request: Request,
    exc: ResponseValidationError,
) -> JSONResponse:
    request_id = _get_request_id(request)
    logger.exception(
        "response_validation_error",
        extra={
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
            "errors": exc.errors(),
        },
    )
    return JSONResponse(
        status_code=500,
        content=_error_payload(detail="Internal Server Error", request_id=request_id),
    )


async def _http_exception_handler(
    request: Request,
    exc: StarletteHTTPException,
) -> JSONResponse:
    request_id = _get_request_id(request)
    return JSONResponse(
        status_code=exc.status_code,
        content=_error_payload(detail=exc.detail, request_id=request_id),
        headers=exc.headers,
    )


async def _unhandled_exception_handler(
    request: Request,
    _exc: Exception,
) -> JSONResponse:
    request_id = _get_request_id(request)
    logger.exception(
        "unhandled_exception",
        extra={
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
        },
    )
    return JSONResponse(
        status_code=500,
        content=_error_payload(detail="Internal Server Error", request_id=request_id),
        headers={REQUEST_ID_HEADER: request_id} if request_id else None,
    )
