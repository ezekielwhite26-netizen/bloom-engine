from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Protocol, Sequence

from bloom_engine.api.models import RuntimePreviewBody
from bloom_engine.pantheon.protocol import CoreRequest
from bloom_engine.pantheon.registry import owner_for
from bloom_engine.runtime.models import RuntimeQuery, SceneRequest


class IntentBuildError(ValueError):
    """The untrusted request cannot be translated without inventing authority."""


@dataclass(frozen=True, slots=True)
class QueryTemplate:
    predicate: str
    subject_fields: Sequence[str] = ()
    input_fields: Sequence[str] = ()
    required_for_request: bool = True
    fact_keys: Sequence[str] = ()


class AuthoritativeIntentCatalog(Protocol):
    """Server-owned mapping from bounded intent to sovereign questions."""

    def templates_for(self, command: str) -> Sequence[QueryTemplate]:
        ...


@dataclass(frozen=True, slots=True)
class StaticIntentCatalog:
    """Small explicit catalog; unsupported commands fail closed.

    This is deliberately not an LLM classifier. Expanding the catalog is a
    reviewed server-side change because each template determines which
    sovereign owners are consulted and which facts may enter a Context Packet.
    """

    templates: Mapping[str, Sequence[QueryTemplate]]

    def templates_for(self, command: str) -> Sequence[QueryTemplate]:
        normalized = " ".join(command.strip().lower().split())
        matches = [value for key, value in self.templates.items() if normalized == key]
        if len(matches) != 1:
            raise IntentBuildError("unsupported or ambiguous Ama intent")
        return tuple(matches[0])


DEFAULT_PREVIEW_CATALOG = StaticIntentCatalog(
    templates={
        "can this actor perform passage here": (
            QueryTemplate(
                predicate="magic.passage_eligibility",
                subject_fields=("requested_actor_ref",),
                input_fields=("requested_target_location_ref", "requested_object_ref"),
                required_for_request=True,
                fact_keys=("passage_eligibility",),
            ),
        ),
        "preview travel to target location": (
            QueryTemplate(
                predicate="travel.feasibility",
                subject_fields=("requested_actor_ref",),
                input_fields=("requested_target_location_ref",),
                required_for_request=True,
                fact_keys=("travel_feasibility",),
            ),
        ),
        "preview object use": (
            QueryTemplate(
                predicate="object.usability",
                subject_fields=("requested_object_ref",),
                input_fields=("requested_actor_ref",),
                required_for_request=True,
                fact_keys=("object_usability",),
            ),
        ),
    }
)


@dataclass(frozen=True, slots=True)
class CatalogAmaRequestBuilder:
    catalog: AuthoritativeIntentCatalog = DEFAULT_PREVIEW_CATALOG

    def build_preview(self, body: RuntimePreviewBody) -> SceneRequest:
        if body.mode != "DRY_RUN":
            raise IntentBuildError("external Ama preview is DRY_RUN only")

        templates = self.catalog.templates_for(body.command)
        queries: list[RuntimeQuery] = []
        for template in templates:
            # Validate ownership now; zero or multiple owners is infrastructure/config error.
            owner_for(template.predicate)
            subject_refs = tuple(self._required_value(body, name) for name in template.subject_fields)
            inputs = {name: self._required_value(body, name) for name in template.input_fields}
            queries.append(
                RuntimeQuery(
                    request=CoreRequest(
                        predicate=template.predicate,
                        subject_refs=subject_refs,
                        inputs=inputs,
                        evidence=(),
                        permission_mode="READ",
                    ),
                    required_for_request=template.required_for_request,
                    fact_keys=tuple(template.fact_keys),
                )
            )

        return SceneRequest(
            arc=body.arc,
            command=body.command,
            queries=tuple(queries),
            mode="DRY_RUN",
            realization="PREVIEW",
            authorization_token=None,
            protected_player_domains=(),
        )

    @staticmethod
    def _required_value(body: RuntimePreviewBody, field_name: str) -> str:
        value = getattr(body, field_name, None)
        if not isinstance(value, str) or not value.strip():
            raise IntentBuildError(f"intent requires {field_name}")
        return value.strip()
