import pytest

from bloom_engine.contracts import Resolution, ResolutionStatus


def test_unknown_fails_closed_for_required_gate():
    result = Resolution(owner="ATLAS", predicate="route_exists", status=ResolutionStatus.UNKNOWN)
    assert result.is_eligible_for_required_gate() is False


def test_blocked_fails_closed_for_required_gate():
    result = Resolution(
        owner="HECATE",
        predicate="passage_endpoint_valid",
        status=ResolutionStatus.BLOCKED,
        evidence=({"source": "HECATE form", "fact": "Passage cannot invent endpoint"},),
    )
    result.require_evidence_for_decisive_status()
    assert result.is_eligible_for_required_gate() is False


def test_known_requires_evidence():
    result = Resolution(owner="THEMIS", predicate="identity", status=ResolutionStatus.KNOWN)
    with pytest.raises(ValueError):
        result.require_evidence_for_decisive_status()


def test_known_with_evidence_can_satisfy_required_gate():
    result = Resolution(
        owner="THEMIS",
        predicate="identity",
        status=ResolutionStatus.KNOWN,
        value="BLM-CHR-000001",
        evidence=({"source": "Saga Entities", "id": "BLM-CHR-000001"},),
    )
    result.require_evidence_for_decisive_status()
    assert result.is_eligible_for_required_gate() is True


def test_not_applicable_is_not_positive_eligibility_by_itself():
    result = Resolution(owner="HECATE", predicate="ordinary_walk", status=ResolutionStatus.NOT_APPLICABLE)
    assert result.is_eligible_for_required_gate() is False
