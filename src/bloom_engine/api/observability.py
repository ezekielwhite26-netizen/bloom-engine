from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from uuid import uuid4

from fastapi import Request, Response


LOGGER = logging.getLogger("bloom_engine.api.access")
_REQUEST_ID_RE = re.compile(r"^[A-Za-z0-9._:-]{8,96}$")


@dataclass(frozen=True, slots=True)
class RequestAuditEvent:
    request_id: str
    method: str
    path: str
    status_code: int


def safe_request_id(candidate: str | None) -> str:
    """Accept only a bounded opaque correlation ID; otherwise mint one server-side."""
    if candidate and _REQUEST_ID_RE.fullmatch(candidate):
        return candidate
    return f"req_{uuid4().hex}"


def emit_access_event(event: RequestAuditEvent) -> None:
    """Log metadata only: never headers, bearer tokens, query strings, or bodies."""
    LOGGER.info(
        "ama_request request_id=%s method=%s path=%s status=%s",
        event.request_id,
        event.method,
        event.path,
        event.status_code,
    )


async def correlation_middleware(request: Request, call_next) -> Response:
    request_id = safe_request_id(request.headers.get("X-Request-ID"))
    request.state.request_id = request_id
    try:
        response = await call_next(request)
    except Exception:
        LOGGER.exception(
            "ama_request_failed request_id=%s method=%s path=%s",
            request_id,
            request.method,
            request.url.path,
        )
        raise

    response.headers["X-Request-ID"] = request_id
    emit_access_event(
        RequestAuditEvent(
            request_id=request_id,
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
        )
    )
    return response
