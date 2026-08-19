from __future__ import annotations

import os
from dataclasses import asdict
from typing import Any

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

app = FastAPI(title="Ama Runtime API", version="0.1.0")


class RunRequest(BaseModel):
    command: str = Field(min_length=1)
    arc: str = "Aster Hollow / At the Threshold"
    mode: str = "PREVIEW"


class CommitRequest(BaseModel):
    transaction_key: str = Field(min_length=1)
    capability_token: str = Field(min_length=1)


@app.get("/health")
def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "service": "ama-runtime",
        "version": "0.1.0",
        "persistence_enabled": os.getenv("AMA_PERSISTENCE_ENABLED", "false").lower() == "true",
    }


@app.post("/v1/run")
def run_preview(request: RunRequest) -> dict[str, Any]:
    # Public transport contract only. The hosted runtime wiring is intentionally
    # fail-closed until its Airtable/model adapters are configured in environment.
    return {
        "status": "READY_FOR_RUNTIME_WIRING",
        "mode": "PREVIEW",
        "arc": request.arc,
        "command": request.command,
        "persistence_authorized": False,
        "message": "Ama API is reachable; live BLOOM runtime adapters are not yet enabled on this host.",
    }


@app.post("/v1/commit")
def commit(
    request: CommitRequest,
    x_ama_api_key: str | None = Header(default=None),
) -> dict[str, Any]:
    expected = os.getenv("AMA_API_KEY")
    if not expected or x_ama_api_key != expected:
        raise HTTPException(status_code=401, detail="Unauthorized")
    if os.getenv("AMA_PERSISTENCE_ENABLED", "false").lower() != "true":
        raise HTTPException(status_code=423, detail="Live persistence is disabled")
    if not request.capability_token.startswith("AMA-CAP::"):
        raise HTTPException(status_code=403, detail="Invalid capability token")
    raise HTTPException(status_code=501, detail="Canonical live commit adapter not enabled on this deployment yet")
