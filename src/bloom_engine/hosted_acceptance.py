from __future__ import annotations

import json
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any, Mapping, Protocol


SCRIBE_TRANSACTIONS_TABLE = "tbllSJiReGQYcpn6q"
EVENTS_TABLE = "tblXERwP6Fuc2ofox"
CURRENT_SCENE_TABLE = "tblipTnwAEA05zs9v"

TX_F = {
    "key": "fldra2sdzTIDbKZIH",
    "arc": "fldSwuPOyimAcUziD",
    "source": "fld2fonXuGgVBWjKU",
    "pre_state": "fld38ENwNft4bFrDn",
    "manifest": "fldRGo8OqzNGzgPuF",
    "authorized": "fld5zb2Dx79IG4JZZ",
    "status": "fld01IZSsnudTJyfz",
    "readback_assertions": "fld8ajfzbuotHV6ue",
    "readback_result": "fldFQfPYgJy58IwV6",
    "created_at": "fldgAwfFb2UpQYgjf",
    "last_attempt": "fldjMct931Kwszi7o",
    "notes": "fldHhHnp9e3u11Uyh",
}
EVENT_F = {
    "stable_id": "fldEKj1Iih2AE7HhM",
    "event_key": "fldb82ATprvlOcqLU",
}
SCENE_F = {
    "key": "fldPweqNPJwM8e5FC",
    "time": "fldyHoqnqks2VaoDg",
    "location": "fld1msBDbtVudey4P",
    "present": "fld5VWkQcajUDmDVh",
    "last_beat": "fldO8KBpPV8DT1m4m",
}

HOSTED_DRY_RUN_KEY = "AMA-TXN-HOSTED-DRYRUN-001"


class AirtableLike(Protocol):
    def list_all(self, table_id: str) -> list[dict[str, Any]]: ...
    def create(self, table_id: str, fields: Mapping[str, Any]) -> dict[str, Any]: ...
    def update(self, table_id: str, record_id: str, fields: Mapping[str, Any]) -> dict[str, Any]: ...


@dataclass(slots=True)
class AirtableHTTP:
    base_id: str
    token: str
    timeout_seconds: int = 20

    def _request(
        self,
        method: str,
        table_id: str,
        payload: Mapping[str, Any] | None = None,
        *,
        offset: str | None = None,
    ) -> dict[str, Any]:
        table = urllib.parse.quote(table_id, safe="")
        url = f"https://api.airtable.com/v0/{self.base_id}/{table}"
        query: dict[str, str] = {}
        if method == "GET":
            # BLOOM stores stable field IDs in its runtime contracts. Airtable's Web API
            # returns field names by default, so fail-safe readback requires this option.
            query["returnFieldsByFieldId"] = "true"
        if offset:
            query["offset"] = offset
        if query:
            url += "?" + urllib.parse.urlencode(query)
        body = None if payload is None else json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            url,
            data=body,
            method=method,
            headers={
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json",
                "User-Agent": "BLOOM-Ama-Runtime/0.1",
            },
        )
        with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
            return json.loads(response.read().decode("utf-8"))

    def list_all(self, table_id: str) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        offset: str | None = None
        while True:
            payload = self._request("GET", table_id, offset=offset)
            records.extend(payload.get("records", []))
            offset = payload.get("offset")
            if not offset:
                return records

    def create(self, table_id: str, fields: Mapping[str, Any]) -> dict[str, Any]:
        payload = self._request("POST", table_id, {"records": [{"fields": dict(fields)}]})
        records = payload.get("records", [])
        if len(records) != 1:
            raise RuntimeError("Airtable create did not return exactly one record.")
        return records[0]

    def update(self, table_id: str, record_id: str, fields: Mapping[str, Any]) -> dict[str, Any]:
        payload = self._request(
            "PATCH",
            table_id,
            {"records": [{"id": record_id, "fields": dict(fields)}]},
        )
        records = payload.get("records", [])
        if len(records) != 1:
            raise RuntimeError("Airtable update did not return exactly one record.")
        return records[0]


def _scene_snapshot(client: AirtableLike) -> tuple[str, dict[str, Any]]:
    scenes = client.list_all(CURRENT_SCENE_TABLE)
    if len(scenes) != 1:
        raise RuntimeError(f"Expected exactly one Current Scene row, found {len(scenes)}.")
    row = scenes[0]
    fields = row.get("fields", {})
    snapshot = {
        "record_id": row.get("id"),
        "scene_key": fields.get(SCENE_F["key"]),
        "time": fields.get(SCENE_F["time"]),
        "location": fields.get(SCENE_F["location"]),
        "present": fields.get(SCENE_F["present"]),
        "last_beat": fields.get(SCENE_F["last_beat"]),
    }
    return json.dumps(snapshot, sort_keys=True, ensure_ascii=False), snapshot


