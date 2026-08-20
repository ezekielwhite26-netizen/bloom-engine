import pytest

from bloom_engine.pantheon.protocol import CoreRequest, assert_core_may_answer
from bloom_engine.pantheon.registry import CORE_SPECS, OwnershipError, assert_registry_has_unique_prefix_ownership, owner_for


def test_registry_contains_exactly_fifteen_sovereign_cores():
    assert len(CORE_SPECS) == 15
    assert {spec.name for spec in CORE_SPECS} == {
        "THEMIS", "CHRONOS", "ATLAS", "HEPHAESTUS", "MNEMOSYNE",
        "HERA", "ANANKE", "HECATE", "APOLLO", "HERMES", "EUNOMIA",
        "ATHENA", "CALLIOPE", "CLIO", "ADRASTEIA",
    }


def test_registry_prefixes_have_unique_ownership():
    assert_registry_has_unique_prefix_ownership()


def test_magic_predicate_routes_only_to_hecate():
    assert owner_for("working.eligible").name == "HECATE"
    assert owner_for("focus.is_focus").name == "HECATE"


def test_core_cannot_answer_another_owners_predicate():
    with pytest.raises(PermissionError):
        assert_core_may_answer("HECATE", "object.available")


def test_unowned_predicate_fails_closed():
    with pytest.raises(OwnershipError):
        owner_for("misc.guess")
