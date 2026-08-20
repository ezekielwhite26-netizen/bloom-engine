from __future__ import annotations

import json
import mimetypes
import os
import urllib.request
import uuid
from dataclasses import dataclass

from bloom_engine.apollo.models import RenderedVisual


def _download(url: str, timeout: int) -> tuple[bytes, str, str]:
    request = urllib.request.Request(url, headers={"User-Agent": "BLOOM-APOLLO/0.1"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        data = response.read()
        content_type = (response.headers.get_content_type() or "image/png").split(";", 1)[0]
        filename = url.rsplit("/", 1)[-1].split("?", 1)[0] or "reference.png"
    if not mimetypes.guess_extension(content_type):
        content_type = "image/png"
    return data, content_type, filename


def _multipart(fields: list[tuple[str, str]], files: list[tuple[str, str, str, bytes]]) -> tuple[bytes, str]:
    boundary = f"----bloom-{uuid.uuid4().hex}"
    chunks: list[bytes] = []
    for name, value in fields:
        chunks.extend((
            f"--{boundary}\r\n".encode(),
            f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode(),
            value.encode(),
            b"\r\n",
        ))
    for field_name, filename, content_type, data in files:
        safe_name = filename.replace('"', "_")
        chunks.extend((
            f"--{boundary}\r\n".encode(),
            f'Content-Disposition: form-data; name="{field_name}"; filename="{safe_name}"\r\n'.encode(),
            f"Content-Type: {content_type}\r\n\r\n".encode(),
            data,
            b"\r\n",
        ))
    chunks.append(f"--{boundary}--\r\n".encode())
    return b"".join(chunks), boundary


@dataclass(slots=True)
class OpenAIGPTImage2Transport:
    """GPT Image 2 edit transport using the pinned 2026-04-21 snapshot."""

    api_key: str | None = None
    endpoint: str = "https://api.openai.com/v1/images/edits"
    model: str = "gpt-image-2-2026-04-21"
    timeout_seconds: int = 240

    def edit(self, *, prompt: str, reference_urls: tuple[str, ...]) -> RenderedVisual:
        key = self.api_key or os.getenv("OPENAI_API_KEY")
        if not key:
            raise RuntimeError("MISSING_ENV:OPENAI_API_KEY")
        if not reference_urls:
            raise RuntimeError("GPT_IMAGE_2_REQUIRES_REFERENCE_IMAGE")
        files: list[tuple[str, str, str, bytes]] = []
        for index, url in enumerate(reference_urls, start=1):
            data, content_type, filename = _download(url, self.timeout_seconds)
            ext = mimetypes.guess_extension(content_type) or ".png"
            files.append(("image[]", f"reference-{index}{ext}", content_type, data))
        body, boundary = _multipart(
            [
                ("model", self.model),
                ("prompt", prompt),
                ("size", "1024x1536"),
                ("quality", "medium"),
                ("output_format", "jpeg"),
                ("output_compression", "90"),
            ],
            files,
        )
        request = urllib.request.Request(
            self.endpoint,
            data=body,
            method="POST",
            headers={
                "Authorization": f"Bearer {key}",
                "Content-Type": f"multipart/form-data; boundary={boundary}",
                "Accept": "application/json",
            },
        )
        with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
            request_id = response.headers.get("x-request-id")
            payload = json.loads(response.read().decode("utf-8"))
        data = payload.get("data") or []
        if not data or not data[0].get("b64_json"):
            raise RuntimeError("GPT_IMAGE_2_EMPTY_RESULT")
        return RenderedVisual(
            provider_id="gpt-image-2",
            model=self.model,
            mime_type="image/jpeg",
            image_base64=str(data[0]["b64_json"]),
            provider_request_id=request_id,
        )
