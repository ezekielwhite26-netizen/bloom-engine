from __future__ import annotations

import unicodedata
from typing import Any, Sequence

from bloom_engine.runtime import manuscript as _manuscript


ENTITY_ALIASES_TABLE = "tbl2Ry6ZRQUwUHcIo"
ALIAS_F = {
    "entity_key": "fld8NVH5yqSmbNzxr",
    "alias": "fldAz1uMA1bBNlufB",
    "arc": "fldUEmdl9FjYYHisG",
    "status": "fldncKBWBlHiTHeLa",
    "entity": "fld2RsD9RDRAE5dte",
}
TARGET_ENTITY_FIELDS = {
    "characters": "fld5f22G49B4HofYR",
    "locations": "fldeWmqTrHhq5QCWm",
}
TARGET_NAME_FIELDS = {
    "characters": _manuscript.F["characters"]["name"],
    "locations": _manuscript.F["location"]["name"],
}

_TRANSLATE = str.maketrans(
    {
        "\u2018": "'",
        "\u2019": "'",
        "\u02bc": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\u2013": "-",
        "\u2014": "-",
        "\u2212": "-",
    }
)


def normalize_identity_text(value: str) -> str:
    """Normalize harmless typography without weakening exact identity matching."""
    normalized = unicodedata.normalize("NFKC", value).translate(_TRANSLATE)
    return " ".join(normalized.casefold().split())


def _text(value: Any) -> str:
    return _manuscript._text(value)


def _link_names(value: Any) -> set[str]:
    if not isinstance(value, list):
        return set()
    names: set[str] = set()
    for item in value:
        if isinstance(item, dict):
            name = str(item.get("name") or "").strip()
            if name:
                names.add(name)
        elif item:
            names.add(str(item).strip())
    return names


def _same_arc(record_arc: str, requested_arc: str) -> bool:
    return not record_arc or record_arc == requested_arc or record_arc in {
        "Project-wide",
        "BLOOM Core / Cross-Project",
    }


class AliasAwareManuscriptContextRepository(_manuscript.ManuscriptContextRepository):
    """Resolve manuscript request names by canonical name or explicit current stable alias.

    This adapter never fuzzy-matches, never drops middle names heuristically, and never creates
    identity. An alias must already be registered against a stable Saga Entity. Typography-only
    punctuation differences are normalized before exact comparison.
    """

    def _resolve_one(self, *, table: str, requested_name: str, arc: str) -> tuple[str, str]:
        rows = self.client.list_all(_manuscript.T[table])
        name_field = TARGET_NAME_FIELDS[table]
        target_entity_field = TARGET_ENTITY_FIELDS[table]
        wanted = normalize_identity_text(requested_name)

        canonical_matches = [
            row
            for row in rows
            if normalize_identity_text(_text(row.get("fields", {}).get(name_field))) == wanted
        ]
        if len(canonical_matches) == 1:
            canonical = _text(canonical_matches[0].get("fields", {}).get(name_field)).strip()
            return canonical, "CANONICAL"
        if len(canonical_matches) > 1:
            return requested_name, "AMBIGUOUS_CANONICAL"

        alias_rows = self.client.list_all(ENTITY_ALIASES_TABLE)
        alias_matches: list[dict[str, Any]] = []
        for alias_row in alias_rows:
            fields = alias_row.get("fields", {})
            if normalize_identity_text(_text(fields.get(ALIAS_F["alias"]))) != wanted:
                continue
            if _text(fields.get(ALIAS_F["status"])).strip() != "Current":
                continue
            if not _same_arc(_text(fields.get(ALIAS_F["arc"])).strip(), arc):
                continue
            alias_matches.append(alias_row)

        target_matches: list[dict[str, Any]] = []
        for alias_row in alias_matches:
            fields = alias_row.get("fields", {})
            stable_keys = set()
            entity_key = _text(fields.get(ALIAS_F["entity_key"])).strip()
            if entity_key:
                stable_keys.add(entity_key)
            stable_keys.update(_link_names(fields.get(ALIAS_F["entity"])))
            if not stable_keys:
                continue
            for row in rows:
                target_keys = _link_names(row.get("fields", {}).get(target_entity_field))
                if target_keys & stable_keys:
                    target_matches.append(row)

        unique_by_id = {str(row.get("id")): row for row in target_matches}
        if len(unique_by_id) == 1:
            row = next(iter(unique_by_id.values()))
            canonical = _text(row.get("fields", {}).get(name_field)).strip()
            return canonical, "REGISTERED_ALIAS"
        if len(unique_by_id) > 1:
            return requested_name, "AMBIGUOUS_ALIAS"
        return requested_name, "UNRESOLVED"

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
        resolved_characters = [self._resolve_one(table="characters", requested_name=name, arc=arc) for name in character_names]
        resolved_locations = [self._resolve_one(table="locations", requested_name=name, arc=arc) for name in location_names]

        context = super().build(
            arc=arc,
            command=command,
            scene_or_chapter=scene_or_chapter,
            temporal_scope=temporal_scope,
            character_names=tuple(name for name, _ in resolved_characters),
            location_names=tuple(name for name, _ in resolved_locations),
        )
        context["identity_resolution"] = {
            "characters": [
                {"requested": requested, "canonical": canonical, "mode": mode}
                for requested, (canonical, mode) in zip(character_names, resolved_characters)
            ],
            "locations": [
                {"requested": requested, "canonical": canonical, "mode": mode}
                for requested, (canonical, mode) in zip(location_names, resolved_locations)
            ],
            "policy": "Canonical exact match or explicit Current Entity Alias only; typography normalization is non-semantic; no fuzzy matching.",
        }
        return context


def install_alias_aware_manuscript_repository() -> None:
    """Install the identity adapter at the existing manuscript repository seam."""
    _manuscript._norm = normalize_identity_text
    _manuscript.ManuscriptContextRepository = AliasAwareManuscriptContextRepository
