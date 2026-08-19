from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from bloom_engine.hecate.models import FocusBond, MagicForm, MagicalCondition, MagicProfile
from bloom_engine.hecate.store import InMemoryHecateStore


# Exact live Airtable table IDs in the BLOOM Engine base.
MAGIC_FORMS_TABLE = "tblIusgSCw9OI7kv9"
MAGIC_PROFILES_TABLE = "tbl3AhVCfyTAVXYtC"
FOCUS_BONDS_TABLE = "tbl3LvrdgEvDMYOfg"
MAGICAL_CONDITIONS_TABLE = "tblVekSeQKOJOY7Ot"


# Field-name -> field-ID mappings. These make connector snapshots using
# cellValuesByFieldId deterministic while also allowing normal REST-style
# records keyed by human-readable field names.
FORM_FIELDS: Mapping[str, str] = {
    "Magic Form Key": "fld45Hpr1qg2aiMQH",
    "Canonical Name": "fldCnGxg9KWAEFTDi",
    "Capability Statement": "fldViW7pE3nknrYAq",
    "Possibility / Target Preconditions": "fldPbLfdMcTKDgyfh",
    "Required Structure / Conditions": "fld2vnwfRP3C9YxT8",
    "Focus Requirements / Roles": "fld1GeZD0TgR42A7M",
    "Hard Limits / Prohibitions": "fldJ4xluUJ4JW84M0",
    "Cost / Heat / Consequence Model": "fld2JJmmETj54axO7",
    "Failure / Degraded Behavior": "fldxpKUG7GJSSX8DW",
    "Clearing / Release Requirements": "fldF6xBBEOfxtIZ5j",
    "Resolver Readiness": "fldYP4gZGlk20K0eq",
    "Source / Provenance": "fldBguuZ5O47gffcx",
    "Evidence Notes": "fldVGA7HswNBd7NLa",
    "Do Not Infer": "fldvJviqRreNOzcz2",
}

PROFILE_FIELDS: Mapping[str, str] = {
    "Magic Profile Key": "flduA8NQAjjygYMB2",
    "Character": "fldBt9Kw2SN4fCZMZ",
    "Character Entity": "fldtcIVcPThrH17ep",
    "Primary Signature / Form": "fldvogs2xoN6k0Bx1",
    "Additional Learned Forms": "fldmQhtUwK9fUXozw",
    "Capability Envelope": "fldBLRIjuGmX7X2o1",
    "General Requirements": "fldHE249kbMeDS01b",
    "Known Hard Limits": "fld2jLxPr5q69YVxC",
    "Current Magical Constraints": "fld41oiui1YtpCN50",
    "Do Not Infer / Open": "fldyU3HzHxQme6lIR",
    "Resolver Readiness": "fldYU0mlIswikBkzh",
    "Source / Provenance": "fldYPXEtRjEWIbRjR",
}

FOCUS_FIELDS: Mapping[str, str] = {
    "Focus Bond Key": "fldNcJT4T0guLFMbj",
    "Practitioner": "fldI3nDruhKJAjZKd",
    "Practitioner Entity": "fldnOylIgrju44d8V",
    "Focus Name / Description": "fldouMkB9g6p72Vsr",
    "Object Entity": "fldO1A7ps6H6xDpCp",
    "Related Forms": "fldaQKgq4w2UEbmhS",
    "Bond State": "fldJtbxCwV6qcDMxX",
    "Focus Function / Externalized Role": "fld0UXExoNkgqxif6",
    "Proven Magical Use": "fldkGCQ6pUAwOpx2M",
    "Known Limits / Negative Evidence": "fldSjSLodQ3YSSnni",
    "Resolver Readiness": "fldGvSTR1jMuyieUi",
    "Source / Provenance": "fldyaKn9rPFx5y9gh",
}

CONDITION_FIELDS: Mapping[str, str] = {
    "Magical Condition Key": "fldPBgWW2LC9QpBmw",
    "Subject Name": "fldXrlNVruzitWK24",
    "Character": "fldGxelWUAck1AKDH",
    "Object": "fldq2fRLXs5uiUVFF",
    "Location": "fldR0ddAQxE046HJ3",
    "Condition State": "fldZ3x0HnJ6cpkzkV",
    "Current Effect / Value": "fldrZZslMoyTNG1WM",
    "Requirements to Maintain": "fldVUqtzJ0l4UzJH9",
    "Costs / Consequences": "fldQtk7tonen3WdMD",
    "Resolution / Clearing Condition": "fldYb243iJRXKFXvK",
    "Hard Limits / Do Not Infer": "fldNS1Mt9XjGt5HxD",
    "Resolver Readiness": "fldz5ndH9VeMGzIIM",
    "Source / Provenance": "fldUdBpxSIKyiZj7I",
}


