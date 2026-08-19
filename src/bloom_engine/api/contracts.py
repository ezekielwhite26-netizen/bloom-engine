from __future__ import annotations

from typing import Protocol

from bloom_engine.api.models import RuntimePreviewBody
from bloom_engine.runtime.models import SceneRequest


class AmaRequestBuilder(Protocol):
    """Trusted boundary that converts untrusted Ama intent into runtime input.

    Implementations may consult authoritative BLOOM state and construct explicit
    sovereign query manifests. The external GPT/client never gets to originate
    those facts or mark them KNOWN itself.
    """

    def build_preview(self, body: RuntimePreviewBody) -> SceneRequest:
        ...
