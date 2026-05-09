from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any


class LLMConfigurationError(RuntimeError):
    pass


@dataclass(frozen=True)
class LLMUsage:
    tokens_input: int
    tokens_output: int
    estimated_cost: float


@dataclass(frozen=True)
class LLMResponse:
    text: str
    usage: LLMUsage
    provider: str = "mock"
    model: str = "mock"
    structured: dict[str, Any] | None = None


class LLMProvider:
    provider_name = "base"
    env_var = ""

    def __init__(self, *, model: str = "mock", temperature: float = 0.2, max_tokens: int = 800, api_key: str | None = None) -> None:
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.api_key = api_key

    def ensure_configured(self) -> None:
        if self.env_var and not (self.api_key or os.getenv(self.env_var)):
            raise LLMConfigurationError(f"Missing environment variable: {self.env_var}")

    def credential(self) -> str:
        self.ensure_configured()
        return self.api_key or os.environ[self.env_var]

    def generate(self, prompt: str, *, max_tokens: int = 600) -> LLMResponse:
        schema = {
            "type": "object",
            "properties": {"text": {"type": "string"}},
            "required": ["text"],
            "additionalProperties": False,
        }
        return self.generate_structured(
            system_prompt="Return a useful editorial response.",
            user_prompt=prompt,
            output_schema=schema,
            model=self.model,
            temperature=self.temperature,
            max_tokens=max_tokens,
        )

    def generate_structured(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        output_schema: dict[str, Any],
        model: str,
        temperature: float,
        max_tokens: int,
        tools: list[dict[str, Any]] | None = None,
        timeout_seconds: int | None = None,
    ) -> LLMResponse:
        raise NotImplementedError

    def _post_json(self, url: str, payload: dict[str, Any], headers: dict[str, str], timeout_seconds: int | None) -> dict[str, Any]:
        body = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(url, data=body, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=timeout_seconds or 30) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"{self.provider_name} HTTP {exc.code}: {detail}") from exc


def _mock_value(schema: dict[str, Any], key: str = "") -> Any:
    if "enum" in schema:
        return schema["enum"][0]
    typ = schema.get("type")
    if typ == "string":
        defaults = {
            "title": "Mock draft title",
            "body": "Mock editorial body with why it matters, practical context, and source-aware wording.",
            "visual_prompt": "Clean editorial mock visual prompt.",
            "what_happened": "A topic entered the ERA editorial pipeline.",
            "why_it_matters": "It may matter to the channel audience and requires editorial review.",
            "uncertainty": "Mock output; human review required.",
            "risk_notes": "No real risk analysis in mock mode.",
            "source_check": "Mock source check.",
            "reason": "Mock decision for UI and pipeline testing.",
            "editorial_value": "Adds context and a practical reader takeaway.",
            "channel_fit_reason": "Fits the selected channel profile in mock mode.",
            "publish_safety": "mock_only",
        }
        return defaults.get(key, f"mock_{key or 'value'}")
    if typ == "number":
        return 0.2 if "risk" in key else 0.82
    if typ == "integer":
        return 0
    if typ == "boolean":
        return key == "requires_human_review"
    if typ == "array":
        item_schema = schema.get("items", {"type": "string"})
        return [_mock_value(item_schema, key)]
    if typ == "object":
        return {child_key: _mock_value(child_schema, child_key) for child_key, child_schema in (schema.get("properties") or {}).items()}
    return None


def _parse_json_text(text: str) -> dict[str, Any]:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if cleaned.startswith("json"):
            cleaned = cleaned[4:]
    return json.loads(cleaned.strip())


class MockProvider(LLMProvider):
    provider_name = "mock"

    def generate_structured(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        output_schema: dict[str, Any],
        model: str,
        temperature: float,
        max_tokens: int,
        tools: list[dict[str, Any]] | None = None,
        timeout_seconds: int | None = None,
    ) -> LLMResponse:
        compact_prompt = " ".join(f"{system_prompt} {user_prompt}".split())
        structured = _mock_value(output_schema)
        text = json.dumps(structured, ensure_ascii=False)
        return LLMResponse(
            text=text,
            usage=LLMUsage(tokens_input=max(1, len(compact_prompt) // 4), tokens_output=max(1, len(text) // 4), estimated_cost=0.0),
            provider="mock",
            model=model or "mock",
            structured=structured,
        )


MockLLMProvider = MockProvider


class OpenAIProvider(LLMProvider):
    provider_name = "openai"
    env_var = "OPENAI_API_KEY"

    def generate_structured(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        output_schema: dict[str, Any],
        model: str,
        temperature: float,
        max_tokens: int,
        tools: list[dict[str, Any]] | None = None,
        timeout_seconds: int | None = None,
    ) -> LLMResponse:
        self.ensure_configured()
        payload = {
            "model": model,
            "input": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": temperature,
            "max_output_tokens": max_tokens,
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "era_agent_output",
                    "strict": True,
                    "schema": output_schema,
                }
            },
        }
        if tools:
            payload["tools"] = tools
            payload["parallel_tool_calls"] = False
        data = self._post_json(
            "https://api.openai.com/v1/responses",
            payload,
            {
                "Authorization": f"Bearer {self.credential()}",
                "Content-Type": "application/json",
            },
            timeout_seconds,
        )
        text = data.get("output_text") or ""
        if not text:
            for item in data.get("output", []):
                for content in item.get("content", []):
                    if content.get("type") in {"output_text", "text"}:
                        text += content.get("text", "")
        parsed = _parse_json_text(text) if text else data
        usage = data.get("usage") or {}
        return LLMResponse(
            text=text or json.dumps(parsed, ensure_ascii=False),
            usage=LLMUsage(
                tokens_input=int(usage.get("input_tokens", 0)),
                tokens_output=int(usage.get("output_tokens", 0)),
                estimated_cost=0.0,
            ),
            provider="openai",
            model=model,
            structured=parsed,
        )


