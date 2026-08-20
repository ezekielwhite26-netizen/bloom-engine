from __future__ import annotations

import hashlib
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Protocol, Sequence


# Existing BLOOM tables. This module is connective authoring infrastructure only.
T = {
    "characters": "tbln3BNS8pbgQSNt8",
    "voice_core": "tblhX7o8os7ridKuL",
    "relationship_cores": "tblXQ6woVndWD7NjH",
    "group_dynamics": "tblAvptDlgIK87jre",
    "locations": "tblozij3g0yWg83D5",
    "location_runtime": "tblGcSdt4wxWbnWnp",
    "writing_corrections": "tblzooviy0Gc6mE5w",
    "writing_qa": "tblVSKZ83WG2jW2cH",
    "gold": "tbllF5snIGAegWAnT",
    "voice_exemplars": "tbliLpoiChKhqcf0k",
    "blueprints": "tbljRchk9RcIZFjM0",
    "writing_runs": "tblZC5j5LQtM8wXKn",
}

F = {
    "characters": {
        "name": "fldFlCoTERehUp8hW", "arc": "fldzfj6YfUoqRzvmQ", "role": "fldEi5K7GR4GDyawQ",
    },
    "voice_core": {
        "key": "fldx4kpGq925r0Xyu", "character": "fld9gtmm8fkiFbyrI", "arc": "fldb0BUgDK6S9lwWp",
        "personality": "fldy6dWvsbLvLx5xn", "emotional_default": "fldv4frB10OcMXuqZ",
        "humor": "fldIeQRxpASHfp9z4", "speech": "fldt4qIdNhPXnAzmS", "register": "fldQQJT3jDDqSG8sa",
        "favorite_moves": "fldN94A1iGetK6z97", "avoided_moves": "fldWVEigX6cyqWugM",
        "body": "fldyX6FLQlq6GAs7l", "silence": "fldgXKoEf2rZT71sT", "contradictions": "fldI6lCJW478ST1lH",
        "do_not_flatten": "fld5URsZ3pVO2zCIC", "neighbors": "fldM4PCGDMAp7y7vp", "differentiate": "fldScIzVlq7W1CzFZ",
        "canon_status": "fldmx1ZKk9W1D8Ld1",
    },
    "relationship": {
        "key": "fldSpH0QpAPyfcDhT", "arc": "fldYDEHULBvSZ2sWW", "a": "fldTmnuUDrHexoTCg", "b": "fldcEXUdvF8jRQWWy",
        "type": "fld9oC5OeruVEknWF", "baseline": "fldPy2dvF5q8tMoHH", "shared_history": "fldzjreGC15FjFxfV",
        "communication": "fldXwH9Oi0LViP9pr", "humor": "fldtdM5doMNQP1lWv", "affection": "fldbP7AW6QcA0c7mx",
        "conflict": "fldrsT8UU7uo2BT7J", "repair": "fldPCerHOksSbDSOq", "boundaries": "fldFjKt4UcCKpTw2F",
        "canon_status": "fldfDQ6mB6YBMJt4C",
    },
    "group": {
        "key": "fldhmP9jRKfV2RC11", "name": "fldbXP2ItOcyhgk64", "arc": "fldLimTcSx93QUFQm", "members": "fldju5pwxz1fxVX3u",
        "baseline": "fldvmJMtwZJeeDaxx", "roles": "fldkY7Cr3gxwf89ou", "conversation": "fld2fEEkTqlu9wLQz",
        "humor": "fldqaHkmJNPEpzWcs", "affection": "fldivYmlebDaJeOLG", "decision": "fldgSu6E9I5uKeTey",
        "conflict": "fldpkQAkGMaNNI2U2", "repair": "fld9NcAdd8NNlPKgh", "rituals": "fldnTi4cHV9B4hvGB",
        "canon_status": "fld9VpwsBByJifxuM",
    },
    "location": {
        "key": "fldoy0Y8lrsbKkkXL", "name": "fldWEQJNZVxpCnSF6", "arc": "fldsTUf2N7OiWZf92", "type": "fldtfJF5UwzW9H80R",
        "parent": "fldYaIZ1HhwDqL2kE", "seen_unseen": "fldxceNkyRkEYhGew", "physical": "fldDiwnN9K3v8G7Uu",
        "social": "fldwIlCjOgQzb0gz6", "access": "fldg1Osj6ERQ8aOS4", "canon_status": "fldYjCf5nF9zUeYQF",
    },
    "location_runtime": {
        "key": "fldGv76Cv4UxqZZ0j", "name": "fldycRgePYOz5UMT7", "arc": "flds85DMpcKLoH0aj", "ordinary": "fld0ND2wSzZ5trpN3",
        "access": "fldk9cNSvaTGTGgOD", "sight": "fldSks9u2awpV8g8a", "sound": "fldyRjjle2L38pvwq",
        "anchors": "fldeIZHcnkyROwyqx", "features": "fld038V9whksqwhqc", "sensory": "fldSwMvqR2wY3DZRF",
        "unknown": "fldkcv6iO4UHeCWZt", "camera": "fldiKA5sB7SrtOwX9", "status": "fldkCJAEQZA006Bbh",
    },
    "correction": {
        "key": "fldh8fKiMtUA0H8rv", "arc": "fldAb2rMif4544vZi", "scope": "fldXOiETUTemIRYrX",
        "preferred": "fldOIycwynfbVuZd9", "strength": "fldXliDSgSE60EnWN", "active": "fldDkZGIY1D6gIeA2",
    },
    "qa": {
        "key": "fldMRgG07ENY2jOHk", "arc": "fldoiNKwAyKXjEDvN", "category": "fldx0szegQgGJZGMr", "scope": "fldaKBat2vvyUns1j",
        "assertion": "fldbVcRN1Lglc4x25", "guidance": "fld500siiqH1pYUHT", "severity": "fld14wpx9g8o5RTZm", "active": "fldINIC9D0jIssMkP",
    },
    "gold": {
        "key": "fldw7BBNGj1rH6zV5", "arc": "fld3M19yQwjYiG2At", "title": "flde1PtESZ16qG2Pz", "passage": "fldhTxfDtnKpHka1g",
        "why": "fldAxa4tkWUTDcOLG", "authoritative": "fldH0YrQN5yJvNv9b", "not_authoritative": "fld3DpEKP7QSJSNWD",
        "approved": "fldF0UBB9svLSKsuG", "status": "fldVPaLPYPtqnT2tc",
    },
    "exemplar": {
        "key": "fldXrv47L2m6mT59j", "arc": "fldJuzupkw7N9WREw", "character_links": "fld4lUlSaeEd3GnjA",
        "context": "fldMhumTmscK8pRVK", "text": "fldmASQ0vDOpr2aXp", "demonstrates": "fldm59RYHMiv4yJZg",
        "limits": "fldimaarpmee5Xadw", "approved": "fldJgqSYYLPiiPmrS", "strength": "fld0F6WsN8gFhCKWf",
    },
    "blueprint": {
        "key": "fldsOjCDwYHAopbwe", "arc": "fldYi6igRyPyIvBz2", "scene": "fld5q1RRRZib21N3x", "intention": "fldTxk1zraarBFXPU",
        "entry": "fldqcYSTLipkJhS7p", "social": "fld6OcAwHNZZkX5Tv", "movement": "fldUUAg64uw9zBYBK", "turn": "fldI8V5jtaK7ECbQD",
        "information": "fldRXcLY35QTZijSC", "protected": "fld6Y5NMxEO8agWUA", "exit": "fldW2rT7me33XkXMx", "status": "fld6GRIF7QXsL2IRz",
    },
    "run": {
        "key": "fld8b16KVA7Ppk1SD", "arc": "fld5yHF0Q94jhPniL", "scene": "flduJn7NTGdCkWJ01", "run_date": "flduSrz6I0dkNyIrk",
        "florence": "fld9NiYrku49j5ytD", "seen": "fldBm8OX5E3NVMejv", "suspect": "fldGzRAhnbsVVQCcz",
        "withheld": "fldH42260mMFA8Yzk", "delta": "fld2vw5kPFjiNjCrd", "committed": "fldfmTOS0hKkuTSFG",
    },
}