class AirtableHecateDataError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class AirtableSnapshot:
    """Read-only normalized input from an Airtable fetch layer.

    The future runtime adapter may fetch however it likes (REST, connector,
    cache). HECATE receives only a bounded snapshot and never owns network or
    credential policy.
    """

    tables: Mapping[str, Sequence[Mapping[str, Any]]]

    def rows(self, table_id: str) -> Sequence[Mapping[str, Any]]:
        return self.tables.get(table_id, ())


def _field_view(record: Mapping[str, Any], mapping: Mapping[str, str]) -> dict[str, Any]:
    if "fields" in record and isinstance(record["fields"], Mapping):
        source = record["fields"]
        return {name: source.get(name) for name in mapping}
    if "cellValuesByFieldId" in record and isinstance(record["cellValuesByFieldId"], Mapping):
        source = record["cellValuesByFieldId"]
        return {name: source.get(field_id) for name, field_id in mapping.items()}
    # Also accept an already-normalized field dictionary for fixture/import use.
    return {name: record.get(name) for name in mapping}


def _text(value: Any) -> str:
    return str(value).strip() if value is not None else ""


def _tuple_if_text(*values: Any) -> tuple[str, ...]:
    return tuple(text for value in values if (text := _text(value)))


def _select_name(value: Any) -> str:
    if isinstance(value, Mapping):
        return _text(value.get("name"))
    return _text(value)


def _linked_names(value: Any) -> tuple[str, ...]:
    if not value:
        return ()
    if isinstance(value, str):
        return (_text(value),) if _text(value) else ()
    result: list[str] = []
    if isinstance(value, Sequence):
        for item in value:
            if isinstance(item, Mapping):
                name = _text(item.get("name"))
            else:
                name = _text(item)
            if name:
                result.append(name)
    return tuple(result)


def _first_linked_name(value: Any) -> str:
    names = _linked_names(value)
    return names[0] if names else ""


def _evidence(source: Any, notes: Any = None) -> tuple[Mapping[str, str], ...]:
    items: list[Mapping[str, str]] = []
    if source_text := _text(source):
        items.append({"source": source_text, "fact": "persisted HECATE record provenance"})
    if notes_text := _text(notes):
        items.append({"source": "HECATE persisted evidence notes", "fact": notes_text})
    return tuple(items)


def _insert_unique(mapping: dict[Any, Any], key: Any, value: Any, label: str) -> None:
    if key in mapping:
        raise AirtableHecateDataError(f"duplicate {label} index for {key!r}")
    mapping[key] = value


