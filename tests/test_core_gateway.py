import pytest

from bloom_engine.contracts.resolution import ResolutionStatus
from bloom_engine.hecate.models import MagicForm, MagicProfile
from bloom_engine.hecate.resolver import HecateResolver
from bloom_engine.hecate.store import InMemoryHecateStore
from bloom_engine.pantheon.gateway import CoreGateway, CoreUnavailableError
from bloom_engine.pantheon.protocol import CoreRequest


FLORENCE = "BLM-CHR-000001"
PASSAGE = "HEC-FORM-SIG-PASSAGE"


def hecate() -> HecateResolver:
    evidence = ({"source": "fixture", "fact": "established"},)
    store = InMemoryHecateStore(
        forms={
            PASSAGE: MagicForm(
                key=PASSAGE,
                name="Passage",
                capability_statement="Works transitions between genuinely connected states.",
                hard_limits=("cannot invent endpoint",),
                resolver_readiness="READY",
                evidence=evidence,
            )
        },
        profiles={
            FLORENCE: MagicProfile(
                key="HEC-PROF-FLORENCE-MACKELLAR",
                practitioner_ref=FLORENCE,
                form_keys=(PASSAGE,),
                capability_envelope="Passage practitioner",
                evidence=evidence,
            )
        },
    )
    return HecateResolver(store)


def test_gateway_routes_hecate_predicate_to_installed_hecate_resolver():
    gateway = CoreGateway()
    gateway.register(hecate())
    result = gateway.resolve(
        CoreRequest(
            predicate="working.eligible",
            inputs={
                "practitioner_ref": FLORENCE,
                "form_key": PASSAGE,
                "genuine_connected_endpoint": False,
            },
        )
    )
    assert result.owner == "HECATE"
    assert result.status is ResolutionStatus.BLOCKED


def test_gateway_does_not_convert_missing_core_into_domain_unknown():
    gateway = CoreGateway()
    gateway.register(hecate())
    with pytest.raises(CoreUnavailableError):
        gateway.resolve(CoreRequest(predicate="time.current"))


def test_gateway_rejects_duplicate_resolver_for_same_sovereign_core():
    gateway = CoreGateway()
    gateway.register(hecate())
    with pytest.raises(ValueError):
        gateway.register(hecate())


def test_gateway_preserves_request_order_and_statuses():
    gateway = CoreGateway()
    gateway.register(hecate())
    results = gateway.resolve_many(
        (
            CoreRequest(predicate="magic.applicable", inputs={"magical_question": False}),
            CoreRequest(
                predicate="working.eligible",
                inputs={
                    "practitioner_ref": FLORENCE,
                    "form_key": PASSAGE,
                    "genuine_connected_endpoint": False,
                },
            ),
        )
    )
    assert tuple(result.predicate for result in results) == (
        "magic.applicable",
        "working.eligible",
    )
    assert tuple(result.status for result in results) == (
        ResolutionStatus.NOT_APPLICABLE,
        ResolutionStatus.BLOCKED,
    )
