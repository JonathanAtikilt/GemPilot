from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, replace
from time import perf_counter
from typing import Literal, Protocol, TypeVar

import httpx
from pydantic import BaseModel, ValidationError

from agent.config import Settings
from agent.model_outputs import (
    BlockerAnalysisOutput,
    DemoScriptOutput,
    FileManifestOutput,
    FinalReadmeOutput,
    MvpScopeOutput,
    PitchOutput,
    RepoPlanOutput,
)


OutputT = TypeVar("OutputT", bound=BaseModel)
ModelMode = Literal["mock", "live", "fallback"]


class ModelClientError(Exception):
    def __init__(self, safe_message: str) -> None:
        super().__init__(safe_message)
        self.safe_message = safe_message


class RetryableModelClientError(ModelClientError):
    pass


@dataclass(frozen=True)
class ModelCallResult[OutputT]:
    output: OutputT
    model: str
    purpose: str
    mode: ModelMode
    latency_ms: int
    fallback_reason: str | None = None


class ModelClient(Protocol):
    async def complete_structured(
        self,
        *,
        purpose: str,
        model: str,
        prompt: str,
        response_model: type[OutputT],
        max_tokens: int = 1200,
        reasoning_effort: str = "medium",
    ) -> ModelCallResult[OutputT]:
        """Return a structured model output for the requested purpose."""


class DeterministicModelClient:
    def __init__(
        self,
        *,
        mode: ModelMode = "mock",
        fallback_reason: str | None = None,
    ) -> None:
        self._mode = mode
        self._fallback_reason = fallback_reason

    async def complete_structured(
        self,
        *,
        purpose: str,
        model: str,
        prompt: str,
        response_model: type[OutputT],
        max_tokens: int = 1200,
        reasoning_effort: str = "medium",
    ) -> ModelCallResult[OutputT]:
        del max_tokens, reasoning_effort
        started = perf_counter()
        data = _deterministic_payload(
            purpose,
            self._mode,
            self._fallback_reason,
            prompt,
        )
        output = response_model.model_validate(data)
        return ModelCallResult(
            output=output,
            model=model,
            purpose=purpose,
            mode=self._mode,
            latency_ms=_elapsed_ms(started),
            fallback_reason=self._fallback_reason,
        )


