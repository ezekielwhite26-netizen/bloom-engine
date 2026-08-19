from __future__ import annotations

import hashlib
from dataclasses import dataclass
from enum import Enum


class AmaActionClass(str, Enum):
    READ_ONLY = "READ_ONLY"
    PREVIEW_STATE_CHANGE = "PREVIEW_STATE_CHANGE"
    ORDINARY_LIVE_PLAY = "ORDINARY_LIVE_PLAY"
    PROTECTED_CREATIVE_DECISION = "PROTECTED_CREATIVE_DECISION"
    CANON_REVISION = "CANON_REVISION"
    DESTRUCTIVE = "DESTRUCTIVE"
    EXTERNAL_SIDE_EFFECT = "EXTERNAL_SIDE_EFFECT"


class AmaPermissionDecision(str, Enum):
    ALLOW = "ALLOW"
    PREVIEW_ONLY = "PREVIEW_ONLY"
    ASK = "ASK"
    DENY = "DENY"


@dataclass(frozen=True, slots=True)
class AmaIntent:
    mode: str
    project: str
    action_class: AmaActionClass
    command: str
    requested_commit: bool = False
    confidence: str = "MEDIUM"
    protected_domain: str | None = None


@dataclass(frozen=True, slots=True)
class AmaPermissionGrant:
    decision: AmaPermissionDecision
    action_class: AmaActionClass
    reason_code: str
    capability_token: str | None = None
    expires_after_run: bool = True


class PersonalAmaPolicyV03:
    """Port of Runtime v0.3's single-user authority policy.

    Intelligence is not authority. Only the non-model permission layer may mint
    one-run write capabilities. Protected/canon/destructive/external effects do
    not self-authorize.
    """

    policy_version = "AMA-AUTONOMY-v0.3"

    def authorize(self, intent: AmaIntent, nonce: str) -> AmaPermissionGrant:
        action = intent.action_class

        if action is AmaActionClass.READ_ONLY:
            return AmaPermissionGrant(
                decision=AmaPermissionDecision.ALLOW,
                action_class=action,
                reason_code="READ_ONLY_ALLOWED",
            )

        if action is AmaActionClass.PREVIEW_STATE_CHANGE:
            return AmaPermissionGrant(
                decision=AmaPermissionDecision.PREVIEW_ONLY,
                action_class=action,
                reason_code="PREVIEW_DEFAULT",
            )

        if action is AmaActionClass.ORDINARY_LIVE_PLAY:
            if not intent.requested_commit:
                return AmaPermissionGrant(
                    decision=AmaPermissionDecision.PREVIEW_ONLY,
                    action_class=action,
                    reason_code="LIVE_PLAY_PREVIEW_DEFAULT",
                )
            digest = hashlib.sha256(
                f"{self.policy_version}|{nonce}|{intent.project}|{intent.command}|ORDINARY_LIVE_PLAY".encode()
            ).hexdigest()
            return AmaPermissionGrant(
                decision=AmaPermissionDecision.ALLOW,
                action_class=action,
                reason_code="USER_REQUESTED_ORDINARY_LIVE_PLAY",
                capability_token=f"AMA-CAP::{digest}",
            )

        if action is AmaActionClass.PROTECTED_CREATIVE_DECISION:
            return AmaPermissionGrant(
                decision=AmaPermissionDecision.ASK,
                action_class=action,
                reason_code="PROTECTED_USER_FULCRUM",
            )

        if action is AmaActionClass.CANON_REVISION:
            return AmaPermissionGrant(
                decision=AmaPermissionDecision.ASK,
                action_class=action,
                reason_code="CANON_REVISION_REQUIRES_EXPLICIT_APPROVAL",
            )

        if action is AmaActionClass.DESTRUCTIVE:
            return AmaPermissionGrant(
                decision=AmaPermissionDecision.DENY,
                action_class=action,
                reason_code="DESTRUCTIVE_NOT_AUTONOMOUS",
            )

        if action is AmaActionClass.EXTERNAL_SIDE_EFFECT:
            return AmaPermissionGrant(
                decision=AmaPermissionDecision.ASK,
                action_class=action,
                reason_code="EXTERNAL_EFFECT_REQUIRES_APPROVAL",
            )

        raise ValueError(f"unsupported Ama action class: {action}")
