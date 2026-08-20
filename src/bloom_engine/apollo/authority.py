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
from bloom_engine.apollo.packs import PACKS_BY_SUBJECT, generic_character_production_pack

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
    "subject_entities": "fldqCp7EF233chehy",
    "type": "fldambDi840eB0cMu",
    "attachment": "fld0cB8AomF9eAFHs",
    "status": "fldvKWE2Sc2KyJ1zB",
    "strength": "fldItxdvTYigaC4Qr",
    "controls": "fldW5ZCmomkkibVaH",
    "not_controls": "fldR8BHiNwbZ53lFV",
    "parent": "fldNXxe3HxnaKbyhF",
    "continuity": "fldxr3taTNYXYAwzN",
    "authority_roles": "fldsHT2et8d6AZosf",
    "authority_scope": "fldOdVVEwNa7xT0Q6",
    "production_slot": "fldrpOM8fkP4GINBs",
}

APPROVED_ASSET_STATUSES = {"Approved Anchor", "Approved Secondary"}


def _norm(value: str) -> str:
    return " ".join(value.casefold().split())


def _arc_matches(authority_arc: str, request_arc: str) -> bool:
    """Match an authority arc to the same arc or an explicit child arc path."""

    authority = _norm(authority_arc)
    requested = _norm(request_arc)
    if not authority:
        return True
    if authority == requested:
        return True
    return requested.startswith(authority + " / ")


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


def _select_name(value: Any) -> str:
    if isinstance(value, dict):
        return str(value.get("name") or "").strip()
    return str(value or "").strip()


def _select_names(value: Any) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    names: list[str] = []
    for item in value:
        name = _select_name(item)
        if name:
            names.append(name)
    return tuple(names)


def _linked_record_ids(value: Any) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    ids: list[str] = []
    for item in value:
        if isinstance(item, str) and item.startswith("rec"):
            ids.append(item)
        elif isinstance(item, dict):
            candidate = str(item.get("id") or "")
            if candidate.startswith("rec"):
                ids.append(candidate)
    return tuple(ids)


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
    def approved_slots(self, subject: VisualSubjectIdentity, arc: str) -> tuple[str, ...]: ...


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
            entity_type = _select_name(fields.get(ENTITY_F["type"]))
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

    @staticmethod
    def _asset_matches_subject(fields: dict[str, Any], subject: VisualSubjectIdentity) -> bool:
        links = _linked_record_ids(fields.get(ASSET_F["subject_entities"]))
        if links:
            return subject.record_id in links
        subjects = str(fields.get(ASSET_F["subjects"], ""))
        return _mentions(subjects, subject.display_name)

    @classmethod
    def _asset_in_authority_scope(cls, fields: dict[str, Any], subject: VisualSubjectIdentity, arc: str) -> bool:
        scope = _select_name(fields.get(ASSET_F["authority_scope"])) or "SUBJECT"
        row_arc = str(fields.get(ASSET_F["arc"], "")).strip()
        if scope == "GLOBAL":
            return True
        if scope == "ARC":
            return _arc_matches(row_arc, arc)
        if row_arc and not _arc_matches(row_arc, arc):
            return False
        return cls._asset_matches_subject(fields, subject)

    def list_references(self, subject: VisualSubjectIdentity, arc: str) -> tuple[VisualReferenceAuthority, ...]:
        output: list[VisualReferenceAuthority] = []
        for row in self.client.list_all(VISUAL_ASSETS):
            fields = row.get("fields", {})
            if not self._asset_in_authority_scope(fields, subject, arc):
                continue
            roles = _select_names(fields.get(ASSET_F["authority_roles"]))
            if not roles:
                continue
            status = _select_name(fields.get(ASSET_F["status"]))
            if status not in APPROVED_ASSET_STATUSES:
                continue
            key = str(fields.get(ASSET_F["key"], "")).strip()
            attachments = fields.get(ASSET_F["attachment"]) or []
            first = attachments[0] if isinstance(attachments, list) and attachments else {}
            for role in roles:
                output.append(VisualReferenceAuthority(
                    asset_key=key,
                    asset_name=str(fields.get(ASSET_F["name"], key)),
                    subject_name=subject.display_name,
                    role=role,
                    uri=str(first.get("url", "")).strip() or None,
                    controls=_split_lines(fields.get(ASSET_F["controls"])),
                    does_not_control=_split_lines(fields.get(ASSET_F["not_controls"])),
                    status=status,
                    reference_strength=_select_name(fields.get(ASSET_F["strength"])),
                    record_id=str(row.get("id", "")),
                    width=int(first["width"]) if isinstance(first, dict) and first.get("width") else None,
                    height=int(first["height"]) if isinstance(first, dict) and first.get("height") else None,
                ))
        return tuple(output)

    def approved_slots(self, subject: VisualSubjectIdentity, arc: str) -> tuple[str, ...]:
        slots: list[str] = []
        for row in self.client.list_all(VISUAL_ASSETS):
            fields = row.get("fields", {})
            if not self._asset_matches_subject(fields, subject):
                continue
            row_arc = str(fields.get(ASSET_F["arc"], "")).strip()
            if row_arc and not _arc_matches(row_arc, arc):
                continue
            if _select_name(fields.get(ASSET_F["status"])) not in APPROVED_ASSET_STATUSES:
                continue
            slot = str(fields.get(ASSET_F["production_slot"], "")).strip()
            if slot:
                slots.append(slot)
        return tuple(dict.fromkeys(slots))


