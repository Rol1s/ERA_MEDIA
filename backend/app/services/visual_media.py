from __future__ import annotations

import base64
import hashlib
import json
import mimetypes
import os
import re
import struct
import uuid
import urllib.error
import urllib.parse
import urllib.request
import zlib
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.models.all_models import Post
from app.services.brain_mode import active_brain
from app.services.org import log_activity
from app.services.secrets import resolve_secret_value

OPENAI_IMAGES_URL = "https://api.openai.com/v1/images/generations"
MEDIA_ROOT = Path(os.getenv("ERA_MEDIA_ROOT", "/app/generated_media"))
MEDIA_URL_PREFIX = "/media"


def visual_prompt_for_post(post: Post) -> str:
    base = (post.visual_prompt or "").strip()
    title = post.title.strip()
    body = re.sub(r"\s+", " ", (post.body or "").strip())[:900]
    sources = ", ".join((post.source_urls or [])[:2])
    risk = (post.risk_reason or "").strip()
    if not base:
        base = (
            f"Editorial visual for the Russian MAX news channel 'Нерв мира'. Topic: {title}. "
            f"Context: {body}. Main risk/factcheck note: {risk or 'avoid overstatement'}. Sources: {sources}. "
            "Create a strong mobile news-card image that shows consequence, place and tension through symbols, not a fake event photo."
        )
    return (
        f"{base}\n\n"
        "Format: square 1024x1024, readable in a mobile MAX feed, clear central composition, one visual idea, no tiny details. "
        "Style: sharp editorial illustration, modern news magazine cover, cinematic but restrained, high contrast, serious. "
        "Use concrete non-deceptive objects: maps, documents, weather/smoke/risk symbols, city silhouettes, official-looking generic papers, data markers. "
        "Forbidden: fake documentary photo, fake politician portrait, fake victims, fake screenshots, real logos, gore, sensational explosions as evidence, "
        "misleading uniforms or flags unless directly supported by the source. No text inside the image."
    )


def _store_local_fallback_visual(db: Session, post: Post, *, reason: str, error: str = "") -> Post:
    if post.mock_only or post.is_demo or post.provider == "mock" or post.generation_mode == "mock":
        raise ValueError("Mock/demo posts cannot receive production visuals.")

    image_bytes = _deterministic_editorial_card(post)
    MEDIA_ROOT.mkdir(parents=True, exist_ok=True)
    filename = f"post-{post.id}-{uuid.uuid4().hex[:10]}.png"
    path = MEDIA_ROOT / filename
    path.write_bytes(image_bytes)

    post.image_url = f"{MEDIA_URL_PREFIX}/{filename}"
    post.visual_url = post.image_url
    post.image_generation_status = "local_fallback_ready"
    post.image_generation_allowed = True
    post.visual_type = post.visual_type if post.visual_type != "none" else "editorial_card"
    post.visual_safety_notes = (
        "Local editorial card only. Not documentary evidence; no fake event photo."
    )
    post.media_source_type = "generated"
    post.media_source_url = post.image_url
    post.media_status = "needs_review" if (post.risk_score or 0) >= 60 else "generated"
    post.media_rights_note = (
        "Local deterministic editorial card. It is an illustrative visual, not a documentary photo or factual evidence."
    )
    post.structured_outputs_json = {
        **(post.structured_outputs_json or {}),
        "visual_generation": {
            "provider": "local_fallback",
            "reason": reason,
            "error": error[:500] if error else "",
            "safety": post.visual_safety_notes,
            "openai_called": False,
        },
    }
    log_activity(
        db,
        actor_type="agent",
        actor_id=None,
        event_type="visual_generated_local_fallback",
        entity_type="post",
        entity_id=post.id,
        message=f"Local fallback visual generated for post #{post.id}.",
        metadata={"image_url": post.image_url, "reason": reason, "openai_called": False},
    )
    db.flush()
    return post


