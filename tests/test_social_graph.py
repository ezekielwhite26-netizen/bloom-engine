from bloom_engine.social.encounters import evaluate_encounter_channel
from bloom_engine.social.models import (
    EncounterChannel,
    EncounterChannelKind,
    EncounterDecision,
    EncounterEvidence,
    EncounterEvidenceState,
    RelationshipEdge,
    RelationshipStatus,
)


def _channel() -> EncounterChannel:
    return EncounterChannel(
        channel_key="AH-TEST-ACADEMY-001",
        focal_ref="BLM-CHR-000001",
        other_ref="BLM-CHR-TEST002",
        kind=EncounterChannelKind.CLASS,
        recurring=True,
    )


def test_supported_relationship_candidate_does_not_become_established():
    edge = RelationshipEdge(
        edge_key="REL-TEST-001",
        left_ref="HENRY",
        right_ref="ANYA",
        relation_kind="peer-friendship",
        status=RelationshipStatus.SUPPORTED_CANDIDATE,
        provenance_refs=("Aster Hollow Definitive Master Compendium",),
    )
    assert edge.status is RelationshipStatus.SUPPORTED_CANDIDATE
    assert edge.status is not RelationshipStatus.ESTABLISHED


def test_relationship_alone_cannot_establish_encounter_presence():
    assert evaluate_encounter_channel(_channel(), ()) is EncounterDecision.UNKNOWN


def test_unknown_schedule_fails_closed_even_when_other_prerequisites_are_known():
    evidence = (
        EncounterEvidence("EUNOMIA", "institution.membership.academy", EncounterEvidenceState.KNOWN_TRUE),
        EncounterEvidence("CHRONOS", "schedule.class.third_period", EncounterEvidenceState.UNKNOWN),
        EncounterEvidence("ATLAS", "location.shared.classroom", EncounterEvidenceState.KNOWN_TRUE),
    )
    assert evaluate_encounter_channel(_channel(), evidence) is EncounterDecision.UNKNOWN


def test_known_false_location_blocks_candidate():
    evidence = (
        EncounterEvidence("EUNOMIA", "institution.membership.academy", EncounterEvidenceState.KNOWN_TRUE),
        EncounterEvidence("CHRONOS", "schedule.class.third_period", EncounterEvidenceState.KNOWN_TRUE),
        EncounterEvidence("ATLAS", "location.shared.classroom", EncounterEvidenceState.KNOWN_FALSE),
    )
    assert evaluate_encounter_channel(_channel(), evidence) is EncounterDecision.CANNOT_ARRIVE


def test_known_school_time_and_place_make_channel_eligible():
    evidence = (
        EncounterEvidence("EUNOMIA", "institution.membership.academy", EncounterEvidenceState.KNOWN_TRUE),
        EncounterEvidence("CHRONOS", "schedule.class.third_period", EncounterEvidenceState.KNOWN_TRUE),
        EncounterEvidence("ATLAS", "location.shared.classroom", EncounterEvidenceState.KNOWN_TRUE),
    )
    assert evaluate_encounter_channel(_channel(), evidence) is EncounterDecision.CAN_ARRIVE


def test_not_applicable_is_not_positive_evidence():
    evidence = (
        EncounterEvidence("HERA", "relationship.familiarity.peer", EncounterEvidenceState.NOT_APPLICABLE),
    )
    assert evaluate_encounter_channel(_channel(), evidence) is EncounterDecision.UNKNOWN