class NemotronModelClient:
    def __init__(
        self,
        settings: Settings,
        *,
        fallback_client: DeterministicModelClient | None = None,
    ) -> None:
        self._settings = settings
        self._fallback_client = fallback_client

    async def complete_structured(
        self,
        *,
        purpose: str,
        model: str,
        prompt: str,
        response_model: type[OutputT],
        max_tokens: int = 1200,
        reasoning_effort: str = "medium",
    ) -> ModelCallResult[OutputT]:
        if not self._settings.nvidia_configured:
            return await self._fallback(
                purpose=purpose,
                model=model,
                prompt=prompt,
                response_model=response_model,
                reason="Missing NVIDIA_API_KEY for live mode.",
            )

        started = perf_counter()
        attempts = max(0, self._settings.nemotron_max_retries) + 1
        last_reason = "Nemotron request failed."

        for attempt in range(attempts):
            try:
                payload = await self._send_completion_request(
                    model=model,
                    prompt=prompt,
                    response_model=response_model,
                    max_tokens=max_tokens,
                    reasoning_effort=reasoning_effort,
                )
                return self._parse_completion_payload(
                    payload=payload,
                    purpose=purpose,
                    model=model,
                    response_model=response_model,
                    started=started,
                )
            except RetryableModelClientError as exc:
                last_reason = exc.safe_message
                if attempt + 1 < attempts:
                    continue
                return await self._fallback(
                    purpose=purpose,
                    model=model,
                    prompt=prompt,
                    response_model=response_model,
                    reason=last_reason,
                    started=started,
                )
            except ModelClientError as exc:
                return await self._fallback(
                    purpose=purpose,
                    model=model,
                    prompt=prompt,
                    response_model=response_model,
                    reason=exc.safe_message,
                    started=started,
                )
            except httpx.TimeoutException:
                last_reason = "Nemotron request timed out."
                if attempt + 1 < attempts:
                    continue
                return await self._fallback(
                    purpose=purpose,
                    model=model,
                    prompt=prompt,
                    response_model=response_model,
                    reason=last_reason,
                    started=started,
                )
            except httpx.HTTPError:
                last_reason = "Nemotron request failed."
                if attempt + 1 < attempts:
                    continue
                return await self._fallback(
                    purpose=purpose,
                    model=model,
                    prompt=prompt,
                    response_model=response_model,
                    reason=last_reason,
                    started=started,
                )

        return await self._fallback(
            purpose=purpose,
            model=model,
            prompt=prompt,
            response_model=response_model,
            reason=last_reason,
            started=started,
        )

    async def _send_completion_request(
        self,
        *,
        model: str,
        prompt: str,
        response_model: type[OutputT],
        max_tokens: int,
        reasoning_effort: str,
    ) -> dict:
        url = f"{self._settings.nemotron_base_url.rstrip('/')}/chat/completions"
        request_body = {
            "model": model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are MVPilot's structured planning model. Return only "
                        "JSON that matches the guided schema."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.2,
            "top_p": 0.95,
            "max_tokens": max_tokens,
            "stream": False,
            "reasoning_effort": reasoning_effort,
            "guided_json": response_model.model_json_schema(),
        }
        headers = {
            "Authorization": (
                f"Bearer {self._settings.nvidia_api_key.get_secret_value()}"
            ),
            "Content-Type": "application/json",
        }

        timeout = httpx.Timeout(self._settings.nemotron_timeout_seconds)
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(url, headers=headers, json=request_body)
            if response.status_code == 202:
                request_id = self._extract_request_id(response)
                return await self._poll_status(client=client, request_id=request_id)
            if response.status_code == 200:
                return self._safe_response_json(response)
            if response.status_code == 429 or response.status_code >= 500:
                raise RetryableModelClientError(
                    f"HTTP {response.status_code} from Nemotron."
                )
            raise ModelClientError(f"HTTP {response.status_code} from Nemotron.")

    async def _poll_status(
        self,
        *,
        client: httpx.AsyncClient,
        request_id: str,
    ) -> dict:
        status_url = (
            f"{self._settings.nemotron_base_url.rstrip('/')}/status/{request_id}"
        )
        attempts = max(1, self._settings.nemotron_poll_attempts)

        for _ in range(attempts):
            if self._settings.nemotron_poll_interval_seconds > 0:
                await asyncio.sleep(self._settings.nemotron_poll_interval_seconds)

            response = await client.get(status_url)
            if response.status_code == 202:
                continue
            if response.status_code != 200:
                raise ModelClientError(
                    f"HTTP {response.status_code} from Nemotron status."
                )

            payload = self._safe_response_json(response)
            status = str(payload.get("status", "")).lower()
            if status in {"failed", "error", "cancelled"}:
                raise ModelClientError("Nemotron async request failed.")
            if status in {"", "fulfilled", "completed", "succeeded", "success"}:
                try:
                    self._extract_content(payload)
                except ModelClientError:
                    continue
                return payload

        raise ModelClientError("Nemotron request stayed pending.")

    def _parse_completion_payload(
        self,
        *,
        payload: dict,
        purpose: str,
        model: str,
        response_model: type[OutputT],
        started: float,
    ) -> ModelCallResult[OutputT]:
        raw_content = self._extract_content(payload)
        try:
            parsed = json.loads(raw_content) if isinstance(raw_content, str) else raw_content
        except json.JSONDecodeError as exc:
            raise ModelClientError("Nemotron returned invalid JSON.") from exc

        try:
            output = response_model.model_validate(parsed)
        except ValidationError as exc:
            raise ModelClientError(
                "Nemotron response failed schema validation."
            ) from exc

        return ModelCallResult(
            output=output,
            model=model,
            purpose=purpose,
            mode="live",
            latency_ms=_elapsed_ms(started),
        )

    async def _fallback(
        self,
        *,
        purpose: str,
        model: str,
        prompt: str,
        response_model: type[OutputT],
        reason: str,
        started: float | None = None,
    ) -> ModelCallResult[OutputT]:
        fallback_client = self._fallback_client or DeterministicModelClient(
            mode="fallback",
            fallback_reason=reason,
        )
        result = await fallback_client.complete_structured(
            purpose=purpose,
            model=model,
            prompt=prompt,
            response_model=response_model,
        )
        if started is None:
            return result
        return replace(result, latency_ms=_elapsed_ms(started))

    @staticmethod
    def _safe_response_json(response: httpx.Response) -> dict:
        try:
            payload = response.json()
        except json.JSONDecodeError as exc:
            raise ModelClientError("Nemotron returned invalid JSON.") from exc
        if not isinstance(payload, dict):
            raise ModelClientError("Nemotron returned invalid JSON.")
        return payload

    @staticmethod
    def _extract_request_id(response: httpx.Response) -> str:
        payload = NemotronModelClient._safe_response_json(response)
        request_id = payload.get("requestId")
        if not isinstance(request_id, str) or not request_id.strip():
            raise ModelClientError("Nemotron accepted request without requestId.")
        return request_id

    @staticmethod
    def _extract_content(payload: dict) -> str | dict | list:
        choices = payload.get("choices")
        if isinstance(choices, list) and choices:
            first_choice = choices[0]
            if isinstance(first_choice, dict):
                message = first_choice.get("message")
                if isinstance(message, dict) and "content" in message:
                    return message["content"]
                if "text" in first_choice:
                    return first_choice["text"]

        for key in ("response", "result", "output"):
            nested = payload.get(key)
            if isinstance(nested, dict):
                return NemotronModelClient._extract_content(nested)
            if isinstance(nested, (str, list)):
                return nested

        if "content" in payload:
            return payload["content"]

        raise ModelClientError("Nemotron response missing completion content.")