def generate_visual_for_post(db: Session, post: Post, *, model: str = "gpt-image-1", size: str = "1024x1024") -> Post:
    if active_brain(db).get("mode") == "local_gemma":
        return _store_local_fallback_visual(
            db,
            post,
            reason="Local Gemma mode blocks OpenAI image generation; zero-token local editorial card created.",
        )
    if post.mock_only or post.is_demo or post.provider == "mock" or post.generation_mode == "mock":
        raise ValueError("Mock/demo posts cannot receive production visuals.")
    try:
        token = resolve_secret_value(db, "openai", "OPENAI_API_KEY")
    except Exception as exc:
        return _store_local_fallback_visual(
            db,
            post,
            reason="OpenAI image key is missing; local safe editorial card created.",
            error=str(exc),
        )
    prompt = visual_prompt_for_post(post)
    post.image_generation_status = "running"
    post.image_generation_allowed = True
    post.visual_type = post.visual_type if post.visual_type != "none" else "editorial_card"
    post.visual_safety_notes = (
        "Editorial illustration only. Do not treat as documentary evidence; no fake event photo."
    )
    db.flush()

    payload = {
        "model": model,
        "prompt": prompt,
        "size": size,
    }
    request = urllib.request.Request(
        OPENAI_IMAGES_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=90) as response:
            result = json.loads(response.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        image_bytes = _deterministic_editorial_card(post)
        MEDIA_ROOT.mkdir(parents=True, exist_ok=True)
        filename = f"post-{post.id}-{uuid.uuid4().hex[:10]}.png"
        path = MEDIA_ROOT / filename
        path.write_bytes(image_bytes)
        post.image_url = f"{MEDIA_URL_PREFIX}/{filename}"
        post.visual_url = post.image_url
        post.image_generation_status = "local_fallback_ready"
        post.media_source_type = "generated"
        post.media_source_url = post.image_url
        post.media_status = "needs_review" if (post.risk_score or 0) >= 60 else "generated"
        post.media_rights_note = (
            "Локальная редакционная карточка без фото события. Это не доказательство и не документальная фотография."
        )
        post.structured_outputs_json = {
            **(post.structured_outputs_json or {}),
            "visual_generation": {
                "provider": "local_fallback",
                "reason": f"OpenAI image generation failed: HTTP {exc.code}",
                "error": body[:500],
                "safety": post.visual_safety_notes,
            },
        }
        log_activity(
            db,
            actor_type="agent",
            actor_id=None,
            event_type="visual_generated_local_fallback",
            entity_type="post",
            entity_id=post.id,
            message=f"Local fallback visual generated for post #{post.id}.",
            metadata={"image_url": post.image_url, "openai_error": body[:500]},
        )
        db.flush()
        return post

    image_bytes = _image_bytes_from_result(result)
    MEDIA_ROOT.mkdir(parents=True, exist_ok=True)
    filename = f"post-{post.id}-{uuid.uuid4().hex[:10]}.png"
    path = MEDIA_ROOT / filename
    path.write_bytes(image_bytes)
    post.image_url = f"{MEDIA_URL_PREFIX}/{filename}"
    post.visual_url = post.image_url
    post.image_generation_status = "ready_for_review"
    post.media_source_type = "generated"
    post.media_source_url = post.image_url
    post.media_status = "needs_review" if (post.risk_score or 0) >= 60 else "generated"
    post.media_rights_note = "Сгенерированная редакционная карточка. Это не фото события и не доказательство."
    post.structured_outputs_json = {
        **(post.structured_outputs_json or {}),
        "visual_generation": {
            "provider": "openai",
            "model": model,
            "size": size,
            "prompt": prompt,
            "safety": post.visual_safety_notes,
        },
    }
    log_activity(
        db,
        actor_type="agent",
        actor_id=None,
        event_type="visual_generated",
        entity_type="post",
        entity_id=post.id,
        message=f"Visual generated for post #{post.id}.",
        metadata={"image_url": post.image_url, "model": model},
    )
    return post


def _image_bytes_from_result(result: dict[str, Any]) -> bytes:
    data = result.get("data") or []
    if not data:
        raise RuntimeError("OpenAI image generation returned no data.")
    item = data[0]
    b64 = item.get("b64_json")
    if b64:
        return base64.b64decode(b64)
    url = item.get("url")
    if url:
        with urllib.request.urlopen(url, timeout=60) as response:
            return response.read()
    raise RuntimeError("OpenAI image generation returned no image payload.")


def _png_chunk(kind: bytes, data: bytes) -> bytes:
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)


