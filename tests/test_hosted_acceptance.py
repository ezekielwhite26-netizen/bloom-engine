import copy

import pytest

from bloom_engine.hosted_acceptance import (
    CURRENT_SCENE_TABLE,
    EVENTS_TABLE,
    HOSTED_DRY_RUN_KEY,
    SCRIBE_TRANSACTIONS_TABLE,
    SCENE_F,
    TX_F,
    run_hosted_dry_run,
)


class FakeAirtable:
    def __init__(self):
        self.tables = {
            EVENTS_TABLE: [
                {"id": f"rec-event-{i}", "fields": {"fldEKj1Iih2AE7HhM": f"BLM-EVT-{i:06d}", "fldb82ATprvlOcqLU": f"EVENT-{i}"}}
                for i in range(1, 20)
            ],
            CURRENT_SCENE_TABLE: [
                {
                    "id": "recQ4LA0or1gHiHgl",
                    "fields": {
                        SCENE_F["key"]: "ASTER-S1E7-LABOR-DAY-GREEN-1218",
                        SCENE_F["time"]: "Monday, 7 September 2009 — 12:18 PM",
                        SCENE_F["location"]: "The Green",
                        SCENE_F["present"]: "Florence; Asteria; Teddy; Claire",
                        SCENE_F["last_beat"]: "Claire checks her phone: 12:18 PM.",
                    },
                }
            ],
            SCRIBE_TRANSACTIONS_TABLE: [],
        }
        self._serial = 1

    def list_all(self, table_id):
        return copy.deepcopy(self.tables[table_id])

    def create(self, table_id, fields):
        row = {"id": f"rec-tx-{self._serial}", "fields": dict(fields)}
        self._serial += 1
        self.tables[table_id].append(row)
        return copy.deepcopy(row)

    def update(self, table_id, record_id, fields):
        matches = [r for r in self.tables[table_id] if r["id"] == record_id]
        assert len(matches) == 1
        matches[0]["fields"].update(dict(fields))
        return copy.deepcopy(matches[0])


def test_hosted_dry_run_writes_only_scribe_and_preserves_story_state():
    air = FakeAirtable()
    events_before = copy.deepcopy(air.tables[EVENTS_TABLE])
    scene_before = copy.deepcopy(air.tables[CURRENT_SCENE_TABLE])

    result = run_hosted_dry_run(air, attempt_label="fixture attempt")

    assert result["status"] == "PASS"
    assert result["events_before"] == 19
    assert result["events_after"] == 19
    assert air.tables[EVENTS_TABLE] == events_before
    assert air.tables[CURRENT_SCENE_TABLE] == scene_before
    assert len(air.tables[SCRIBE_TRANSACTIONS_TABLE]) == 1
    tx = air.tables[SCRIBE_TRANSACTIONS_TABLE][0]["fields"]
    assert tx[TX_F["key"]] == HOSTED_DRY_RUN_KEY
    assert tx[TX_F["status"]] == "Dry Run"
    assert tx[TX_F["authorized"]] is False
    assert "PASS" in tx[TX_F["readback_result"]]


def test_hosted_dry_run_retry_reuses_same_transaction_row():
    air = FakeAirtable()
    first = run_hosted_dry_run(air, attempt_label="fixture attempt 1")
    second = run_hosted_dry_run(air, attempt_label="fixture attempt 2")

    assert first["transaction_record_id"] == second["transaction_record_id"]
    assert len(air.tables[SCRIBE_TRANSACTIONS_TABLE]) == 1
    assert len(air.tables[EVENTS_TABLE]) == 19


def test_hosted_dry_run_fails_closed_if_current_scene_is_ambiguous():
    air = FakeAirtable()
    air.tables[CURRENT_SCENE_TABLE].append(copy.deepcopy(air.tables[CURRENT_SCENE_TABLE][0]))

    with pytest.raises(RuntimeError, match="exactly one Current Scene"):
        run_hosted_dry_run(air, attempt_label="fixture attempt")

    assert not air.tables[SCRIBE_TRANSACTIONS_TABLE]
    assert len(air.tables[EVENTS_TABLE]) == 19


def test_hosted_dry_run_fails_closed_on_duplicate_transaction_key():
    air = FakeAirtable()
    duplicate = {"id": "rec-dup-1", "fields": {TX_F["key"]: HOSTED_DRY_RUN_KEY}}
    air.tables[SCRIBE_TRANSACTIONS_TABLE] = [copy.deepcopy(duplicate), {"id": "rec-dup-2", "fields": {TX_F["key"]: HOSTED_DRY_RUN_KEY}}]

    with pytest.raises(RuntimeError, match="resolved more than once"):
        run_hosted_dry_run(air, attempt_label="fixture attempt")

    assert len(air.tables[EVENTS_TABLE]) == 19