class AnthropicProvider(LLMProvider):
    provider_name = "anthropic"
    env_var = "ANTHROPIC_API_KEY"

    def generate_structured(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        output_schema: dict[str, Any],
        model: str,
        temperature: float,
        max_tokens: int,
        tools: list[dict[str, Any]] | None = None,
        timeout_seconds: int | None = None,
    ) -> LLMResponse:
        self.ensure_configured()
        tool = {
            "name": "emit_json",
            "description": "Return only the requested schema-constrained JSON.",
            "input_schema": output_schema,
        }
        payload = {
            "model": model,
            "system": system_prompt,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": [{"role": "user", "content": user_prompt}],
            "tools": [tool, *(tools or [])],
            "tool_choice": {"type": "tool", "name": "emit_json"},
        }
        data = self._post_json(
            "https://api.anthropic.com/v1/messages",
            payload,
            {
                "x-api-key": self.credential(),
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            timeout_seconds,
        )
        usage = data.get("usage") or {}
        content = data.get("content") or []
        parsed: dict[str, Any] | None = None
        for item in content:
            if item.get("type") == "tool_use" and item.get("name") == "emit_json":
                parsed = item.get("input") or {}
                break
        text = json.dumps(parsed if parsed is not None else content, ensure_ascii=False)
        return LLMResponse(
            text=text,
            usage=LLMUsage(
                tokens_input=int(usage.get("input_tokens", 0)),
                tokens_output=int(usage.get("output_tokens", 0)),
                estimated_cost=0.0,
            ),
            provider="anthropic",
            model=model,
            structured=parsed or data,
        )


class GeminiProvider(LLMProvider):
    provider_name = "gemini"
    env_var = "GEMINI_API_KEY"

    def generate_structured(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        output_schema: dict[str, Any],
        model: str,
        temperature: float,
        max_tokens: int,
        tools: list[dict[str, Any]] | None = None,
        timeout_seconds: int | None = None,
    ) -> LLMResponse:
        self.ensure_configured()
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={self.credential()}"
        payload = {
            "system_instruction": {"parts": [{"text": system_prompt}]},
            "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens,
                "responseMimeType": "application/json",
                "responseSchema": output_schema,
            },
        }
        data = self._post_json(url, payload, {"Content-Type": "application/json"}, timeout_seconds)
        text = ""
        for candidate in data.get("candidates", []):
            for part in candidate.get("content", {}).get("parts", []):
                text += part.get("text", "")
        parsed = _parse_json_text(text) if text else data
        usage = data.get("usageMetadata") or {}
        return LLMResponse(
            text=text,
            usage=LLMUsage(
                tokens_input=int(usage.get("promptTokenCount", 0)),
                tokens_output=int(usage.get("candidatesTokenCount", 0)),
                estimated_cost=0.0,
            ),
            provider="gemini",
            model=model,
            structured=parsed,
        )


class LocalOllamaProvider(LLMProvider):
    provider_name = "local_ollama_optional"
    env_var = "OLLAMA_BASE_URL"

    def ensure_configured(self) -> None:
        if not os.getenv(self.env_var):
            raise LLMConfigurationError("Missing environment variable: OLLAMA_BASE_URL")

    def generate_structured(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        output_schema: dict[str, Any],
        model: str,
        temperature: float,
        max_tokens: int,
        tools: list[dict[str, Any]] | None = None,
        timeout_seconds: int | None = None,
    ) -> LLMResponse:
        self.ensure_configured()
        base_url = os.environ[self.env_var].rstrip("/")
        payload = {
            "model": model,
            "stream": False,
            "format": "json",
            "prompt": f"{system_prompt}\n\n{user_prompt}\n\nJSON schema: {json.dumps(output_schema)}",
            "options": {"temperature": temperature, "num_predict": max_tokens},
        }
        data = self._post_json(f"{base_url}/api/generate", payload, {"Content-Type": "application/json"}, timeout_seconds)
        text = data.get("response", "")
        parsed = _parse_json_text(text) if text else data
        return LLMResponse(
            text=text,
            usage=LLMUsage(tokens_input=0, tokens_output=0, estimated_cost=0.0),
            provider="local_ollama_optional",
            model=model,
            structured=parsed,
        )


def provider_for_name(provider: str, *, model: str, temperature: float = 0.2, max_tokens: int = 800, api_key: str | None = None) -> LLMProvider:
    providers: dict[str, type[LLMProvider]] = {
        "mock": MockProvider,
        "openai": OpenAIProvider,
        "anthropic": AnthropicProvider,
        "gemini": GeminiProvider,
        "local_ollama_optional": LocalOllamaProvider,
    }
    cls = providers.get(provider)
    if cls is None:
        raise LLMConfigurationError(f"Unsupported LLM provider: {provider}")
    return cls(model=model, temperature=temperature, max_tokens=max_tokens, api_key=api_key)