def _deterministic_editorial_card(post: Post, *, width: int = 1024, height: int = 1024) -> bytes:
    seed = hashlib.sha256(f"{post.id}:{post.title}:{post.channel_id}".encode("utf-8", errors="ignore")).digest()
    accent = (80 + seed[0] % 120, 70 + seed[1] % 120, 90 + seed[2] % 120)
    dark = (18, 24, 30)
    mid = (38 + seed[3] % 35, 44 + seed[4] % 35, 54 + seed[5] % 35)
    warm = (180 + seed[6] % 50, 145 + seed[7] % 55, 70 + seed[8] % 70)
    rows = bytearray()
    for y in range(height):
        rows.append(0)
        for x in range(width):
            t = y / max(1, height - 1)
            r = int(dark[0] * (1 - t) + mid[0] * t)
            g = int(dark[1] * (1 - t) + mid[1] * t)
            b = int(dark[2] * (1 - t) + mid[2] * t)
            if 170 < x - y * 0.35 < 260:
                r, g, b = accent
            if 710 < x + y * 0.22 < 790:
                r, g, b = warm
            cx, cy = width // 2, height // 2
            dist = ((x - cx) ** 2 + (y - cy) ** 2) ** 0.5
            if 260 < dist < 266 or 390 < dist < 396:
                r = min(255, r + 35)
                g = min(255, g + 35)
                b = min(255, b + 35)
            if (x // 42 + y // 42 + seed[9]) % 17 == 0:
                r = min(255, r + 18)
                g = min(255, g + 18)
                b = min(255, b + 18)
            rows.extend((r, g, b))
    raw = bytes(rows)
    return b"\x89PNG\r\n\x1a\n" + b"".join(
        [
            _png_chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)),
            _png_chunk(b"IDAT", zlib.compress(raw, 6)),
            _png_chunk(b"IEND", b""),
        ]
    )


def local_media_path(image_url: str | None) -> Path | None:
    if not image_url:
        return None
    clean = image_url.strip()
    if not clean.startswith(f"{MEDIA_URL_PREFIX}/"):
        return None
    name = clean.removeprefix(f"{MEDIA_URL_PREFIX}/")
    if not re.fullmatch(r"[A-Za-z0-9._-]+", name):
        return None
    path = MEDIA_ROOT / name
    return path if path.exists() else None


def upload_image_to_max(*, base_url: str, token: str, image_path: Path) -> dict[str, Any]:
    upload = _max_upload_descriptor(base_url=base_url, token=token)
    upload_url = str(upload.get("url") or upload.get("upload_url") or "")
    if not upload_url:
        raise RuntimeError(f"MAX upload descriptor has no url: {upload}")
    payload = _multipart_file("data", image_path)
    request = urllib.request.Request(
        upload_url,
        data=payload["body"],
        headers=payload["headers"],
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            body = response.read().decode("utf-8", errors="replace")
            parsed = json.loads(body or "{}")
            return parsed
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"MAX image upload failed: HTTP {exc.code} {body[:500]}") from exc


def _max_upload_descriptor(*, base_url: str, token: str) -> dict[str, Any]:
    url = f"{base_url.rstrip('/')}/uploads?type=image"
    request = urllib.request.Request(
        url,
        headers={"Authorization": token, "Accept": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            return json.loads(response.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"MAX upload init failed: HTTP {exc.code} {body[:500]}") from exc


def _multipart_file(field_name: str, path: Path) -> dict[str, Any]:
    boundary = f"----era{uuid.uuid4().hex}"
    content_type = mimetypes.guess_type(path.name)[0] or "image/png"
    chunks = [
        f"--{boundary}\r\n".encode(),
        f'Content-Disposition: form-data; name="{field_name}"; filename="{path.name}"\r\n'.encode(),
        f"Content-Type: {content_type}\r\n\r\n".encode(),
        path.read_bytes(),
        b"\r\n",
        f"--{boundary}--\r\n".encode(),
    ]
    body = b"".join(chunks)
    return {
        "body": body,
        "headers": {
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "Content-Length": str(len(body)),
        },
    }
