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


def _presence_evidence(*, eunomia=EncounterEvidenceState.KNOWN_TRUE, chronos=EncounterEvidenceState.KNOWN_TRUE, atlas=EncounterEvidenceState.KNOWN_TRUE):
    return (
        EncounterEvidence("EUNOMIA", "institution.membership.academy", eunomia),
        EncounterEvidence("CHRONOS", "schedule.class.third_period", chronos),
        EncounterEvidence("ATLAS", "location.shared.classroom", atlas),
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
    evidence = (
        EncounterEvidence("HERA", "relationship.familiarity.friend", EncounterEvidenceState.KNOWN_TRUE),
    )
    assert evaluate_encounter_channel(_channel(), evidence) is EncounterDecision.UNKNOWN


def test_unknown_schedule_fails_closed_even_when_other_prerequisites_are_known():
    evidence = _presence_evidence(chronos=EncounterEvidenceState.UNKNOWN)
    assert evaluate_encounter_channel(_channel(), evidence) is EncounterDecision.UNKNOWN


def test_known_false_location_blocks_candidate():
    evidence = _presence_evidence(atlas=EncounterEvidenceState.KNOWN_FALSE)
    assert evaluate_encounter_channel(_channel(), evidence) is EncounterDecision.CANNOT_ARRIVE


def test_known_school_time_and_place_make_channel_eligible():
    assert evaluate_encounter_channel(_channel(), _presence_evidence()) is EncounterDecision.CAN_ARRIVE


def test_not_applicable_is_not_positive_evidence():
    evidence = (
        EncounterEvidence("EUNOMIA", "institution.membership.academy", EncounterEvidenceState.NOT_APPLICABLE),
        EncounterEvidence("CHRONOS", "schedule.class.third_period", EncounterEvidenceState.KNOWN_TRUE),
        EncounterEvidence("ATLAS", "location.shared.classroom", EncounterEvidenceState.KNOWN_TRUE),
    )
    assert evaluate_encounter_channel(_channel(), evidence) is EncounterDecision.UNKNOWN


def test_missing_chronos_cannot_be_compensated_by_relationship_or_location():
    evidence = (
        EncounterEvidence("EUNOMIA", "institution.membership.academy", EncounterEvidenceState.KNOWN_TRUE),
        EncounterEvidence("ATLAS", "location.academy.same_site", EncounterEvidenceState.KNOWN_TRUE),
        EncounterEvidence("HERA", "relationship.familiarity.friend", EncounterEvidenceState.KNOWN_TRUE),
    )
    assert evaluate_encounter_channel(_channel(), evidence) is EncounterDecision.UNKNOWN


def test_missing_atlas_cannot_be_compensated_by_known_membership_and_schedule():
    evidence = (
        EncounterEvidence("EUNOMIA", "organization.student_council.events_membership", EncounterEvidenceState.KNOWN_TRUE),
        EncounterEvidence("CHRONOS", "schedule.events_committee.overlap", EncounterEvidenceState.KNOWN_TRUE),
    )
    assert evaluate_encounter_channel(_channel(), evidence) is EncounterDecision.UNKNOWN


def test_organization_existence_does_not_equal_actor_presence():
    evidence = (
        EncounterEvidence("EUNOMIA", "organization.student_council.exists", EncounterEvidenceState.KNOWN_TRUE),
        EncounterEvidence("CHRONOS", "schedule.events_committee.overlap", EncounterEvidenceState.UNKNOWN),
        EncounterEvidence("ATLAS", "location.academy.reachable", EncounterEvidenceState.KNOWN_TRUE),
    )
    assert evaluate_encounter_channel(_channel(), evidence) is EncounterDecision.UNKNOWN


def test_optional_refiners_cannot_override_false_location():
    evidence = _presence_evidence(atlas=EncounterEvidenceState.KNOWN_FALSE) + (
        EncounterEvidence("HERA", "relationship.familiarity.friend", EncounterEvidenceState.KNOWN_TRUE),
        EncounterEvidence("MNEMOSYNE", "inclination.wants_to_talk", EncounterEvidenceState.KNOWN_TRUE),
        EncounterEvidence("HERMES", "communication.reason_to_contact", EncounterEvidenceState.KNOWN_TRUE),
    )
    assert evaluate_encounter_channel(_channel(), evidence) is EncounterDecision.CANNOT_ARRIVE


def test_athena_evidence_cannot_make_an_ineligible_candidate_present():
    evidence = (
        EncounterEvidence("EUNOMIA", "institution.membership.academy", EncounterEvidenceState.KNOWN_TRUE),
        EncounterEvidence("CHRONOS", "schedule.shared_window", EncounterEvidenceState.UNKNOWN),
        EncounterEvidence("ATLAS", "location.academy.same_site", EncounterEvidenceState.KNOWN_TRUE),
        EncounterEvidence("ATHENA", "discretion.select_candidate", EncounterEvidenceState.KNOWN_TRUE),
    )
    assert evaluate_encounter_channel(_channel(), evidence) is EncounterDecision.UNKNOWN


def test_shared_junior_cohort_without_resolved_overlap_does_not_spawn_peer():
    channel = EncounterChannel(
        channel_key="AH-TEST-JUNIOR-COHORT-001",
        focal_ref="BLM-CHR-000001",
        other_ref="PLANNING-JUNIOR-PEER",
        kind=EncounterChannelKind.SCHOOL_COHORT,
        recurring=True,
    )
    evidence = (
        EncounterEvidence("EUNOMIA", "institution.academy.junior_cohort", EncounterEvidenceState.KNOWN_TRUE),
        EncounterEvidence("CHRONOS", "schedule.shared_window", EncounterEvidenceState.UNKNOWN),
        EncounterEvidence("ATLAS", "location.academy.same_site", EncounterEvidenceState.KNOWN_TRUE),
    )
    assert evaluate_encounter_channel(channel, evidence) is EncounterDecision.UNKNOWN


def test_events_membership_without_confirmed_meeting_time_does_not_spawn_peer():
    channel = EncounterChannel(
        channel_key="AH-TEST-EVENTS-001",
        focal_ref="BLM-CHR-000001",
        other_ref="PLANNING-EVENTS-PEER",
        kind=EncounterChannelKind.STUDENT_ACTIVITY,
        recurring=True,
    )
    evidence = (
        EncounterEvidence("EUNOMIA", "organization.student_council.events_membership", EncounterEvidenceState.KNOWN_TRUE),
        EncounterEvidence("CHRONOS", "schedule.events_committee.overlap", EncounterEvidenceState.UNKNOWN),
        EncounterEvidence("ATLAS", "location.academy.reachable", EncounterEvidenceState.KNOWN_TRUE),
    )
    assert evaluate_encounter_channel(channel, evidence) is EncounterDecision.UNKNOWN
