from __future__ import annotations

import json
import os
from collections.abc import AsyncIterator, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Literal

import httpx

LLMProvider = Literal["gemini", "groq", "openai"]
Message = Mapping[str, str]

DEFAULT_MODELS: dict[LLMProvider, str] = {
    "gemini": "gemini-2.5-flash",
    "groq": "llama-3.1-8b-instant",
    "openai": "gpt-4.1-mini",
}

DEFAULT_BASE_URLS: dict[LLMProvider, str] = {
    "gemini": "https://generativelanguage.googleapis.com/v1beta",
    "groq": "https://api.groq.com/openai/v1",
    "openai": "https://api.openai.com/v1",
}


class LLMProviderError(Exception):
    def __init__(
        self,
        safe_message: str,
        *,
        provider: str | None = None,
        status_code: int | None = None,
        retryable: bool = False,
    ) -> None:
        super().__init__(safe_message)
        self.safe_message = safe_message
        self.provider = provider
        self.status_code = status_code
        self.retryable = retryable


class MissingLLMApiKeyError(LLMProviderError):
    pass


@dataclass(frozen=True)
class LLMOptions:
    provider: LLMProvider
    model: str
    api_key: str
    base_url: str
    fallback_provider: LLMProvider | None = None
    fallback_model: str | None = None
    fallback_api_key: str | None = None
    fallback_base_url: str | None = None
    temperature: float = 0.2
    top_p: float = 0.95
    max_tokens: int = 1200
    timeout_seconds: float = 120.0


def _provider_from_env(value: str | None = None) -> LLMProvider:
    provider = (value or os.getenv("LLM_PROVIDER") or "gemini").strip().lower()
    if provider not in {"gemini", "groq", "openai"}:
        raise LLMProviderError(
            "Unsupported LLM_PROVIDER. Use one of: gemini, groq, openai."
        )
    return provider  # type: ignore[return-value]


def _api_key_for(provider: LLMProvider, override: str | None = None) -> str:
    if override and override.strip():
        return override.strip()
    env_name = {
        "gemini": "GEMINI_API_KEY",
        "groq": "GROQ_API_KEY",
        "openai": "OPENAI_API_KEY",
    }[provider]
    value = os.getenv(env_name, "").strip()
    if value:
        return value
    raise MissingLLMApiKeyError(
        f"Missing {env_name}. Set it in the backend environment for LLM_PROVIDER={provider}.",
        provider=provider,
    )


def _resolve_options(options: Mapping[str, Any] | None = None) -> LLMOptions:
    data = dict(options or {})
    provider = _provider_from_env(data.get("provider"))
    fallback_provider = data.get("fallback_provider")
    fallback = _provider_from_env(str(fallback_provider)) if fallback_provider else None
    allow_provider_fallback = os.getenv("ALLOW_IDEA_AWARE_PARTIAL", "false").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    if (
        fallback is None
        and allow_provider_fallback
        and provider != "groq"
        and os.getenv("GROQ_API_KEY", "").strip()
    ):
        fallback = "groq"

    switched_to_fallback = False
    try:
        api_key = _api_key_for(provider, data.get("api_key"))
    except MissingLLMApiKeyError:
        if fallback is None:
            raise
        provider = fallback
        fallback = None
        switched_to_fallback = True
        api_key = _api_key_for(provider, data.get("fallback_api_key"))
        data["model"] = data.get("fallback_model") or os.getenv("LLM_FALLBACK_MODEL")
        data["base_url"] = data.get("fallback_base_url")

    model = str(
        data.get("model")
        or (None if switched_to_fallback else os.getenv("LLM_MODEL"))
        or DEFAULT_MODELS[provider]
    )
    base_url = str(
        data.get("base_url")
        or os.getenv(f"{provider.upper()}_BASE_URL")
        or DEFAULT_BASE_URLS[provider]
    ).rstrip("/")

    fallback_api_key: str | None = None
    fallback_model: str | None = None
    fallback_base_url: str | None = None
    if fallback is not None:
        try:
            fallback_api_key = _api_key_for(fallback, data.get("fallback_api_key"))
        except MissingLLMApiKeyError:
            fallback = None
        else:
            fallback_model = str(
                data.get("fallback_model")
                or os.getenv("LLM_FALLBACK_MODEL")
                or DEFAULT_MODELS[fallback]
            )
            fallback_base_url = str(
                data.get("fallback_base_url")
                or os.getenv(f"{fallback.upper()}_BASE_URL")
                or DEFAULT_BASE_URLS[fallback]
            ).rstrip("/")

    return LLMOptions(
        provider=provider,
        model=model,
        api_key=api_key,
        base_url=base_url,
        fallback_provider=fallback,
        fallback_model=fallback_model,
        fallback_api_key=fallback_api_key,
        fallback_base_url=fallback_base_url,
        temperature=float(data.get("temperature", os.getenv("LLM_TEMPERATURE", 0.2))),
        top_p=float(data.get("top_p", os.getenv("LLM_TOP_P", 0.95))),
        max_tokens=int(data.get("max_tokens", os.getenv("LLM_MAX_TOKENS", 1200))),
        timeout_seconds=float(
            data.get("timeout_seconds", os.getenv("LLM_TIMEOUT_SECONDS", 120))
        ),
    )