def _event_snapshot(client: AirtableLike) -> tuple[str, list[tuple[Any, Any]]]:
    rows = client.list_all(EVENTS_TABLE)
    identities = sorted(
        (
            r.get("fields", {}).get(EVENT_F["stable_id"]),
            r.get("fields", {}).get(EVENT_F["event_key"]),
        )
        for r in rows
    )
    return json.dumps(identities, sort_keys=True, ensure_ascii=False), identities


def _transaction_matches(client: AirtableLike) -> list[dict[str, Any]]:
    return [
        row
        for row in client.list_all(SCRIBE_TRANSACTIONS_TABLE)
        if row.get("fields", {}).get(TX_F["key"]) == HOSTED_DRY_RUN_KEY
    ]


def run_hosted_dry_run(client: AirtableLike, *, attempt_label: str) -> dict[str, Any]:
    """Exercise only the operational SCRIBE ledger; never write canonical story tables."""

    events_before_digest, events_before = _event_snapshot(client)
    scene_before_digest, scene_before = _scene_snapshot(client)

    manifest = {
        "version": "CLIO-HOSTED-DRYRUN-v0.1",
        "event": None,
        "deltas": [],
        "invalidations": [],
        "readbackAssertions": [
            "Events snapshot is unchanged.",
            "Current Scene snapshot is unchanged.",
            "Persistence Authorized remains false.",
            "Exactly one SCRIBE transaction exists for the hosted dry-run key.",
        ],
    }
    pre_state = {
        "events_count": len(events_before),
        "events_digest": events_before_digest,
        "current_scene": scene_before,
        "current_scene_digest": scene_before_digest,
    }
    base_fields = {
        TX_F["key"]: HOSTED_DRY_RUN_KEY,
        TX_F["arc"]: "Aster Hollow / At the Threshold",
        TX_F["source"]: "HOSTED::ama-runtime.onrender.com / acceptance-only",
        TX_F["pre_state"]: json.dumps(pre_state, sort_keys=True, ensure_ascii=False),
        TX_F["manifest"]: json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False),
        TX_F["authorized"]: False,
        TX_F["status"]: "Dry Run",
        TX_F["readback_assertions"]: "\n".join(manifest["readbackAssertions"]),
        TX_F["last_attempt"]: attempt_label,
        TX_F["notes"]: "Hosted acceptance only. This path has no canonical Event/state writer.",
    }

    matches = _transaction_matches(client)
    if len(matches) > 1:
        raise RuntimeError("Hosted dry-run Transaction Key resolved more than once.")
    if matches:
        transaction = client.update(SCRIBE_TRANSACTIONS_TABLE, str(matches[0]["id"]), base_fields)
    else:
        create_fields = dict(base_fields)
        create_fields[TX_F["created_at"]] = attempt_label
        transaction = client.create(SCRIBE_TRANSACTIONS_TABLE, create_fields)

    events_after_digest, events_after = _event_snapshot(client)
    scene_after_digest, scene_after = _scene_snapshot(client)
    tx_matches = _transaction_matches(client)

    checks = {
        "events_unchanged": events_after_digest == events_before_digest,
        "scene_unchanged": scene_after_digest == scene_before_digest,
        "transaction_exactly_once": len(tx_matches) == 1,
        "transaction_status_dry_run": len(tx_matches) == 1
        and tx_matches[0].get("fields", {}).get(TX_F["status"]) == "Dry Run",
        "persistence_authorized_false": len(tx_matches) == 1
        and not bool(tx_matches[0].get("fields", {}).get(TX_F["authorized"], False)),
    }
    if not all(checks.values()):
        raise RuntimeError(f"Hosted dry-run readback failed: {checks}")

    readback = (
        f"PASS — hosted dry-run readback verified. Events remained {len(events_before)}; "
        f"Current Scene remained {scene_after.get('scene_key')} at {scene_after.get('time')} / "
        f"{scene_after.get('location')}; Transaction Key exists exactly once; "
        "Status=Dry Run; Persistence Authorized=false; no canonical Event/state write occurred."
    )
    client.update(
        SCRIBE_TRANSACTIONS_TABLE,
        str(tx_matches[0]["id"]),
        {TX_F["readback_result"]: readback, TX_F["last_attempt"]: attempt_label},
    )

    return {
        "status": "PASS",
        "transaction_key": HOSTED_DRY_RUN_KEY,
        "transaction_record_id": transaction.get("id"),
        "events_before": len(events_before),
        "events_after": len(events_after),
        "current_scene_key": scene_after.get("scene_key"),
        "checks": checks,
    }
