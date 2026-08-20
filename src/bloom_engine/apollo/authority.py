from __future__ import annotations

import hashlib
import json
import re
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any, Protocol

from bloom_engine.apollo.models import (
    CompiledVisualJob,
    CompiledVisualRequest,
    VisualJobRequest,
    VisualPackDefinition,
    VisualReferenceAuthority,
    VisualSubjectIdentity,
    VisualSubjectKind,
)
from bloom_engine.apollo.packs import PACKS_BY_SUBJECT

SAGA_ENTITIES = "tblUGacqeNEhBgB30"
ENTITY_ALIASES = "tbl2Ry6ZRQUwUHcIo"
VISUAL_ASSETS = "tblR8LVRGUEFGS2lX"

ENTITY_F = {
    "key": "fldF9WOyVgzA8CMWm",
    "name": "fldIDTR4spiBIUy4h",
    "type": "fldxTog2pdecZelWY",
    "arc": "fldZxvV1qUYa2U2p4",
    "aliases": "fldNoz18sNb4rWSBn",
    "state": "flds4Kplq44niLxCn",
}
ALIAS_F = {
    "entity_key": "fld8NVH5yqSmbNzxr",
    "alias": "fldAz1uMA1bBNlufB",
    "status": "fldncKBWBlHiTHeLa",
}
ASSET_F = {
    "key": "fldkJGMdmUlVVqCLu",
    "name": "fldPyou5bDkoxqgno",
    "arc": "fldfYhxo2CaqwsUZp",
    "subjects": "fld9BzJ4e9jJl2JDI",
    "type": "fldambDi840eB0cMu",
    "attachment": "fld0cB8AomF9eAFHs",
    "status": "fldvKWE2Sc2KyJ1zB",
    "strength": "fldItxdvTYigaC4Qr",
    "controls": "fldW5ZCmomkkibVaH",
    "not_controls": "fldR8BHiNwbZ53lFV",
    "parent": "fldNXxe3HxnaKbyhF",
    "continuity": "fldxr3taTNYXYAwzN",
}

# These roles are explicit migration mappings for existing approved Florence assets.
# Future subjects should gain a first-class role field rather than rely on guessing.
ROLE_BY_ASSET_KEY = {
    "AH-VA-FLO-001": "FACE_GOLD",
    "AH-VA-FLO-002": "FRONT_BODY_GOLD",
    "AH-VA-FLO-003": "REAR_HAIR_BODY_GOLD",
}


def _norm(value: str) -> str:
    return " ".join(value.casefold().split())


