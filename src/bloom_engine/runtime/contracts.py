from __future__ import annotations

from typing import Protocol, Sequence

from bloom_engine.runtime.models import (
    AthenaDecision,
    CalliopeRender,
    ClioHandoff,
    ClioResult,
    ContextPacket,
    EligibleOption,
    RuntimeTrace,
    SceneAnchor,
    SceneRequest,
)


class RuntimeRepository(Protocol):
    def load_scene_anchor(self, request: SceneRequest) -> SceneAnchor: ...

    def write_runtime_trace(self, trace: RuntimeTrace) -> None: ...


class OptionBuilder(Protocol):
    def build(self, packet: ContextPacket, request: SceneRequest) -> Sequence[EligibleOption]: ...


class AthenaAdapter(Protocol):
    def decide(self, packet: ContextPacket, eligible_options: Sequence[EligibleOption]) -> AthenaDecision: ...


class CalliopeAdapter(Protocol):
    def render(
        self,
        packet: ContextPacket,
        decision: AthenaDecision,
        selected_option: EligibleOption | None,
    ) -> CalliopeRender: ...


class ClioPort(Protocol):
    def commit(self, handoff: ClioHandoff) -> ClioResult: ...
