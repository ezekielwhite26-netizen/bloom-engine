from bloom_engine.api.hosted_live import (
    CURRENT_SCENE_FIELDS,
    CURRENT_SCENE_TABLE,
    AirtableCurrentSceneRepository,
    build_live_services,
)
from bloom_engine.api.models import RuntimePreviewBody
from bloom_engine.runtime.models import SceneRequest


class FakeReadOnlyAirtable:
    def __init__(self):
        self.calls = []

    def list_all(self, table_id):
        self.calls.append(("GET", table_id))
        assert table_id == CURRENT_SCENE_TABLE
        return [
            {
                "id": "recQ4LA0or1gHiHgl",
                "fields": {
                    CURRENT_SCENE_FIELDS["scene_key"]: "ASTER-S1E7-LABOR-DAY-GREEN-1218",
                    CURRENT_SCENE_FIELDS["arc"]: "Aster Hollow / At the Threshold",
                    CURRENT_SCENE_FIELDS["episode"]: "Season 1, Episode 7 — OPENING",
                    CURRENT_SCENE_FIELDS["time"]: "Monday, 7 September 2009 — 12:18 PM",
                    CURRENT_SCENE_FIELDS["location"]: "The Green",
                    CURRENT_SCENE_FIELDS["present"]: "Florence; Asteria; Teddy; Claire",
                    CURRENT_SCENE_FIELDS["last_beat"]: "Claire checks her phone; the observed time is 12:18 PM.",
                    CURRENT_SCENE_FIELDS["guardrails"]: "Presence Gate required before named arrivals.",
                    CURRENT_SCENE_FIELDS["location_entity"]: [
                        {"id": "recT07mVNPDKBen95", "name": "BLM-LOC-000004"}
                    ],
                    CURRENT_SCENE_FIELDS["present_entities"]: [
                        {"id": "a", "name": "BLM-CHR-000001"},
                        {"id": "b", "name": "BLM-CHR-000002"},
                        {"id": "c", "name": "BLM-CHR-000010"},
                        {"id": "d", "name": "BLM-CHR-000007"},
                    ],
                },
            }
        ]


def test_repository_maps_exact_current_scene_anchor_without_writes():
    client = FakeReadOnlyAirtable()
    repo = AirtableCurrentSceneRepository(client)
    anchor = repo.load_scene_anchor(
        SceneRequest(
            arc="Aster Hollow / At the Threshold",
            command="inspect current scene",
        )
    )

    assert anchor.scene_key == "ASTER-S1E7-LABOR-DAY-GREEN-1218"
    assert anchor.location_ref == "BLM-LOC-000004"
    assert tuple(anchor.present_character_refs) == (
        "BLM-CHR-000001",
        "BLM-CHR-000002",
        "BLM-CHR-000010",
        "BLM-CHR-000007",
    )
    assert anchor.source_refs == (
        "airtable:tblipTnwAEA05zs9v:recQ4LA0or1gHiHgl",
    )
    repo.write_runtime_trace(object())
    assert client.calls == [("GET", CURRENT_SCENE_TABLE)]
    assert not hasattr(client, "create")
    assert not hasattr(client, "update")


def test_real_runtime_packet_uses_current_scene_instead_of_hosted_fixture():
    client = FakeReadOnlyAirtable()
    services = build_live_services(client)
    request = services.request_builder.build_preview(
        RuntimePreviewBody(
            arc="Aster Hollow / At the Threshold",
            command="Inspect the current Aster Hollow state without changing anything.",
            mode="DRY_RUN",
        )
    )

    output = services.runner.run(request)

    assert output.status == "COMPLETE"
    assert output.trace.packet is not None
    assert output.trace.packet.anchor.scene_key == "ASTER-S1E7-LABOR-DAY-GREEN-1218"
    assert output.trace.run_key != "RUN::HOSTED-FIXTURE"
    assert output.trace.clio is not None
    assert output.trace.clio.status == "NO_OP"
    assert "Nothing was persisted" in output.text
    assert client.calls == [("GET", CURRENT_SCENE_TABLE)]


def test_scene_inspection_stays_preview_only():
    services = build_live_services(FakeReadOnlyAirtable())
    request = services.request_builder.build_preview(
        RuntimePreviewBody(
            arc="Aster Hollow / At the Threshold",
            command="inspect active scene pointer",
            mode="DRY_RUN",
        )
    )
    assert request.realization == "PREVIEW"
    assert request.authorization_token is None
    assert request.queries == ()