class AirtableReadClient(Protocol):
    def list_all(self, table_id: str) -> list[dict[str, Any]]: ...


def _text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, list):
        return "; ".join(filter(None, (_text(item) for item in value)))
    if isinstance(value, dict):
        return _text(value.get("name") or value.get("value") or "")
    return str(value)


def _bool(value: Any) -> bool:
    return value is True or _text(value).strip().lower() == "true"


def _norm(value: str) -> str:
    return " ".join(value.casefold().split())


def _same_arc(record_arc: str, requested_arc: str) -> bool:
    return not record_arc or record_arc == requested_arc or record_arc in {"Project-wide", "BLOOM Core / Cross-Project"}


def _fact_key(table_id: str, record_id: str, field_id: str, value: str) -> str:
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()[:12].upper()
    return f"EVID::{table_id}::{record_id}::{field_id}::{digest}"


def _field_fact(table_id: str, record: dict[str, Any], field_id: str, label: str) -> dict[str, str] | None:
    value = _text(record.get("fields", {}).get(field_id)).strip()
    if not value:
        return None
    return {
        "key": _fact_key(table_id, str(record.get("id", "UNKNOWN")), field_id, value),
        "label": label,
        "value": value,
        "source": f"airtable:{table_id}:{record.get('id', 'UNKNOWN')}:{field_id}",
    }