def _split_lines(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    text = str(value).strip()
    if not text:
        return ()
    chunks = re.split(r"[\n;]+", text)
    return tuple(part.strip(" -\t") for part in chunks if part.strip(" -\t"))


def _mentions(query: str, candidate: str) -> bool:
    q = _norm(query)
    c = _norm(candidate)
    if not c:
        return False
    return re.search(rf"(?<![\w]){re.escape(c)}(?![\w])", q) is not None


@dataclass(slots=True)
class AirtableVisualHTTP:
    base_id: str
    token: str
    timeout_seconds: int = 30
    api_base: str = "https://api.airtable.com/v0"

    def list_all(self, table_id: str) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        offset: str | None = None
        while True:
            table = urllib.parse.quote(table_id, safe="")
            params = {"returnFieldsByFieldId": "true"}
            if offset:
                params["offset"] = offset
            url = f"{self.api_base}/{self.base_id}/{table}?" + urllib.parse.urlencode(params)
            req = urllib.request.Request(url, headers={"Authorization": f"Bearer {self.token}"})
            with urllib.request.urlopen(req, timeout=self.timeout_seconds) as response:
                payload = json.loads(response.read().decode("utf-8"))
            records.extend(payload.get("records", []))
            offset = payload.get("offset")
            if not offset:
                return records


class VisualAuthoritySource(Protocol):
    def resolve_subject(self, query: str, kind: VisualSubjectKind, arc: str) -> VisualSubjectIdentity | None: ...
    def list_references(self, subject: VisualSubjectIdentity, arc: str) -> tuple[VisualReferenceAuthority, ...]: ...
    def approved_slots(self, subject_id: str) -> tuple[str, ...]: ...


class AirtableVisualAuthoritySource:
    def __init__(self, client: AirtableVisualHTTP):
        self.client = client

    def resolve_subject(self, query: str, kind: VisualSubjectKind, arc: str) -> VisualSubjectIdentity | None:
        entity_rows = self.client.list_all(SAGA_ENTITIES)
        alias_rows = self.client.list_all(ENTITY_ALIASES)
        aliases_by_key: dict[str, list[str]] = {}
        for row in alias_rows:
            fields = row.get("fields", {})
            key = str(fields.get(ALIAS_F["entity_key"], "")).strip()
            alias = str(fields.get(ALIAS_F["alias"], "")).strip()
            if key and alias:
                aliases_by_key.setdefault(key, []).append(alias)

        expected_type = {
            VisualSubjectKind.CHARACTER: "Character",
            VisualSubjectKind.LOCATION: "Location",
            VisualSubjectKind.OBJECT: "Object",
            VisualSubjectKind.SCENE: "Scene",
        }[kind]
        matches: list[VisualSubjectIdentity] = []
        for row in entity_rows:
            fields = row.get("fields", {})
            key = str(fields.get(ENTITY_F["key"], "")).strip()
            name = str(fields.get(ENTITY_F["name"], "")).strip()
            entity_type = str(fields.get(ENTITY_F["type"], "")).strip()
            row_arc = str(fields.get(ENTITY_F["arc"], "")).strip()
            if entity_type != expected_type or (row_arc and row_arc != arc):
                continue
            aliases = list(_split_lines(fields.get(ENTITY_F["aliases"]))) + aliases_by_key.get(key, [])
            if _norm(query) == _norm(key) or _mentions(query, name) or any(_mentions(query, alias) for alias in aliases):
                matches.append(VisualSubjectIdentity(key, name, kind, str(row.get("id", "")), tuple(dict.fromkeys(aliases))))

        if not matches:
            return None
        unique = {match.stable_id: match for match in matches}
        if len(unique) != 1:
            raise ValueError(f"AMBIGUOUS_VISUAL_SUBJECT:{sorted(unique)}")
        return next(iter(unique.values()))

    def list_references(self, subject: VisualSubjectIdentity, arc: str) -> tuple[VisualReferenceAuthority, ...]:
        output: list[VisualReferenceAuthority] = []
        for row in self.client.list_all(VISUAL_ASSETS):
            fields = row.get("fields", {})
            key = str(fields.get(ASSET_F["key"], "")).strip()
            role = ROLE_BY_ASSET_KEY.get(key)
            if not role:
                continue
            subjects = str(fields.get(ASSET_F["subjects"], ""))
            if not _mentions(subjects, subject.display_name):
                continue
            row_arc = str(fields.get(ASSET_F["arc"], "")).strip()
            if row_arc and row_arc != arc:
                continue
            attachments = fields.get(ASSET_F["attachment"]) or []
            first = attachments[0] if isinstance(attachments, list) and attachments else {}
            output.append(VisualReferenceAuthority(
                asset_key=key,
                asset_name=str(fields.get(ASSET_F["name"], key)),
                subject_name=subject.display_name,
                role=role,
                uri=str(first.get("url", "")).strip() or None,
                controls=_split_lines(fields.get(ASSET_F["controls"])),
                does_not_control=_split_lines(fields.get(ASSET_F["not_controls"])),
                status=str(fields.get(ASSET_F["status"], "")),
                reference_strength=str(fields.get(ASSET_F["strength"], "")),
                record_id=str(row.get("id", "")),
                width=int(first["width"]) if isinstance(first, dict) and first.get("width") else None,
                height=int(first["height"]) if isinstance(first, dict) and first.get("height") else None,
            ))
        return tuple(output)

    def approved_slots(self, subject_id: str) -> tuple[str, ...]:
        # Visual Assets does not yet have a first-class production-slot field.
        # Fail closed rather than infer approval from filenames or prose.
        return ()


class ApolloVisualAuthorityCompiler:
    def __init__(self, source: VisualAuthoritySource, packs: dict[str, VisualPackDefinition] | None = None):
        self.source = source
        self.packs = packs or PACKS_BY_SUBJECT

    def compile(self, request: VisualJobRequest) -> CompiledVisualRequest:
        subject = self.source.resolve_subject(request.subject_query, request.subject_kind, request.arc)
        if subject is None:
            raise ValueError(f"VISUAL_SUBJECT_NOT_RESOLVED:{request.subject_query}")
        pack = self.packs.get(subject.stable_id)
        if pack is None:
            raise ValueError(f"VISUAL_PACK_NOT_REGISTERED:{subject.stable_id}")
        references = self.source.list_references(subject, request.arc)
        by_role = {ref.role: ref for ref in references}
        if len(by_role) != len(references):
            raise ValueError("AMBIGUOUS_VISUAL_AUTHORITY_ROLE")
        approved = set(self.source.approved_slots(subject.stable_id))

        definitions = list(pack.jobs)
        if request.request_kind.value == "SINGLE_ASSET":
            if not request.output_type:
                raise ValueError("VISUAL_SINGLE_ASSET_OUTPUT_TYPE_REQUIRED")
            definitions = [job for job in definitions if job.output_type == request.output_type]
            if not definitions:
                raise ValueError(f"VISUAL_OUTPUT_TYPE_NOT_REGISTERED:{request.output_type}")

        jobs: list[CompiledVisualJob] = []
        warnings: list[str] = []
        for index, definition in enumerate(sorted(definitions, key=lambda job: job.priority), start=1):
            missing: list[str] = []
            selected: list[VisualReferenceAuthority] = []
            for role in definition.required_reference_roles:
                ref = by_role.get(role)
                if ref is None:
                    missing.append(f"REFERENCE:{role}")
                elif not ref.has_image:
                    missing.append(f"MISSING_ATTACHMENT:{ref.asset_key}")
                else:
                    selected.append(ref)
            for dep in definition.approved_dependencies:
                if dep not in approved:
                    missing.append(f"APPROVED_SLOT:{dep}")
            if missing:
                warnings.append(f"{definition.output_type}: {', '.join(missing)}")
            jobs.append(CompiledVisualJob(
                job_key=f"{pack.key}::{index:02d}::{definition.output_type}",
                arc=request.arc,
                subject_id=subject.stable_id,
                subject_name=subject.display_name,
                subject_kind=subject.kind,
                output_type=definition.output_type,
                prompt=definition.prompt,
                references=tuple(selected),
                hard_gates=definition.hard_gates,
                soft_criteria=definition.soft_criteria,
                style_rules=definition.style_rules,
                anti_drift=definition.anti_drift,
                open_fields=definition.open_fields,
                max_iterations=max(1, min(request.max_iterations, 6)),
                missing_dependencies=tuple(missing),
            ))

        digest = hashlib.sha256(
            f"{request.arc}|{subject.stable_id}|{request.command}|{request.request_kind.value}|{request.output_type or 'PACK'}".encode()
        ).hexdigest()[:16]
        return CompiledVisualRequest(
            request_key=f"VIS-RUN::{subject.stable_id}::{digest}",
            subject=subject,
            jobs=tuple(jobs),
            warnings=tuple(warnings),
        )
