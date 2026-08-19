from bloom_engine.contracts.resolution import ResolutionStatus
from bloom_engine.hecate.models import MagicForm, MagicProfile
from bloom_engine.hecate.resolver import HecateResolver
from bloom_engine.hecate.store import InMemoryHecateStore
from bloom_engine.pantheon.gateway import CoreGateway
from bloom_engine.pantheon.protocol import CoreRequest
from bloom_engine.runtime import (
    AthenaDecision,
    CalliopeRender,
    EligibleOption,
    GatedClio,
    InMemoryClioTransactionStore,
    RenderClaim,
    RunnerDeps,
    RuntimeQuery,
    RuntimeRunner,
    SceneAnchor,
    SceneRequest,
)


FLORENCE = "BLM-CHR-000001"
PASSAGE = "HEC-FORM-SIG-PASSAGE"
ELIGIBLE_FACT = "MAGIC:PASSAGE:ELIGIBLE"


def evidence(fact: str):
    return ({"source": "runtime-port fixture", "fact": fact},)


def hecate_gateway() -> CoreGateway:
    form = MagicForm(
        key=PASSAGE,
        name="Passage",
        capability_statement="Works the transition between genuinely connected states.",
        requirements=("genuine connected endpoint",),
        hard_limits=("cannot invent an endpoint",),
        resolver_readiness="READY",
        evidence=evidence("Passage form is established"),
    )
    profile = MagicProfile(
        key="HEC-PROF-FLORENCE-MACKELLAR",
        practitioner_ref=FLORENCE,
        form_keys=(PASSAGE,),
        capability_envelope="Florence is an established Passage practitioner.",
        resolver_readiness="PARTIAL",
        evidence=evidence("Florence Passage profile is established"),
    )
    store = InMemoryHecateStore(forms={PASSAGE: form}, profiles={FLORENCE: profile})
    gateway = CoreGateway()
    gateway.register(HecateResolver(store))
    return gateway


class Repo:
    def __init__(self):
        self.traces = []

    def load_scene_anchor(self, request: SceneRequest) -> SceneAnchor:
        return SceneAnchor(
            scene_key="ASTER-S1E7-LABOR-DAY-GREEN-1218",
            arc=request.arc,
            episode="Episode 7",
            time_text="Monday 7 September 2009 12:18 PM",
            location_ref="BLM-LOC-000004",
            present_character_refs=(FLORENCE,),
            source_refs=("fixture:current-scene",),
        )

    def write_runtime_trace(self, trace):
        self.traces.append(trace)


class OneOption:
    def build(self, packet, request):
        return (
            EligibleOption(
                id="OPT-1",
                actor_ref=FLORENCE,
                summary="Use Passage within the established endpoint constraint.",
                requires_fact_keys=(ELIGIBLE_FACT,),
                intended_fact_keys=("ACTION:PASSAGE:ATTEMPT",),
            ),
        )


class SelectFirst:
    def decide(self, packet, eligible_options):
        return AthenaDecision(
            selected_option_id="OPT-1",
            fulcrum="ROUTINE_PLAYER_AUTONOMY",
            result="ACT",
            basis_fact_keys=(ELIGIBLE_FACT,),
            intended_fact_keys=("ACTION:PASSAGE:ATTEMPT",),
            reason_code="FIXTURE",
        )


class SafeRender:
    def __init__(self, unsupported=False):
        self.unsupported = unsupported

    def render(self, packet, decision, selected_option):
        claim = "UNSUPPORTED:INVENTED" if self.unsupported else "ACTION:PASSAGE:ATTEMPT"
        return CalliopeRender(
            text="Florence tests the established Passage.",
            claims=(RenderClaim(kind="FACT", key=claim),),
            source_decision_option_id=selected_option.id if selected_option else None,
        )


def make_runner(calliope=None):
    repo = Repo()
    clio_store = InMemoryClioTransactionStore()
    runner = RuntimeRunner(
        RunnerDeps(
            repository=repo,
            gateway=hecate_gateway(),
            options=OneOption(),
            athena=SelectFirst(),
            calliope=calliope or SafeRender(),
            clio=GatedClio(clio_store),
        )
    )
    return runner, repo, clio_store


def working_request(endpoint_state):
    inputs = {"practitioner_ref": FLORENCE, "form_key": PASSAGE}
    if endpoint_state is not ...:
        inputs["genuine_connected_endpoint"] = endpoint_state
    return SceneRequest(
        arc="Aster Hollow / At the Threshold",
        command="test Passage",
        mode="LIVE_PLAY",
        realization="COMMIT_AFTER_RENDER",
        authorization_token="AMA-CAP::fixture",
        queries=(
            RuntimeQuery(
                CoreRequest(predicate="working.eligible", inputs=inputs),
                required_for_request=True,
                fact_keys=(ELIGIBLE_FACT,),
            ),
        ),
    )


def test_runner_routes_through_core_gateway_and_hecate_end_to_end():
    runner, repo, _ = make_runner()
    output = runner.run(working_request(True))
    assert output.status == "COMPLETE"
    assert output.text == "Florence tests the established Passage."
    assert output.trace.packet is not None
    assert ELIGIBLE_FACT in output.trace.packet.allowed_fact_keys
    assert output.trace.packet.query_outcomes[0].resolution.status is ResolutionStatus.KNOWN
    # The clean port intentionally does not manufacture a story write from prose.
    assert output.trace.clio is not None
    assert output.trace.clio.status == "NO_OP"
    assert repo.traces[-1].final_status == "COMPLETE"


def test_required_hecate_unknown_fails_closed_before_athena():
    runner, _, _ = make_runner()
    output = runner.run(working_request(...))
    assert output.status == "BLOCKED"
    assert output.trace.packet is not None
    assert output.trace.packet.required_unknowns
    assert output.trace.athena is None
    assert ELIGIBLE_FACT not in output.trace.packet.allowed_fact_keys


def test_hecate_blocked_endpoint_stops_runtime():
    runner, _, _ = make_runner()
    output = runner.run(working_request(False))
    assert output.status == "BLOCKED"
    result = output.trace.packet.query_outcomes[0].resolution
    assert result.status is ResolutionStatus.BLOCKED
    assert output.trace.athena is None


def test_calliope_cannot_create_unsupported_reality():
    runner, _, _ = make_runner(calliope=SafeRender(unsupported=True))
    output = runner.run(working_request(True))
    assert output.status == "BLOCKED"
    assert output.trace.calliope is not None
    assert output.trace.adrasteia_postflight.status == "BLOCKED"
