from __future__ import annotations

import pytest

from bloom_engine.api import AmaApiServices, create_app
from bloom_engine.api.action_schema import build_custom_gpt_action_schema
from bloom_engine.runtime.models import RunnerOutput, RuntimeTrace, SceneRequest


TOKEN = "test-token-that-is-long-enough-12345"


class NoopBuilder:
    def build_preview(self, body):
        return SceneRequest(arc=body.arc, command=body.command)


class NoopRunner:
    def run(self, request):
        trace = RuntimeTrace(run_key="RUN::ACTION-SCHEMA", request=request, final_status="COMPLETE")
        return RunnerOutput(status="COMPLETE", trace=trace)


def app():
    return create_app(
        services=AmaApiServices(runner=NoopRunner(), request_builder=NoopBuilder()),
        bearer_token=TOKEN,
    )


def test_action_schema_exposes_only_reviewed_read_preview_surface():
    schema = build_custom_gpt_action_schema(app(), server_url="https://ama.example.test")
    assert set(schema["paths"]) == {"/v1/capabilities", "/v1/runtime/preview"}
    assert "/health" not in schema["paths"]
    assert schema["paths"]["/v1/capabilities"]["get"]["operationId"] == "getBloomCapabilities"
    assert schema["paths"]["/v1/runtime/preview"]["post"]["operationId"] == "previewBloomRuntime"
    assert schema["paths"]["/v1/runtime/preview"]["post"]["x-openai-isConsequential"] is False


def test_action_schema_keeps_write_authority_out_of_preview_input_model():
    schema = build_custom_gpt_action_schema(app(), server_url="https://ama.example.test")
    preview = schema["components"]["schemas"]["RuntimePreviewBody"]
    properties = set(preview["properties"])
    assert properties == {
        "arc",
        "command",
        "mode",
        "requested_actor_ref",
        "requested_target_location_ref",
        "requested_object_ref",
        "visual_requested",
    }
    assert properties.isdisjoint(
        {
            "authorization_token",
            "capability_token",
            "evidence",
            "permission_mode",
            "commit",
            "write",
            "resolution",
            "queries",
        }
    )


def test_action_schema_requires_https_and_rejects_embedded_credentials():
    with pytest.raises(ValueError):
        build_custom_gpt_action_schema(app(), server_url="http://ama.example.test")
    with pytest.raises(ValueError):
        build_custom_gpt_action_schema(app(), server_url="https://user:secret@ama.example.test")


def test_action_schema_advertises_capability_state_but_has_no_write_path():
    schema = build_custom_gpt_action_schema(app(), server_url="https://ama.example.test/")
    assert schema["servers"] == [{"url": "https://ama.example.test"}]
    assert all("commit" not in path.lower() and "write" not in path.lower() for path in schema["paths"])
    capabilities = schema["components"]["schemas"]["CapabilityView"]
    assert "runtime_commit" in capabilities["properties"]
    assert "persistence_live" in capabilities["properties"]