def _compact(record: dict[str, Any], field_map: dict[str, str], keys: Sequence[str]) -> dict[str, str]:
    fields = record.get("fields", {})
    return {name: _text(fields.get(field_map[name])).strip() for name in keys if _text(fields.get(field_map[name])).strip()}


@dataclass(slots=True)
class ManuscriptContextRepository:
    client: AirtableReadClient

    def _rows(self, table: str) -> list[dict[str, Any]]:
        return self.client.list_all(T[table])

    def _exact_subjects(self, table: str, name_field: str, requested: Sequence[str]) -> tuple[list[dict[str, Any]], list[str]]:
        rows = self._rows(table)
        resolved: list[dict[str, Any]] = []
        missing: list[str] = []
        for name in requested:
            matches = [row for row in rows if _norm(_text(row.get("fields", {}).get(name_field))) == _norm(name)]
            if len(matches) != 1:
                missing.append(name)
            else:
                resolved.append(matches[0])
        return resolved, missing

    def build(
        self,
        *,
        arc: str,
        command: str,
        scene_or_chapter: str,
        temporal_scope: str,
        character_names: Sequence[str],
        location_names: Sequence[str],
    ) -> dict[str, Any]:
        if temporal_scope not in {"CURRENT_SCENE", "HISTORICAL_MANUSCRIPT"}:
            raise ValueError("temporal_scope must be CURRENT_SCENE or HISTORICAL_MANUSCRIPT")

        character_rows, missing_characters = self._exact_subjects("characters", F["characters"]["name"], character_names)
        location_rows, missing_locations = self._exact_subjects("locations", F["location"]["name"], location_names)
        requested_names = {_norm(name) for name in character_names}
        character_record_ids = {str(row.get("id")) for row in character_rows}
        warnings: list[str] = []
        blockers: list[str] = []
        if missing_characters:
            blockers.append("Exact character identity unresolved: " + ", ".join(missing_characters))
        if missing_locations:
            blockers.append("Exact location identity unresolved: " + ", ".join(missing_locations))
        if temporal_scope == "HISTORICAL_MANUSCRIPT":
            warnings.append(
                "Historical manuscript safety: later mutable Character/Relationship/Group state is intentionally omitted. "
                "This packet supplies stable cores/baselines and authoring rules; exact historical mutable state must come from a dated source/Event before use."
            )

        evidence: list[dict[str, str]] = []
        characters: list[dict[str, Any]] = []
        for row in character_rows:
            fields = row.get("fields", {})
            name = _text(fields.get(F["characters"]["name"]))
            characters.append({
                "record_id": row.get("id"),
                "name": name,
                "role": _text(fields.get(F["characters"]["role"])),
            })
            for field_name, label in (("name", "Character name"), ("role", "Narrative role")):
                fact = _field_fact(T["characters"], row, F["characters"][field_name], f"{name} — {label}")
                if fact:
                    evidence.append(fact)

        voice_cores: list[dict[str, Any]] = []
        voice_safe = (
            "key", "character", "personality", "emotional_default", "humor", "speech", "register",
            "favorite_moves", "avoided_moves", "body", "silence", "contradictions", "do_not_flatten", "neighbors", "differentiate", "canon_status",
        )
        for row in self._rows("voice_core"):
            fields = row.get("fields", {})
            char_name = _text(fields.get(F["voice_core"]["character"]))
            if _norm(char_name) not in requested_names or not _same_arc(_text(fields.get(F["voice_core"]["arc"])), arc):
                continue
            compact = _compact(row, F["voice_core"], voice_safe)
            compact["record_id"] = str(row.get("id"))
            voice_cores.append(compact)
            for field_name in voice_safe:
                fact = _field_fact(T["voice_core"], row, F["voice_core"][field_name], f"{char_name} voice core — {field_name}")
                if fact:
                    evidence.append(fact)

        relationship_cores: list[dict[str, Any]] = []
        relationship_safe = ("key", "a", "b", "type", "baseline", "shared_history", "communication", "humor", "affection", "conflict", "repair", "boundaries", "canon_status")
        for row in self._rows("relationship_cores"):
            fields = row.get("fields", {})
            a = _text(fields.get(F["relationship"]["a"]))
            b = _text(fields.get(F["relationship"]["b"]))
            if not {_norm(a), _norm(b)}.issubset(requested_names) or not _same_arc(_text(fields.get(F["relationship"]["arc"])), arc):
                continue
            compact = _compact(row, F["relationship"], relationship_safe)
            compact["record_id"] = str(row.get("id"))
            relationship_cores.append(compact)
            for field_name in relationship_safe:
                fact = _field_fact(T["relationship_cores"], row, F["relationship"][field_name], f"{a} ↔ {b} relationship — {field_name}")
                if fact:
                    evidence.append(fact)

        group_dynamics: list[dict[str, Any]] = []
        group_safe = ("key", "name", "members", "baseline", "roles", "conversation", "humor", "affection", "decision", "conflict", "repair", "rituals", "canon_status")
        if len(requested_names) >= 2:
            for row in self._rows("group_dynamics"):
                fields = row.get("fields", {})
                members = _text(fields.get(F["group"]["members"]))
                member_text = _norm(members)
                if not all(name in member_text for name in requested_names) or not _same_arc(_text(fields.get(F["group"]["arc"])), arc):
                    continue
                compact = _compact(row, F["group"], group_safe)
                compact["record_id"] = str(row.get("id"))
                group_dynamics.append(compact)
                for field_name in group_safe:
                    fact = _field_fact(T["group_dynamics"], row, F["group"][field_name], f"Group dynamic — {field_name}")
                    if fact:
                        evidence.append(fact)

        locations: list[dict[str, Any]] = []
        location_safe = ("key", "name", "type", "parent", "seen_unseen", "physical", "social", "access", "canon_status")
        for row in location_rows:
            fields = row.get("fields", {})
            loc_name = _text(fields.get(F["location"]["name"]))
            compact = _compact(row, F["location"], location_safe)
            compact["record_id"] = str(row.get("id"))
            locations.append(compact)
            for field_name in location_safe:
                fact = _field_fact(T["locations"], row, F["location"][field_name], f"{loc_name} — {field_name}")
                if fact:
                    evidence.append(fact)

        location_runtimes: list[dict[str, Any]] = []
        runtime_safe = ("key", "name", "ordinary", "access", "sight", "sound", "anchors", "features", "sensory", "unknown", "camera", "status")
        requested_locations = {_norm(name) for name in location_names}
        for row in self._rows("location_runtime"):
            fields = row.get("fields", {})
            loc_name = _text(fields.get(F["location_runtime"]["name"]))
            if _norm(loc_name) not in requested_locations or not _same_arc(_text(fields.get(F["location_runtime"]["arc"])), arc):
                continue
            compact = _compact(row, F["location_runtime"], runtime_safe)
            compact["record_id"] = str(row.get("id"))
            location_runtimes.append(compact)
            for field_name in runtime_safe:
                fact = _field_fact(T["location_runtime"], row, F["location_runtime"][field_name], f"{loc_name} runtime — {field_name}")
                if fact:
                    evidence.append(fact)

        corrections: list[dict[str, str]] = []
        for row in self._rows("writing_corrections"):
            fields = row.get("fields", {})
            if not _bool(fields.get(F["correction"]["active"])) or not _same_arc(_text(fields.get(F["correction"]["arc"])), arc):
                continue
            corrections.append(_compact(row, F["correction"], ("key", "scope", "preferred", "strength")))

        qa_rules: list[dict[str, str]] = []
        for row in self._rows("writing_qa"):
            fields = row.get("fields", {})
            if not _bool(fields.get(F["qa"]["active"])) or not _same_arc(_text(fields.get(F["qa"]["arc"])), arc):
                continue
            qa_rules.append(_compact(row, F["qa"], ("key", "category", "scope", "assertion", "guidance", "severity")))

        gold: list[dict[str, str]] = []
        for row in self._rows("gold"):
            fields = row.get("fields", {})
            if not _bool(fields.get(F["gold"]["approved"])) or not _same_arc(_text(fields.get(F["gold"]["arc"])), arc):
                continue
            gold.append(_compact(row, F["gold"], ("key", "title", "passage", "why", "authoritative", "not_authoritative", "status")))

        exemplars: list[dict[str, str]] = []
        for row in self._rows("voice_exemplars"):
            fields = row.get("fields", {})
            linked = fields.get(F["exemplar"]["character_links"]) or []
            linked_ids = {str(item) if not isinstance(item, dict) else str(item.get("id", "")) for item in linked}
            if character_record_ids and not (linked_ids & character_record_ids):
                continue
            if not _bool(fields.get(F["exemplar"]["approved"])) or not _same_arc(_text(fields.get(F["exemplar"]["arc"])), arc):
                continue
            exemplars.append(_compact(row, F["exemplar"], ("key", "context", "text", "demonstrates", "limits", "strength")))

        target = _norm(scene_or_chapter)
        blueprints: list[dict[str, str]] = []
        for row in self._rows("blueprints"):
            fields = row.get("fields", {})
            if not _same_arc(_text(fields.get(F["blueprint"]["arc"])), arc):
                continue
            scene = _norm(_text(fields.get(F["blueprint"]["scene"])))
            if target and scene and target not in scene and scene not in target and "template" not in scene:
                continue
            blueprints.append(_compact(row, F["blueprint"], ("key", "scene", "intention", "entry", "social", "movement", "turn", "information", "protected", "exit", "status")))

        committed_runs: list[dict[str, Any]] = []
        for row in self._rows("writing_runs"):
            fields = row.get("fields", {})
            if _bool(fields.get(F["run"]["committed"])) and _same_arc(_text(fields.get(F["run"]["arc"])), arc):
                committed_runs.append(row)
        committed_runs.sort(key=lambda row: _text(row.get("fields", {}).get(F["run"]["run_date"])), reverse=True)
        if committed_runs:
            latest = committed_runs[0]
            fields = latest.get("fields", {})
            reader_ledger = {
                "source_run_key": _text(fields.get(F["run"]["key"])),
                "florence_epistemic_window": _text(fields.get(F["run"]["florence"])),
                "reader_has_seen": _text(fields.get(F["run"]["seen"])),
                "reader_invited_to_suspect": _text(fields.get(F["run"]["suspect"])),
                "objective_truth_withheld": _text(fields.get(F["run"]["withheld"])),
            }
        else:
            reader_ledger = {
                "source_run_key": None,
                "florence_epistemic_window": "No committed manuscript reader-ledger boundary found.",
                "reader_has_seen": "No committed manuscript reader disclosures found.",
                "reader_invited_to_suspect": "No committed manuscript suspicions found.",
                "objective_truth_withheld": "Resolve from controlling canon; do not infer from absence.",
            }

        status = "BLOCKED" if blockers else ("DEGRADED" if warnings else "COMPLETE")
        return {
            "status": status,
            "arc": arc,
            "command": command,
            "scene_or_chapter": scene_or_chapter,
            "temporal_scope": temporal_scope,
            "story_canon_persisted": False,
            "reader_ledger_committed": False,
            "characters": characters,
            "voice_cores": voice_cores,
            "relationship_cores": relationship_cores,
            "group_dynamics": group_dynamics,
            "locations": locations,
            "location_runtime": location_runtimes,
            "writing_corrections": corrections,
            "writing_qa_rules": qa_rules,
            "approved_gold": gold,
            "approved_voice_exemplars": exemplars,
            "scene_blueprints": blueprints,
            "reader_ledger": reader_ledger,
            "evidence": evidence,
            "allowed_fact_keys": [fact["key"] for fact in evidence],
            "blockers": blockers,
            "warnings": warnings,
            "do_not_infer": [
                "A generated draft is not canon.",
                "A calibration/test draft does not advance reader knowledge.",
                "Safe-to-disclose is not the same as already disclosed.",
                "Historical manuscript mode does not import later mutable state backward.",
                "Facts not represented by supplied evidence require another authoritative source or HUMAN_REVIEW.",
            ],
        }


