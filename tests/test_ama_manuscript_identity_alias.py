from bloom_engine.runtime.manuscript import F, T, ManuscriptContextRepository
from bloom_engine.runtime.manuscript_identity import ALIAS_F, ENTITY_ALIASES_TABLE


ARC = "Aster Hollow / At the Threshold"


def _rec(record_id: str, fields: dict) -> dict:
    return {"id": record_id, "fields": fields}


class FakeAirtable:
    def __init__(self, rows: dict[str, list[dict]]):
        self.rows = rows

    def list_all(self, table_id: str) -> list[dict]:
        return list(self.rows.get(table_id, []))


def _repo() -> ManuscriptContextRepository:
    rows = {table_id: [] for table_id in T.values()}
    rows[T["characters"]] = [
        _rec(
            "rec-amara",
            {
                F["characters"]["name"]: "Amara Simone Bellamy",
                F["characters"]["arc"]: ARC,
                F["characters"]["role"]: "focal teen / Bellamy practitioner",
                "fld5f22G49B4HofYR": [{"id": "ent-amara", "name": "BLM-CHR-000003"}],
            },
        ),
        _rec(
            "rec-elias",
            {
                F["characters"]["name"]: "Elias James Verran",
                F["characters"]["arc"]: ARC,
                F["characters"]["role"]: "focal teen / Verran practitioner",
                "fld5f22G49B4HofYR": [{"id": "ent-elias", "name": "BLM-CHR-000004"}],
            },
        ),
    ]
    rows[T["locations"]] = [
        _rec(
            "rec-morrows",
            {
                F["location"]["key"]: "BLM-LOC-000009",
                F["location"]["name"]: "Morrow's",
                F["location"]["arc"]: ARC,
                F["location"]["type"]: "Business",
                "fldeWmqTrHhq5QCWm": [{"id": "ent-morrows", "name": "BLM-LOC-000009"}],
            },
        )
    ]
    rows[ENTITY_ALIASES_TABLE] = [
        _rec(
            "alias-amara",
            {
                ALIAS_F["entity_key"]: "BLM-CHR-000003",
                ALIAS_F["alias"]: "Amara Bellamy",
                ALIAS_F["arc"]: ARC,
                ALIAS_F["status"]: "Current",
                ALIAS_F["entity"]: [{"id": "ent-amara", "name": "BLM-CHR-000003"}],
            },
        ),
        _rec(
            "alias-elias",
            {
                ALIAS_F["entity_key"]: "BLM-CHR-000004",
                ALIAS_F["alias"]: "Elias Verran",
                ALIAS_F["arc"]: ARC,
                ALIAS_F["status"]: "Current",
                ALIAS_F["entity"]: [{"id": "ent-elias", "name": "BLM-CHR-000004"}],
            },
        ),
    ]
    return ManuscriptContextRepository(FakeAirtable(rows))


def test_acceptance_names_resolve_through_stable_aliases_and_typography():
    context = _repo().build(
        arc=ARC,
        command="Run the Morrow's Chapter 1 acceptance test",
        scene_or_chapter="Chapter 1 — Morrow's",
        temporal_scope="HISTORICAL_MANUSCRIPT",
        character_names=("Amara Bellamy", "Elias Verran"),
        location_names=("Morrow’s",),
    )

    assert context["status"] != "BLOCKED"
    assert context["blockers"] == []
    assert [item["name"] for item in context["characters"]] == [
        "Amara Simone Bellamy",
        "Elias James Verran",
    ]
    assert context["locations"][0]["name"] == "Morrow's"
    assert [item["mode"] for item in context["identity_resolution"]["characters"]] == [
        "REGISTERED_ALIAS",
        "REGISTERED_ALIAS",
    ]
    assert context["identity_resolution"]["locations"][0]["mode"] == "CANONICAL"


def test_unregistered_short_name_remains_blocked_no_fuzzy_match():
    context = _repo().build(
        arc=ARC,
        command="Draft",
        scene_or_chapter="Chapter 1",
        temporal_scope="HISTORICAL_MANUSCRIPT",
        character_names=("Amara",),
        location_names=("Morrow's",),
    )

    assert context["status"] == "BLOCKED"
    assert any("Exact character identity unresolved: Amara" in blocker for blocker in context["blockers"])
    assert context["identity_resolution"]["characters"][0]["mode"] == "UNRESOLVED"


def test_noncurrent_alias_does_not_resolve():
    repo = _repo()
    rows = repo.client.rows[ENTITY_ALIASES_TABLE]
    rows[0]["fields"][ALIAS_F["status"]] = "Deprecated"

    context = repo.build(
        arc=ARC,
        command="Draft",
        scene_or_chapter="Chapter 1",
        temporal_scope="HISTORICAL_MANUSCRIPT",
        character_names=("Amara Bellamy",),
        location_names=("Morrow's",),
    )

    assert context["status"] == "BLOCKED"
    assert context["identity_resolution"]["characters"][0]["mode"] == "UNRESOLVED"