async def generate_text(
    messages: Sequence[Message],
    options: Mapping[str, Any] | None = None,
) -> str:
    resolved = _resolve_options(options)
    try:
        return await _generate_text_once(messages, resolved)
    except LLMProviderError:
        if not _has_fallback(resolved):
            raise
        fallback_options = _fallback_options(resolved)
        return await _generate_text_once(messages, fallback_options)


async def generate_json(
    messages: Sequence[Message],
    schema: Mapping[str, Any],
    options: Mapping[str, Any] | None = None,
) -> Any:
    resolved = _resolve_options(options)
    try:
        return await _generate_json_once(messages, schema, resolved)
    except LLMProviderError:
        if not _has_fallback(resolved):
            raise
        fallback_options = _fallback_options(resolved)
        return await _generate_json_once(messages, schema, fallback_options)


async def stream_text(
    messages: Sequence[Message],
    options: Mapping[str, Any] | None = None,
) -> AsyncIterator[str]:
    resolved = _resolve_options(options)
    async for chunk in _stream_text_once(messages, resolved):
        yield chunk


async def _generate_text_once(messages: Sequence[Message], options: LLMOptions) -> str:
    if options.provider == "gemini":
        payload = await _post_gemini(messages, options)
    else:
        payload = await _post_openai_compatible(messages, options)
    return _extract_text(payload, options.provider)


async def _generate_json_once(
    messages: Sequence[Message],
    schema: Mapping[str, Any],
    options: LLMOptions,
) -> Any:
    if options.provider == "gemini":
        payload = await _post_gemini(messages, options, schema=schema)
    else:
        payload = await _post_openai_compatible(messages, options, schema=schema)
    raw = _extract_text(payload, options.provider)
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise LLMProviderError(
            f"{options.provider} returned invalid JSON.",
            provider=options.provider,
            retryable=True,
        ) from exc


def _gemini_response_schema(schema: Mapping[str, Any]) -> dict[str, Any]:
    """Inline Pydantic JSON Schema refs for Gemini's responseSchema format."""

    root = dict(schema)
    defs = root.pop("$defs", {})

    def resolve(node: Any) -> Any:
        if isinstance(node, dict):
            if "$ref" in node:
                ref = node["$ref"]
                if ref.startswith("#/$defs/"):
                    def_name = ref.rsplit("/", 1)[-1]
                    if def_name not in defs:
                        raise LLMProviderError(
                            f"Unresolved JSON schema reference: {ref}",
                            provider="gemini",
                        )
                    return resolve(defs[def_name])
            cleaned: dict[str, Any] = {}
            for key, value in node.items():
                if key in {"$defs", "$schema", "title", "default"}:
                    continue
                cleaned[key] = resolve(value)
            return cleaned
        if isinstance(node, list):
            return [resolve(item) for item in node]
        return node

    return resolve(root)