@dataclass(slots=True)
class ManuscriptReviewSession:
    context_id: str
    allowed_fact_keys: frozenset[str]
    protected_domains: frozenset[str]
    created_at: float
    expires_at: float


@dataclass(slots=True)
class ManuscriptSessionStore:
    ttl_seconds: int = 3600
    _sessions: dict[str, ManuscriptReviewSession] = field(default_factory=dict)

    def issue(self, context: dict[str, Any]) -> ManuscriptReviewSession:
        now = time.time()
        context_id = f"MCTX::{uuid.uuid4()}"
        session = ManuscriptReviewSession(
            context_id=context_id,
            allowed_fact_keys=frozenset(str(key) for key in context.get("allowed_fact_keys", [])),
            protected_domains=frozenset({
                "FLORENCE_PRIVATE_INTERIORITY",
                "FLORENCE_DURABLE_RELATIONSHIP_COMMITMENT",
                "FLORENCE_MAJOR_MAGIC_ETHICS",
                "FLORENCE_MAJOR_COMMITMENT",
            }),
            created_at=now,
            expires_at=now + self.ttl_seconds,
        )
        self._sessions[context_id] = session
        return session

    def get(self, context_id: str) -> ManuscriptReviewSession | None:
        session = self._sessions.get(context_id)
        if session is None:
            return None
        if time.time() > session.expires_at:
            self._sessions.pop(context_id, None)
            return None
        return session

    def clear(self) -> None:
        self._sessions.clear()