class AirtableHecateStore(InMemoryHecateStore):
    """HECATE store reconstructed from a bounded persisted Airtable snapshot.

    Unknown/unsupported row states are omitted instead of coerced. In
    particular, a Focus Bond becomes a boolean only for the explicit states
    `Active Focus` and `Explicitly Not Focus`; any other state stays unresolved.
    """

    @classmethod
    def from_snapshot(cls, snapshot: AirtableSnapshot) -> "AirtableHecateStore":
        forms: dict[str, MagicForm] = {}
        profiles: dict[str, MagicProfile] = {}
        focus_bonds: dict[tuple[str, str], FocusBond] = {}
        conditions: dict[str, MagicalCondition] = {}

        for raw in snapshot.rows(MAGIC_FORMS_TABLE):
            f = _field_view(raw, FORM_FIELDS)
            key = _text(f["Magic Form Key"])
            if not key:
                continue
            form = MagicForm(
                key=key,
                name=_text(f["Canonical Name"]),
                capability_statement=_text(f["Capability Statement"]),
                requirements=_tuple_if_text(
                    f["Possibility / Target Preconditions"],
                    f["Required Structure / Conditions"],
                ),
                focus_roles=_tuple_if_text(f["Focus Requirements / Roles"]),
                costs_or_strain=_tuple_if_text(f["Cost / Heat / Consequence Model"]),
                hard_limits=_tuple_if_text(f["Hard Limits / Prohibitions"]),
                clearing_requirements=_tuple_if_text(f["Clearing / Release Requirements"]),
                resolver_readiness=_select_name(f["Resolver Readiness"]) or "PARTIAL",
                evidence=_evidence(f["Source / Provenance"], f["Evidence Notes"]),
                do_not_infer=_tuple_if_text(f["Do Not Infer"]),
            )
            _insert_unique(forms, key, form, "Magic Form")

        for raw in snapshot.rows(MAGIC_PROFILES_TABLE):
            f = _field_view(raw, PROFILE_FIELDS)
            key = _text(f["Magic Profile Key"])
            if not key:
                continue
            practitioner_ref = _first_linked_name(f["Character Entity"])
            if not practitioner_ref:
                # A profile without stable practitioner identity is not safe for
                # machine resolution; do not substitute display-name identity.
                continue
            form_keys = (
                *_linked_names(f["Primary Signature / Form"]),
                *_linked_names(f["Additional Learned Forms"]),
            )
            profile = MagicProfile(
                key=key,
                practitioner_ref=practitioner_ref,
                form_keys=form_keys,
                capability_envelope=_text(f["Capability Envelope"]),
                constraints=_tuple_if_text(
                    f["General Requirements"],
                    f["Known Hard Limits"],
                    f["Current Magical Constraints"],
                ),
                resolver_readiness=_select_name(f["Resolver Readiness"]) or "PARTIAL",
                evidence=_evidence(f["Source / Provenance"]),
                do_not_infer=_tuple_if_text(f["Do Not Infer / Open"]),
            )
            _insert_unique(profiles, practitioner_ref, profile, "Magic Profile practitioner")

        for raw in snapshot.rows(FOCUS_BONDS_TABLE):
            f = _field_view(raw, FOCUS_FIELDS)
            key = _text(f["Focus Bond Key"])
            practitioner_ref = _first_linked_name(f["Practitioner Entity"])
            focus_name = _text(f["Focus Name / Description"])
            state = _select_name(f["Bond State"])
            if not key or not practitioner_ref or not focus_name:
                continue
            if state == "Active Focus":
                is_focus = True
            elif state == "Explicitly Not Focus":
                is_focus = False
            else:
                # Do not turn an unresolved/dormant/other state into either a
                # supported positive or supported negative.
                continue
            object_ref = _first_linked_name(f["Object Entity"]) or None
            bond = FocusBond(
                key=key,
                practitioner_ref=practitioner_ref,
                focus_name=focus_name,
                is_focus=is_focus,
                related_form_keys=_linked_names(f["Related Forms"]),
                roles=_tuple_if_text(f["Focus Function / Externalized Role"]),
                object_ref=object_ref,
                resolver_readiness=_select_name(f["Resolver Readiness"]) or "PARTIAL",
                evidence=_evidence(f["Source / Provenance"], f["Proven Magical Use"]),
                do_not_infer=_tuple_if_text(f["Known Limits / Negative Evidence"]),
            )
            normalized_name = focus_name.casefold()
            _insert_unique(focus_bonds, (practitioner_ref, normalized_name), bond, "Focus Bond")
            if object_ref:
                _insert_unique(focus_bonds, (practitioner_ref, object_ref.casefold()), bond, "Focus Bond object")

        for raw in snapshot.rows(MAGICAL_CONDITIONS_TABLE):
            f = _field_view(raw, CONDITION_FIELDS)
            key = _text(f["Magical Condition Key"])
            if not key:
                continue
            subject_ref = (
                _first_linked_name(f["Character"])
                or _first_linked_name(f["Object"])
                or _first_linked_name(f["Location"])
                or _text(f["Subject Name"])
            )
            readiness = _select_name(f["Resolver Readiness"]) or "PARTIAL"
            effect = _text(f["Current Effect / Value"]) or None
            condition = MagicalCondition(
                key=key,
                subject_ref=subject_ref,
                state=_select_name(f["Condition State"]) or "UNKNOWN",
                effect_summary=effect,
                exact_behavior_known=bool(effect and readiness == "READY"),
                requirements_to_maintain=_tuple_if_text(f["Requirements to Maintain"]),
                costs_or_consequences=_tuple_if_text(f["Costs / Consequences"]),
                clearing_requirements=_tuple_if_text(f["Resolution / Clearing Condition"]),
                evidence=_evidence(f["Source / Provenance"]),
                do_not_infer=_tuple_if_text(f["Hard Limits / Do Not Infer"]),
            )
            _insert_unique(conditions, key, condition, "Magical Condition")

        return cls(
            forms=forms,
            profiles=profiles,
            focus_bonds=focus_bonds,
            conditions=conditions,
        )

    def get_focus_bond(self, practitioner_ref: str, focus_name: str) -> FocusBond | None:
        return self.focus_bonds.get((practitioner_ref, focus_name.casefold()))