def _elapsed_ms(started: float) -> int:
    return max(0, round((perf_counter() - started) * 1000))


def _trace(
    mode: ModelMode,
    fallback_reason: str | None,
    entries: list[str],
) -> list[str]:
    if mode == "fallback":
        return ["Fallback mode: NVIDIA endpoint unavailable.", *entries]
    return entries


def _extract_idea(prompt: str) -> str:
    marker = "Idea:\n"
    if marker not in prompt:
        return _clean_idea(prompt)

    value = prompt.split(marker, 1)[1].split("\n\n", 1)[0]
    return _clean_idea(value)


def _clean_idea(value: str) -> str:
    cleaned = " ".join(value.strip().split())
    return cleaned or "the submitted MVP idea"


def _idea_label(idea: str) -> str:
    label = idea.rstrip(".")
    return label if len(label) <= 90 else f"{label[:87].rstrip()}..."


def _idea_title(idea: str) -> str:
    label = _idea_label(idea)
    lowered = label.lower()
    for prefix in ("build a ", "build an ", "create a ", "make a "):
        if lowered.startswith(prefix):
            label = label[len(prefix):]
            break
    return label[:1].upper() + label[1:] if label else "Submitted MVP"


def _deterministic_payload(
    purpose: str,
    mode: ModelMode,
    fallback_reason: str | None,
    prompt: str,
) -> dict:
    idea = _extract_idea(prompt)
    if purpose == "plan_repo":
        return _repo_plan_payload(mode, fallback_reason, idea, prompt)

    payloads = {
        "scope_mvp": _scope_payload,
        "file_manifest": _file_manifest_payload,
        "blocker_analysis": _blocker_analysis_payload,
        "final_readme": _final_readme_payload,
        "demo_script": _demo_script_payload,
        "pitch": _pitch_payload,
    }
    try:
        return payloads[purpose](mode, fallback_reason, idea)
    except KeyError as exc:
        raise ModelClientError(f"Unsupported model purpose: {purpose}.") from exc


def _scope_payload(mode: ModelMode, fallback_reason: str | None, idea: str) -> dict:
    label = _idea_label(idea)
    return MvpScopeOutput(
        target_user="primary user for the submitted MVP",
        must_have=[
            "clear user intake",
            "source-grounded MVP scope",
            "visible progress and final package",
        ],
        demo_boundary=f"one mocked workflow for: {label}",
        mode=mode,
        decision_trace=_trace(
            mode,
            fallback_reason,
            [
                f"Grounded the scope in the submitted idea: {label}.",
                "Kept the MVP to one visible workflow for a short hackathon demo.",
                "Rejected broad integrations until the core demo path is reliable.",
            ],
        ),
    ).model_dump()


def _repo_plan_payload(
    mode: ModelMode,
    fallback_reason: str | None,
    idea: str,
    prompt: str,
) -> dict:
    label = _idea_label(idea)
    resolved_stack = _extract_resolved_stack_summary(prompt)
    return RepoPlanOutput(
        files=["README.md", "demo_script.md", "pitch.md"],
        test_plan=["unit workflow", "API integration", "mock build verify"],
        architecture_notes=[
            f"Use resolvedTechStack for generated files, tests, and architecture: {resolved_stack}.",
            "Keep model calls behind a client protocol.",
            "Keep GitHub and build actions behind mockable tool adapters.",
        ],
        mode=mode,
        decision_trace=_trace(
            mode,
            fallback_reason,
            [
                f"Selected a small artifact set for the submitted idea: {label}.",
                "Preserved existing API response shape for the frontend.",
                "Planned tests around workflow state instead of generated file IO.",
            ],
        ),
    ).model_dump()


def _extract_resolved_stack_summary(prompt: str) -> str:
    marker = "Resolved tech stack:\n"
    if marker not in prompt:
        return "the resolved MVPilot stack from build context"

    raw_block = prompt.split(marker, 1)[1].split("\n\n", 1)[0]
    try:
        payload = json.loads(raw_block)
    except json.JSONDecodeError:
        return "the resolved MVPilot stack from build context"

    items = payload.get("items") if isinstance(payload, dict) else None
    if not isinstance(items, list):
        return "the resolved MVPilot stack from build context"

    stack_items = [item for item in items if isinstance(item, str) and item.strip()]
    if not stack_items:
        return "the resolved MVPilot stack from build context"

    return ", ".join(stack_items)


