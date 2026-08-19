from __future__ import annotations

from copy import deepcopy
from urllib.parse import urlparse

from fastapi import FastAPI


ACTION_PATHS = frozenset({"/v1/capabilities", "/v1/runtime/preview"})
ACTION_OPERATION_IDS = {
    ("/v1/capabilities", "get"): "getBloomCapabilities",
    ("/v1/runtime/preview", "post"): "previewBloomRuntime",
}
FORBIDDEN_TOKENS = (
    "authorization_token",
    "capability_token",
    "evidence",
    "permission_mode",
    "persistence",
    "commit",
    "write",
)


def _assert_https_server(server_url: str) -> None:
    parsed = urlparse(server_url)
    if parsed.scheme != "https" or not parsed.netloc:
        raise ValueError("Custom GPT Action server URL must be an absolute HTTPS URL")
    if parsed.username or parsed.password:
        raise ValueError("Custom GPT Action server URL must not embed credentials")


def build_custom_gpt_action_schema(app: FastAPI, *, server_url: str) -> dict:
    """Return a deliberately narrower OpenAPI schema for Ama Custom GPT Actions.

    The hosted FastAPI app may contain operational endpoints such as /health.
    This exporter whitelists only the reviewed read/preview action surface and
    refuses to publish a schema if forbidden authority-bearing terms appear in
    the exposed request contract.
    """

    _assert_https_server(server_url)
    source = deepcopy(app.openapi())
    source_paths = source.get("paths", {})

    missing = ACTION_PATHS.difference(source_paths)
    if missing:
        raise RuntimeError(f"required Ama Action path missing from app: {sorted(missing)}")

    exposed_paths: dict = {}
    for path in sorted(ACTION_PATHS):
        item = deepcopy(source_paths[path])
        for method, operation in list(item.items()):
            if method.lower() not in {"get", "post", "put", "patch", "delete", "options", "head"}:
                continue
            key = (path, method.lower())
            if key not in ACTION_OPERATION_IDS:
                del item[method]
                continue
            operation["operationId"] = ACTION_OPERATION_IDS[key]
            operation["x-openai-isConsequential"] = False
        exposed_paths[path] = item

    schema = {
        "openapi": source.get("openapi", "3.1.0"),
        "info": {
            "title": "BLOOM / Ama Read-Only Actions",
            "version": "0.1.0",
            "description": (
                "Private Ama action surface for BLOOM capability inspection and "
                "read-only runtime preview. No persistence or canon mutation is exposed."
            ),
        },
        "servers": [{"url": server_url.rstrip("/")}],
        "paths": exposed_paths,
        "components": deepcopy(source.get("components", {})),
    }

    rendered = repr(schema).lower()
    for token in FORBIDDEN_TOKENS:
        if token in rendered:
            # persistence appears in the capability response by design, but it
            # must never appear as an input field or route. Inspect request-only
            # structures separately below instead of allowing it wholesale.
            if token == "persistence":
                continue
            raise RuntimeError(f"forbidden authority-bearing token exposed in Action schema: {token}")

    preview = schema["paths"]["/v1/runtime/preview"]["post"]
    request_body = repr(preview.get("requestBody", {})).lower()
    for token in FORBIDDEN_TOKENS:
        if token in request_body:
            raise RuntimeError(f"forbidden client input exposed in preview request schema: {token}")

    if any("commit" in path.lower() or "write" in path.lower() for path in schema["paths"]):
        raise RuntimeError("write-like path leaked into Custom GPT Action schema")

    return schema