async def _post_gemini(
    messages: Sequence[Message],
    options: LLMOptions,
    *,
    schema: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    request_body: dict[str, Any] = {
        "contents": _gemini_contents(messages),
        "generationConfig": {
            "temperature": options.temperature,
            "topP": options.top_p,
            "maxOutputTokens": options.max_tokens,
        },
    }
    system_instruction = _gemini_system_instruction(messages)
    if system_instruction:
        request_body["systemInstruction"] = {
            "parts": [{"text": system_instruction}],
        }
    if schema is not None:
        request_body["generationConfig"]["responseMimeType"] = "application/json"
        request_body["generationConfig"]["responseSchema"] = _gemini_response_schema(schema)

    url = f"{options.base_url}/models/{options.model}:generateContent"
    async with httpx.AsyncClient(timeout=options.timeout_seconds) as client:
        response = await client.post(
            url,
            headers={
                "x-goog-api-key": options.api_key,
                "Content-Type": "application/json",
            },
            json=request_body,
        )
    return _checked_json(response, options.provider)


async def _post_openai_compatible(
    messages: Sequence[Message],
    options: LLMOptions,
    *,
    schema: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "model": options.model,
        "messages": [dict(message) for message in messages],
        "temperature": options.temperature,
        "top_p": options.top_p,
        "max_tokens": options.max_tokens,
        "stream": False,
    }
    if schema is not None:
        body["response_format"] = {
            "type": "json_schema",
            "json_schema": {
                "name": "gempilot_response",
                "schema": dict(schema),
                "strict": False,
            },
        }

    url = f"{options.base_url}/chat/completions"
    async with httpx.AsyncClient(timeout=options.timeout_seconds) as client:
        response = await client.post(
            url,
            headers={
                "Authorization": f"Bearer {options.api_key}",
                "Content-Type": "application/json",
            },
            json=body,
        )
    return _checked_json(response, options.provider)


async def _stream_text_once(
    messages: Sequence[Message],
    options: LLMOptions,
) -> AsyncIterator[str]:
    if options.provider == "gemini":
        body = {
            "contents": _gemini_contents(messages),
            "generationConfig": {
                "temperature": options.temperature,
                "topP": options.top_p,
                "maxOutputTokens": options.max_tokens,
            },
        }
        system_instruction = _gemini_system_instruction(messages)
        if system_instruction:
            body["systemInstruction"] = {"parts": [{"text": system_instruction}]}
        url = f"{options.base_url}/models/{options.model}:streamGenerateContent?alt=sse"
        headers = {
            "x-goog-api-key": options.api_key,
            "Content-Type": "application/json",
        }
    else:
        body = {
            "model": options.model,
            "messages": [dict(message) for message in messages],
            "temperature": options.temperature,
            "top_p": options.top_p,
            "max_tokens": options.max_tokens,
            "stream": True,
        }
        url = f"{options.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {options.api_key}",
            "Content-Type": "application/json",
        }

    async with httpx.AsyncClient(timeout=None) as client:
        async with client.stream("POST", url, headers=headers, json=body) as response:
            if response.status_code >= 400:
                payload = await response.aread()
                raise LLMProviderError(
                    _http_error_message(options.provider, response.status_code, payload),
                    provider=options.provider,
                    status_code=response.status_code,
                    retryable=response.status_code == 429 or response.status_code >= 500,
                )
            async for line in response.aiter_lines():
                if not line.startswith("data:"):
                    continue
                data = line.removeprefix("data:").strip()
                if not data or data == "[DONE]":
                    continue
                try:
                    payload = json.loads(data)
                except json.JSONDecodeError:
                    continue
                chunk = _extract_stream_delta(payload, options.provider)
                if chunk:
                    yield chunk


