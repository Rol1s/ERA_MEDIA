from __future__ import annotations

import hashlib
import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.all_models import LlmCache
from app.services.org import log_activity


def stable_hash(payload: Any) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def llm_cache_key(*, source_item_id: int | None, pipeline_step: str, prompt_version: str, payload_hash: str) -> str:
    item = source_item_id if source_item_id is not None else "none"
    return f"{item}:{pipeline_step}:{prompt_version}:{payload_hash}"


def get_cached_llm_json(
    db: Session,
    *,
    source_item_id: int | None,
    pipeline_step: str,
    prompt_version: str,
    input_payload: Any,
    tokens_saved_estimate: int = 0,
) -> dict[str, Any] | None:
    payload_hash = stable_hash(input_payload)
    key = llm_cache_key(source_item_id=source_item_id, pipeline_step=pipeline_step, prompt_version=prompt_version, payload_hash=payload_hash)
    row = db.execute(select(LlmCache).where(LlmCache.cache_key == key)).scalar_one_or_none()
    if row is None:
        return None
    row.hits = int(row.hits or 0) + 1
    if tokens_saved_estimate:
        row.tokens_saved_estimate = int(row.tokens_saved_estimate or 0) + int(tokens_saved_estimate)
    log_activity(
        db,
        actor_type="system",
        actor_id=None,
        event_type="llm_cache_hit",
        entity_type="source_item",
        entity_id=source_item_id,
        message=f"LLM cache hit for {pipeline_step}; saved about {tokens_saved_estimate} tokens.",
        metadata={
            "pipeline_step": pipeline_step,
            "prompt_version": prompt_version,
            "tokens_saved_estimate": tokens_saved_estimate,
            "cache_key": key,
        },
    )
    db.flush()
    return dict(row.response_json or {})


def put_cached_llm_json(
    db: Session,
    *,
    source_item_id: int | None,
    pipeline_step: str,
    prompt_version: str,
    input_payload: Any,
    response_json: dict[str, Any],
    provider: str,
    model: str,
) -> LlmCache:
    payload_hash = stable_hash(input_payload)
    key = llm_cache_key(source_item_id=source_item_id, pipeline_step=pipeline_step, prompt_version=prompt_version, payload_hash=payload_hash)
    row = db.execute(select(LlmCache).where(LlmCache.cache_key == key)).scalar_one_or_none()
    if row is None:
        row = LlmCache(
            cache_key=key,
            source_item_id=source_item_id,
            pipeline_step=pipeline_step,
            prompt_version=prompt_version,
            input_hash=payload_hash,
        )
        db.add(row)
    row.response_json = response_json
    row.provider = provider
    row.model = model
    db.flush()
    return row
