from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from hmac import compare_digest

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.encoders import jsonable_encoder
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from bloom_engine.api.contracts import AmaRequestBuilder
from bloom_engine.api.models import CapabilityView, RuntimePreviewBody
from bloom_engine.api.observability import correlation_middleware
from bloom_engine.runtime.models import SceneRequest
from bloom_engine.runtime.runner import RuntimeRunner


API_VERSION = "AMA-BLOOM-API-v0.1"


@dataclass(frozen=True, slots=True)
class AmaApiServices:
    runner: RuntimeRunner
    request_builder: AmaRequestBuilder


def _assert_preview_only(request: SceneRequest) -> None:
    if request.realization != "PREVIEW":
        raise RuntimeError("Ama preview boundary produced a non-preview SceneRequest")
    if request.authorization_token is not None:
        raise RuntimeError("Ama preview boundary produced a write-capability token")
    for runtime_query in request.queries:
        if runtime_query.request.permission_mode != "READ":
            raise RuntimeError("Ama preview boundary produced a non-read sovereign query")


def _proxy_json(*, method: str, path: str, bearer_token: str, body: dict | None = None) -> dict:
    upstream = os.getenv("AMA_UPSTREAM_URL", "").rstrip("/")
    if not upstream:
        raise RuntimeError("AMA_UPSTREAM_URL is not configured")

    payload = None if body is None else json.dumps(body).encode("utf-8")
    request = urllib.request.Request(
        f"{upstream}{path}",
        data=payload,
        method=method,
        headers={
            "Authorization": f"Bearer {bearer_token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "BLOOM-Ama-Preview-Bridge/0.1",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=25) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise HTTPException(status_code=exc.code, detail=f"Upstream BLOOM rejected request: {detail}") from exc
    except urllib.error.URLError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Upstream BLOOM connection failed: {exc.reason}",
        ) from exc


def create_app(*, services: AmaApiServices, bearer_token: str) -> FastAPI:
    if len(bearer_token) < 24:
        raise ValueError("BLOOM API bearer token must be at least 24 characters")

    app = FastAPI(
        title="BLOOM / Ama Runtime API",
        version="0.1.0",
        description=(
            "Read/preview-only external boundary for Ama. Sovereign facts and "
            "write authority remain server-side."
        ),
    )
    app.middleware("http")(correlation_middleware)
    bearer = HTTPBearer(auto_error=False)

    def require_auth(
        credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    ) -> None:
        if credentials is None or credentials.scheme.lower() != "bearer":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing bearer credentials",
            )
        if not compare_digest(credentials.credentials, bearer_token):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid bearer credentials",
            )

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "service": "bloom-engine", "api_version": API_VERSION}

    @app.get(
        "/v1/capabilities",
        response_model=CapabilityView,
        dependencies=[Depends(require_auth)],
    )
    def capabilities() -> CapabilityView:
        if os.getenv("AMA_UPSTREAM_URL"):
            return CapabilityView(**_proxy_json(
                method="GET",
                path="/v1/capabilities",
                bearer_token=bearer_token,
            ))
        return CapabilityView(
            api_version=API_VERSION,
            runtime_preview=True,
            runtime_commit=False,
            persistence_live=False,
            raw_sovereign_query_api=False,
            client_may_supply_authoritative_evidence=False,
            model_may_mint_write_authority=False,
        )

    @app.post("/v1/runtime/preview", dependencies=[Depends(require_auth)])
    def runtime_preview(body: RuntimePreviewBody) -> dict:
        if os.getenv("AMA_UPSTREAM_URL"):
            return _proxy_json(
                method="POST",
                path="/v1/runtime/preview",
                bearer_token=bearer_token,
                body=body.model_dump(mode="json"),
            )

        try:
            request = services.request_builder.build_preview(body)
            _assert_preview_only(request)
            output = services.runner.run(request)
        except RuntimeError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Runtime safety boundary rejected request: {exc}",
            ) from exc

        return jsonable_encoder(
            {
                "api_version": API_VERSION,
                "status": output.status,
                "text": output.text,
                "trace": output.trace,
            }
        )

    return app