def _checked_json(response: httpx.Response, provider: str) -> dict[str, Any]:
    content = response.content
    if response.status_code >= 400:
        raise LLMProviderError(
            _http_error_message(provider, response.status_code, content),
            provider=provider,
            status_code=response.status_code,
            retryable=response.status_code == 429 or response.status_code >= 500,
        )
    try:
        payload = response.json()
    except json.JSONDecodeError as exc:
        raise LLMProviderError(
            f"{provider} returned an invalid JSON response.",
            provider=provider,
            retryable=True,
        ) from exc
    if not isinstance(payload, dict):
        raise LLMProviderError(
            f"{provider} returned an unexpected response shape.",
            provider=provider,
        )
    return payload


def _http_error_message(provider: str, status_code: int, content: bytes) -> str:
    detail = ""
    try:
        payload = json.loads(content.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        payload = {}
    if isinstance(payload, dict):
        error = payload.get("error")
        if isinstance(error, dict):
            detail = str(error.get("message") or "")
        elif isinstance(error, str):
            detail = error
    suffix = f": {detail}" if detail else ""
    return f"HTTP {status_code} from {provider}{suffix}."


def _extract_text(payload: Mapping[str, Any], provider: str) -> str:
    if provider == "gemini":
        candidates = payload.get("candidates")
        if isinstance(candidates, list) and candidates:
            parts = (
                ((candidates[0] or {}).get("content") or {}).get("parts")
                if isinstance(candidates[0], dict)
                else None
            )
            if isinstance(parts, list):
                text = "".join(
                    part.get("text", "") for part in parts if isinstance(part, dict)
                ).strip()
                if text:
                    return text
    else:
        choices = payload.get("choices")
        if isinstance(choices, list) and choices:
            first = choices[0]
            if isinstance(first, dict):
                message = first.get("message")
                if isinstance(message, dict) and isinstance(message.get("content"), str):
                    return message["content"].strip()
                if isinstance(first.get("text"), str):
                    return first["text"].strip()
    raise LLMProviderError(
        f"{provider} response missing completion text.",
        provider=provider,
        retryable=True,
    )


def _extract_stream_delta(payload: Mapping[str, Any], provider: str) -> str:
    if provider == "gemini":
        try:
            parts = payload["candidates"][0]["content"]["parts"]
        except (KeyError, IndexError, TypeError):
            return ""
        if not isinstance(parts, list):
            return ""
        return "".join(part.get("text", "") for part in parts if isinstance(part, dict))

    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        return ""
    delta = choices[0].get("delta") if isinstance(choices[0], dict) else None
    if isinstance(delta, dict) and isinstance(delta.get("content"), str):
        return delta["content"]
    return ""


def _gemini_system_instruction(messages: Sequence[Message]) -> str:
    return "\n\n".join(
        message.get("content", "")
        for message in messages
        if message.get("role") == "system" and message.get("content")
    ).strip()


def _gemini_contents(messages: Sequence[Message]) -> list[dict[str, Any]]:
    contents: list[dict[str, Any]] = []
    for message in messages:
        role = message.get("role", "user")
        content = message.get("content", "")
        if role == "system" or not content:
            continue
        contents.append(
            {
                "role": "model" if role == "assistant" else "user",
                "parts": [{"text": content}],
            }
        )
    return contents or [{"role": "user", "parts": [{"text": ""}]}]


def _has_fallback(options: LLMOptions) -> bool:
    return bool(
        options.fallback_provider
        and options.fallback_model
        and options.fallback_api_key
        and options.fallback_base_url
    )


def _fallback_options(options: LLMOptions) -> LLMOptions:
    assert options.fallback_provider is not None
    assert options.fallback_model is not None
    assert options.fallback_api_key is not None
    assert options.fallback_base_url is not None
    return LLMOptions(
        provider=options.fallback_provider,
        model=options.fallback_model,
        api_key=options.fallback_api_key,
        base_url=options.fallback_base_url,
        temperature=options.temperature,
        top_p=options.top_p,
        max_tokens=options.max_tokens,
        timeout_seconds=options.timeout_seconds,
    )