def _file_manifest_payload(mode: ModelMode, fallback_reason: str | None, idea: str) -> dict:
    title = _idea_title(idea)
    return FileManifestOutput(
        artifacts=[
            {
                "name": "README.md",
                "kind": "markdown",
                "summary": "Generated setup and MVP overview.",
                "content": f"# {title}\n\nGenerated demo package for: {idea}",
            },
            {
                "name": "demo_script.md",
                "kind": "markdown",
                "summary": "Generated a three-minute demo script.",
                "content": f"# Demo Script\n\nShow the idea intake for: {idea}",
            },
            {
                "name": "pitch.md",
                "kind": "markdown",
                "summary": "Generated a concise hackathon pitch.",
                "content": f"# Pitch\n\nMVPilot turns this idea into a demo package: {idea}",
            },
        ],
        mode=mode,
        decision_trace=_trace(
            mode,
            fallback_reason,
            [
                "Mapped the repo plan into README, script, and pitch artifacts.",
                "Kept artifact content compact so dashboard traces stay readable.",
            ],
        ),
    ).model_dump()


def _blocker_analysis_payload(mode: ModelMode, fallback_reason: str | None, idea: str) -> dict:
    label = _idea_label(idea)
    return BlockerAnalysisOutput(
        blocker_type="missing_demo_dependency",
        severity="medium",
        recoverable=True,
        root_cause=(
            "The generated package references a demo dependency before the mock "
            "build adapter has a matching stub."
        ),
        recovery_plan=[
            "Classify the build result as recoverable.",
            "Apply the deterministic dependency stub patch.",
            "Run build verification again before final packaging.",
        ],
        decision_trace=_trace(
            mode,
            fallback_reason,
            [
                f"Kept blocker analysis tied to the submitted idea: {label}.",
                "Read the build tool result before applying recovery.",
                "Chose a minimal recovery because the repo plan is otherwise sound.",
                "Kept the blocker visible as proof of autonomous error handling.",
            ],
        ),
    ).model_dump()


def _final_readme_payload(mode: ModelMode, fallback_reason: str | None, idea: str) -> dict:
    title = _idea_title(idea)
    return FinalReadmeOutput(
        title=title,
        content=(
            f"# {title}\n\n"
            f"MVPilot turned this submitted idea into a small demo package: {idea}\n\n"
            "The package includes scoped requirements, generated artifacts, build "
            "verification, blocker recovery, and a judge-ready final summary."
        ),
        setup_steps=[
            "Install dependencies.",
            "Run the FastAPI backend in mock mode.",
            "Submit the idea through the dashboard.",
        ],
        decision_trace=_trace(
            mode,
            fallback_reason,
            [
                "Summarized the workflow around the submitted idea.",
                "Included setup steps that work without live external services.",
            ],
        ),
    ).model_dump()


def _demo_script_payload(mode: ModelMode, fallback_reason: str | None, idea: str) -> dict:
    title = _idea_title(idea)
    return DemoScriptOutput(
        title=f"Three-minute {title} demo",
        content=(
            f"Open with the submitted idea: {idea}. "
            "Show MVPilot retrieving context, scoping the MVP, generating repo "
            "artifacts, hitting a build blocker, applying recovery, and ending "
            "with README, script, and pitch content."
        ),
        beats=[
            "Enter the project idea.",
            "Watch the graph trace fill with model-backed decisions.",
            "Show the recoverable build blocker and recovery step.",
            "Close on the generated package and pitch.",
        ],
        decision_trace=_trace(
            mode,
            fallback_reason,
            [
                "Built the script around observable dashboard moments.",
                "Kept the blocker in the story instead of hiding it.",
            ],
        ),
    ).model_dump()


def _pitch_payload(mode: ModelMode, fallback_reason: str | None, idea: str) -> dict:
    label = _idea_label(idea)
    return PitchOutput(
        title="MVPilot",
        tagline="An AI teammate that turns messy hackathon ideas into demo packages.",
        content=(
            f"MVPilot helps teams move from idea to credible MVP evidence fast. "
            f"For this submitted idea, {label}, it scopes the workflow, plans "
            "the repo, generates artifacts, catches a build blocker, recovers, "
            "and produces the final README, demo script, and pitch."
        ),
        proof_points=[
            "Stable FastAPI task contracts for frontend integration.",
            "Structured Nemotron-style reasoning on model-backed steps.",
            "Visible blocker analysis and recovery before final packaging.",
        ],
        decision_trace=_trace(
            mode,
            fallback_reason,
            [
                "Focused the pitch on speed, traceability, and recovery.",
                "Used generated artifacts as the proof instead of broad claims.",
            ],
        ),
    ).model_dump()