def review_manuscript(
    *,
    session: ManuscriptReviewSession,
    phase: str,
    claims: Sequence[dict[str, str]],
    reader_new_subjects: Sequence[str],
    oriented_subjects: Sequence[str],
    reader_ledger_commit_requested: bool,
) -> dict[str, Any]:
    if phase not in {"DRAFT", "FINAL"}:
        raise ValueError("phase must be DRAFT or FINAL")

    findings: list[dict[str, Any]] = []
    for claim in claims:
        kind = str(claim.get("kind", "")).upper()
        key = str(claim.get("key", ""))
        if kind == "PLAYER_COMMITMENT":
            findings.append({
                "category": "AGENCY", "severity": "CRITICAL", "result": "BLOCK",
                "message": "Protected player commitment cannot be authored by manuscript mode.",
                "evidence_refs": [key] if key else [], "responsible_owner": "AUTHOR",
            })
        elif key not in session.allowed_fact_keys:
            findings.append({
                "category": "CANON", "severity": "CRITICAL", "result": "BLOCK",
                "message": f"Draft claim is not supported by the issued authoring evidence: {key or '(missing key)'}",
                "evidence_refs": [key] if key else [], "responsible_owner": "ADRASTEIA",
            })

    oriented = {_norm(name) for name in oriented_subjects}
    missing_orientation = [name for name in reader_new_subjects if _norm(name) not in oriented]
    if missing_orientation:
        findings.append({
            "category": "READER_ORIENTATION", "severity": "WARN", "result": "WARN",
            "message": "Reader-new familiar subject lacks a declared landing/orientation beat: " + ", ".join(missing_orientation),
            "evidence_refs": ["BLOOM-WR-CORR-007", "BLOOM-WR-QA-009"], "responsible_owner": "CALLIOPE",
        })

    if reader_ledger_commit_requested:
        findings.append({
            "category": "EPISTEMICS", "severity": "CRITICAL", "result": "BLOCK",
            "message": "Hosted manuscript preview cannot commit Reader Knowledge Ledger state. Acceptance/promotion remains a separate human-authorized manuscript operation.",
            "evidence_refs": ["BLOOM-WR-QA-011", "BLM-TST-000147"], "responsible_owner": "AUTHOR",
        })

    if any(f["result"] == "BLOCK" for f in findings):
        status = "BLOCKED"
    elif any(f["result"] == "WARN" for f in findings):
        status = "PASS_WITH_WARNINGS"
    else:
        status = "PASS"
        findings.append({
            "category": "CANON", "severity": "HIGH", "result": "PASS",
            "message": "Declared manuscript claims stay within the issued evidence contract. No persistence is authorized.",
            "evidence_refs": [], "responsible_owner": "ADRASTEIA",
        })

    return {
        "status": status,
        "phase": phase,
        "findings": findings,
        "story_canon_persisted": False,
        "reader_ledger_committed": False,
        "replacement_prose": None,
        "editor_contract": "ADRASTEIA diagnoses and routes; CALLIOPE revises prose.",
    }
