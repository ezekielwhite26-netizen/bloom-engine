from __future__ import annotations

from typing import Any, Sequence

from bloom_engine.runtime import manuscript as _manuscript


# Keep the original deterministic evidence gate for actual FACT claims. This adapter
# adds a separate non-canon lane for manuscript texture/discovery so absence of a
# pre-existing Airtable fact is not automatically treated as contradiction.
_BASE_REVIEW = _manuscript.review_manuscript


def _kind(value: Any) -> str:
    return (
        str(value or "")
        .strip()
        .upper()
        .replace("-", "_")
        .replace("/", "_")
        .replace(" ", "_")
    )


def _finding(
    *,
    authority_class: str,
    severity: str,
    result: str,
    message: str,
    key: str,
    may_remain_provisionally: bool,
    responsible_owner: str,
) -> dict[str, Any]:
    return {
        "category": "CANON",
        "severity": severity,
        "result": result,
        "authority_class": authority_class,
        "message": message,
        "evidence_refs": [key] if key else [],
        "responsible_owner": responsible_owner,
        "provisional_only": authority_class != "CANON/GOLD",
        "may_remain_provisionally": may_remain_provisionally,
        "canon_promotion_authorized": False,
    }


def review_manuscript_with_discovery(
    *,
    session: _manuscript.ManuscriptReviewSession,
    phase: str,
    claims: Sequence[dict[str, str]],
    reader_new_subjects: Sequence[str],
    oriented_subjects: Sequence[str],
    reader_ledger_commit_requested: bool,
) -> dict[str, Any]:
    """Run ADRASTEIA with a bounded manuscript-discovery lane.

    FACT remains fail-closed against the issued evidence contract. A caller may instead
    declare a detail as adjacent/discovery/open when it is intentionally *not* being
    asserted as established world truth. Those details can survive manuscript review
    provisionally and are surfaced for later author review/promotion.

    This adapter does not make semantic contradictions safe. A detail already identified
    as conflicting must use CONFLICTING_DETAIL and blocks. Protected player commitments
    and ordinary unissued FACT claims are still routed through the original hard gate.
    """

    factual_claims: list[dict[str, str]] = []
    classifications: list[dict[str, Any]] = []

    for claim in claims:
        kind = _kind(claim.get("kind"))
        key = str(claim.get("key", "")).strip()

        if kind in {"ADJACENT_DETAIL", "SUPPORTED_ADJACENT", "SUPPORTED_ADJACENT_DETAIL"}:
            classifications.append(
                _finding(
                    authority_class="SUPPORTED/ADJACENT",
                    severity="INFO",
                    result="PASS",
                    message=(
                        "Detail is explicitly non-canonical manuscript texture adjacent to established reality. "
                        "Absence of a prior record is not a contradiction; it may remain provisionally if the "
                        "semantic review finds no conflict. It does not become canon by appearing in prose."
                    ),
                    key=key,
                    may_remain_provisionally=True,
                    responsible_owner="ADRASTEIA",
                )
            )
            continue

        if kind in {
            "CANON_CANDIDATE",
            "CANON_CANDIDATE_DISCOVERY",
            "DISCOVERY_CANDIDATE",
            "DISCOVERY",
        }:
            classifications.append(
                _finding(
                    authority_class="CANON CANDIDATE/DISCOVERY",
                    severity="WARN",
                    result="WARN",
                    message=(
                        "Manuscript has discovered a coherent candidate detail. It may remain provisionally, "
                        "but durable promotion requires explicit author approval and routing to the responsible "
                        "sovereign core; this review performs no canon write."
                    ),
                    key=key,
                    may_remain_provisionally=True,
                    responsible_owner="AUTHOR / RESPONSIBLE SOVEREIGN",
                )
            )
            continue

        if kind in {"OPEN_DETAIL", "OPEN"}:
            classifications.append(
                _finding(
                    authority_class="OPEN",
                    severity="WARN",
                    result="WARN",
                    message=(
                        "Detail chooses among materially unresolved possibilities. It may be carried only as an "
                        "explicitly provisional manuscript choice and must not be cited as established canon until resolved."
                    ),
                    key=key,
                    may_remain_provisionally=True,
                    responsible_owner="AUTHOR / RESPONSIBLE SOVEREIGN",
                )
            )
            continue

        if kind in {"CONFLICTING_DETAIL", "CONFLICTING", "CONFLICT"}:
            classifications.append(
                _finding(
                    authority_class="CONFLICTING",
                    severity="CRITICAL",
                    result="BLOCK",
                    message=(
                        "Detail is identified as conflicting with controlling canon/Gold/played history or another "
                        "sovereign constraint and cannot pass manuscript review unchanged."
                    ),
                    key=key,
                    may_remain_provisionally=False,
                    responsible_owner="RESPONSIBLE SOVEREIGN / CALLIOPE",
                )
            )
            continue

        # FACT, CANON/GOLD, PLAYER_COMMITMENT, and unknown kinds retain the original
        # evidence/agency behavior. This prevents the discovery lane from weakening the
        # existing fail-closed contract for actual truth claims.
        factual_claims.append(claim)

    reviewed = _BASE_REVIEW(
        session=session,
        phase=phase,
        claims=tuple(factual_claims),
        reader_new_subjects=reader_new_subjects,
        oriented_subjects=oriented_subjects,
        reader_ledger_commit_requested=reader_ledger_commit_requested,
    )

    findings = list(reviewed.get("findings", []))
    findings.extend(classifications)
    reviewed["findings"] = findings
    reviewed["authority_classifications"] = classifications
    reviewed["authority_policy"] = {
        "classes": [
            "CANON/GOLD",
            "SUPPORTED/ADJACENT",
            "CANON CANDIDATE/DISCOVERY",
            "OPEN",
            "CONFLICTING",
        ],
        "rule_refs": ["BLOOM-WR-CORR-009", "BLOOM-WR-QA-012", "BLM-TST-000149"],
        "absence_of_record_is_not_contradiction": True,
        "provisional_detail_creates_canon": False,
        "promotion_requires_author_approval": True,
    }

    if any(item.get("result") == "BLOCK" for item in findings):
        reviewed["status"] = "BLOCKED"
    elif any(item.get("result") == "WARN" for item in findings):
        reviewed["status"] = "PASS_WITH_WARNINGS"
    else:
        reviewed["status"] = "PASS"

    # Reassert the read-only manuscript boundary even if future callers add fields.
    reviewed["story_canon_persisted"] = False
    reviewed["reader_ledger_committed"] = False
    reviewed["replacement_prose"] = None
    reviewed["editor_contract"] = (
        "ADRASTEIA diagnoses, classifies authority, and routes discoveries; "
        "CALLIOPE revises prose; sovereign cores own truth and promotion."
    )
    return reviewed


def install_manuscript_discovery_policy() -> None:
    """Install the world-discovery adapter at the existing manuscript review seam."""
    _manuscript.review_manuscript = review_manuscript_with_discovery
