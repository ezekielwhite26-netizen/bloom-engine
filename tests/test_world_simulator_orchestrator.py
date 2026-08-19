import pytest

from bloom_engine.pantheon.protocol import CoreRequest
from bloom_engine.world_simulator import SimulationBoundary, WorldSimulatorOrchestrator


def boundary() -> SimulationBoundary:
    return SimulationBoundary(
        boundary_key="MIDNIGHT-20090907",
        kind="civil_time_boundary",
        evidence=({"owner": "CHRONOS", "fact": "Monday 7 Sep 2009 00:00 boundary established"},),
    )


def test_world_simulator_routes_without_answering():
    plan = WorldSimulatorOrchestrator().plan(
        boundary=boundary(),
        requests=(
            CoreRequest(predicate="time.boundary", subject_refs=("Aster Hollow",)),
            CoreRequest(predicate="organization.current_state", subject_refs=("Academy",)),
            CoreRequest(predicate="forecast.matured", subject_refs=("Labor Day closure",)),
        ),
    )
    assert plan.owners == ("CHRONOS", "EUNOMIA", "ANANKE")
    assert plan.requires_athena is False
    assert all("World Simulator" in note or "CLIO" in note for note in plan.notes)


def test_boundary_requires_evidence():
    with pytest.raises(ValueError, match="boundary requires evidence"):
        WorldSimulatorOrchestrator().plan(
            boundary=SimulationBoundary(boundary_key="X", kind="unknown"),
            requests=(CoreRequest(predicate="time.boundary"),),
        )


def test_unknown_or_ambiguous_owner_fails_closed():
    with pytest.raises(Exception):
        WorldSimulatorOrchestrator().plan(
            boundary=boundary(),
            requests=(CoreRequest(predicate="world_state.catchall"),),
        )


def test_duplicate_query_is_rejected():
    req = CoreRequest(predicate="time.boundary", subject_refs=("Aster Hollow",))
    with pytest.raises(ValueError, match="duplicate sovereign query"):
        WorldSimulatorOrchestrator().plan(boundary=boundary(), requests=(req, req))


def test_athena_cannot_be_smuggled_into_deterministic_advancement():
    with pytest.raises(PermissionError, match="genuine discretion"):
        WorldSimulatorOrchestrator().plan(
            boundary=boundary(),
            requests=(CoreRequest(predicate="decision.select", subject_refs=("NPC",)),),
            genuine_discretion=False,
        )


def test_discretion_requires_explicit_athena_query():
    with pytest.raises(ValueError, match="explicit ATHENA request"):
        WorldSimulatorOrchestrator().plan(
            boundary=boundary(),
            requests=(CoreRequest(predicate="forecast.matured", subject_refs=("thread",)),),
            genuine_discretion=True,
        )


def test_genuine_discretion_routes_to_athena_but_simulator_does_not_choose():
    plan = WorldSimulatorOrchestrator().plan(
        boundary=boundary(),
        requests=(
            CoreRequest(predicate="forecast.matured", subject_refs=("thread",)),
            CoreRequest(predicate="decision.select", subject_refs=("NPC",)),
        ),
        genuine_discretion=True,
    )
    assert plan.owners == ("ANANKE", "ATHENA")
    assert plan.requires_athena is True