class ApolloVisualAuthorityCompiler:
    def __init__(self, source: VisualAuthoritySource, packs: dict[str, VisualPackDefinition] | None = None):
        self.source = source
        self.packs = packs or PACKS_BY_SUBJECT

    def _pack_for_subject(self, subject: VisualSubjectIdentity) -> VisualPackDefinition:
        explicit = self.packs.get(subject.stable_id)
        if explicit is not None:
            return explicit
        if subject.kind is VisualSubjectKind.CHARACTER:
            return generic_character_production_pack(subject.stable_id)
        raise ValueError(f"VISUAL_PACK_NOT_REGISTERED:{subject.stable_id}")

    @staticmethod
    def _one_authority(refs_by_role: dict[str, list[VisualReferenceAuthority]], role: str) -> VisualReferenceAuthority | None:
        matches = refs_by_role.get(role, [])
        if not matches:
            return None
        if len(matches) != 1:
            keys = sorted(ref.asset_key for ref in matches)
            raise ValueError(f"AMBIGUOUS_VISUAL_AUTHORITY_ROLE:{role}:{keys}")
        return matches[0]

    def compile(self, request: VisualJobRequest) -> CompiledVisualRequest:
        subject = self.source.resolve_subject(request.subject_query, request.subject_kind, request.arc)
        if subject is None:
            raise ValueError(f"VISUAL_SUBJECT_NOT_RESOLVED:{request.subject_query}")
        pack = self._pack_for_subject(subject)
        references = self.source.list_references(subject, request.arc)
        refs_by_role: dict[str, list[VisualReferenceAuthority]] = {}
        for ref in references:
            refs_by_role.setdefault(ref.role, []).append(ref)
        approved = set(self.source.approved_slots(subject, request.arc))

        definitions = list(pack.jobs)
        if request.request_kind.value == "SINGLE_ASSET":
            if not request.output_type:
                raise ValueError("VISUAL_SINGLE_ASSET_OUTPUT_TYPE_REQUIRED")
            definitions = [job for job in definitions if job.output_type == request.output_type]
            if not definitions:
                raise ValueError(f"VISUAL_OUTPUT_TYPE_NOT_REGISTERED:{request.output_type}")

        # Secondary/mood/reference roles may legitimately have several approved
        # records. They are not production authority unless a registered job asks
        # for that role. Ambiguity therefore fails closed only when the pack would
        # actually consume the duplicated authority.
        consumed_roles = {
            role
            for definition in definitions
            for role in (*definition.required_reference_roles, *definition.optional_reference_roles)
        }
        ambiguous = sorted(role for role in consumed_roles if len(refs_by_role.get(role, [])) > 1)
        if ambiguous:
            details = {role: sorted(ref.asset_key for ref in refs_by_role[role]) for role in ambiguous}
            raise ValueError(f"AMBIGUOUS_VISUAL_AUTHORITY_ROLE:{details}")

        jobs: list[CompiledVisualJob] = []
        warnings: list[str] = []
        for index, definition in enumerate(sorted(definitions, key=lambda job: job.priority), start=1):
            missing: list[str] = []
            selected: list[VisualReferenceAuthority] = []
            for role in definition.required_reference_roles:
                ref = self._one_authority(refs_by_role, role)
                if ref is None:
                    missing.append(f"REFERENCE:{role}")
                elif not ref.has_image:
                    missing.append(f"MISSING_ATTACHMENT:{ref.asset_key}")
                else:
                    selected.append(ref)
            for role in definition.optional_reference_roles:
                ref = self._one_authority(refs_by_role, role)
                if ref is None:
                    continue
                if not ref.has_image:
                    warnings.append(f"{definition.output_type}: OPTIONAL_MISSING_ATTACHMENT:{ref.asset_key}")
                    continue
                selected.append(ref)
            selected = list({ref.record_id: ref for ref in selected}.values())
            for dep in definition.approved_dependencies:
                if dep not in approved:
                    missing.append(f"APPROVED_SLOT:{dep}")
            if missing:
                warnings.append(f"{definition.output_type}: {', '.join(missing)}")
            jobs.append(CompiledVisualJob(
                job_key=f"{pack.key}::{index:02d}::{definition.output_type}",
                arc=request.arc,
                subject_id=subject.stable_id,
                subject_record_id=subject.record_id,
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
