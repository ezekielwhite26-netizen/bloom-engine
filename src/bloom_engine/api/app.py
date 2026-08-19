from __future__ import annotations

from dataclasses import dataclass
from hmac import compare_digest

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.encoders import jsonable_encoder
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from bloom_engine.api.contracts import AmaRequestBuilder
from bloom_engine.api.models import CapabilityView, RuntimePreviewBody
from bloom_engine.runtime.models import SceneRequest
from bloom_engine.runtime.runner import RuntimeRunner


API_VERSION = "AMA-BLOOM-API-v0.1"


@dataclass(frozen=True, slots=True)
class AmaApiServices:
    runner: RuntimeRunner
    request_builder: AmaRequestBuilder


def _assert_preview_only(request: SceneRequest) -> None:
    """Fail closed if a server-side builder accidentally creates write authority."""

    if request.realization != "PREVIEW":
        raise RuntimeError("Ama preview boundary produced a non-preview SceneRequest")
    if request.authorization_token is not None:
        raise RuntimeError("Ama preview boundary produced a write-capability token")
    for runtime_query in request.queries:
        if runtime_query.request.permission_mode != "READ":
            raise RuntimeError("Ama preview boundary produced a non-read sovereign query")


def create_app(*, services: AmaApiServices, bearer_token: str) -> FastAPI:
    """Create the first hosted boundary for Ama.

    v0.1 is intentionally read/preview only. It does not expose raw sovereign
    resolver calls and it does not expose any persistence endpoint. Authorization
    for future writes must be minted by a non-model server-side policy layer.
    """

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
