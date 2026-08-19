from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class RuntimePreviewBody(BaseModel):
    """Untrusted client intent for a read-only BLOOM runtime preview.

    The external client may identify what it is asking about, but it may not
    supply sovereign facts, evidence, resolution statuses, query manifests, or
    write-capability tokens. A trusted server-side request builder owns that
    translation boundary.
    """

    model_config = ConfigDict(extra="forbid")

    arc: str = Field(min_length=1)
    command: str = Field(min_length=1)
    mode: Literal["DRY_RUN", "LIVE_PLAY"] = "DRY_RUN"
    requested_actor_ref: str | None = None
    requested_target_location_ref: str | None = None
    requested_object_ref: str | None = None
    visual_requested: bool = False


class CapabilityView(BaseModel):
    model_config = ConfigDict(extra="forbid")

    api_version: str
    runtime_preview: bool
    runtime_commit: bool
    persistence_live: bool
    raw_sovereign_query_api: bool
    client_may_supply_authoritative_evidence: bool
    model_may_mint_write_authority: bool
