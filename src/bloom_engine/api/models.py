from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class CoreResolveBody(BaseModel):
    """Read-only sovereign query accepted from an external Ama client."""

    predicate: str = Field(min_length=1)
    subject_refs: list[str] = Field(default_factory=list)
    inputs: dict[str, Any] = Field(default_factory=dict)
    evidence: list[dict[str, Any]] = Field(default_factory=list)


class RuntimeQueryBody(BaseModel):
    predicate: str = Field(min_length=1)
    subject_refs: list[str] = Field(default_factory=list)
    inputs: dict[str, Any] = Field(default_factory=dict)
    evidence: list[dict[str, Any]] = Field(default_factory=list)
    required_for_request: bool = False
    fact_keys: list[str] = Field(default_factory=list)


class RuntimePreviewBody(BaseModel):
    """A bounded runtime request that can never carry write authority."""

    arc: str = Field(min_length=1)
    command: str = Field(min_length=1)
    queries: list[RuntimeQueryBody] = Field(default_factory=list)
    mode: Literal["DRY_RUN", "LIVE_PLAY"] = "DRY_RUN"
    protected_player_domains: list[str] = Field(default_factory=list)


class CapabilityView(BaseModel):
    api_version: str
    core_resolve: bool
    runtime_preview: bool
    runtime_commit: bool
    persistence_live: bool
    model_may_mint_write_authority: bool
