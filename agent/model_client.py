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
    if purpose == "file_manifest":
        return _file_manifest_payload(mode, fallback_reason, idea, prompt)
    if purpose == "final_readme":
        return _final_readme_payload(mode, fallback_reason, idea, prompt)
    if purpose == "demo_script":
        return _demo_script_payload(mode, fallback_reason, idea, prompt)
    if purpose == "pitch":
        return _pitch_payload(mode, fallback_reason, idea, prompt)

    payloads = {
        "scope_mvp": _scope_payload,
        "blocker_analysis": _blocker_analysis_payload,
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
    title = _project_title(idea, prompt)
    resolved_stack = _extract_resolved_stack_summary(prompt)
    warning_summary = _source_warning_summary(prompt)
    files = [
        "README.md",
        "requirements.txt",
        "src/app.py",
        "src/core/agent.py",
        "tests/test_app.py",
        "docs/ARCHITECTURE.md",
        "docs/BUILD_LOG.md",
        "demo/demo_script.md",
        ".env.example",
    ]
    return RepoPlanOutput(
        files=files,
        required_files=files,
        selected_stack=[item.strip() for item in resolved_stack.split(",") if item.strip()],
        repo_structure=[
            "README.md",
            "src/ for application code",
            "tests/ for smoke tests",
            "docs/ for architecture and build logs",
            "demo/ for the judging walkthrough",
        ],
        implementation_steps=[
            "Create a minimal API entrypoint.",
            "Add a deterministic agent core that mirrors the scoped MVP.",
            "Document architecture, build evidence, and demo flow.",
            "Commit generated files through the GitHub Agent.",
        ],
        agent_assignments=[
            "orchestrator: scope, plan, and validate the package",
            "rag: provide rules, stack, and safety evidence before planning",
            "github: create or update the repository and commit files",
            "black_box: store decisions, logs, artifacts, and final summary",
        ],
        github_actions_needed=[
            "create_new_repo or use_existing_repo from frontend intake",
            "commit generated project files",
            "return repoUrl, commitUrl, branch, filesUploaded, and errors",
        ],
        generated_artifacts=files,
        security_constraints=[
            "Never commit .env files or real secrets.",
            "Only include placeholder values in .env.example.",
            "Keep GitHub and Supabase service credentials server-side.",
        ],
        demo_requirements=[
            "Show the flight-stage progress path.",
            "Show RAG evidence before plan generation.",
            "End with GitHub repo and commit links.",
        ],
        test_plan=["unit workflow", "API integration", "repo health smoke check"],
        architecture_notes=[
            f"Use submitted title as project identity: {title}.",
            f"Use resolvedTechStack for generated files, tests, and architecture: {resolved_stack}.",
            "Keep model calls behind a client protocol.",
            "Keep GitHub and build actions behind mockable tool adapters.",
            warning_summary or "No submitted source warnings were present.",
        ],
        mode=mode,
        decision_trace=_trace(
            mode,
            fallback_reason,
            [
                f"Selected a complete but small repo package for the submitted idea: {label}.",
                "Planned around the RAG build context before any GitHub action.",
                "Kept generated files secret-safe and repo-health checkable.",
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


def _extract_json_section(prompt: str, marker: str) -> dict:
    if marker not in prompt:
        return {}

    raw_block = prompt.split(marker, 1)[1].split("\n\n", 1)[0]
    try:
        payload = json.loads(raw_block)
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _extract_frontend_intake(prompt: str) -> dict:
    return _extract_json_section(prompt, "Frontend intake:\n")


def _extract_source_context(prompt: str) -> dict:
    return _extract_json_section(prompt, "Source context:\n")


def _project_title(idea: str, prompt: str) -> str:
    intake = _extract_frontend_intake(prompt)
    title = intake.get("title")
    if isinstance(title, str) and title.strip():
        return title.strip()
    return _idea_title(idea)


def _source_warning_summary(prompt: str) -> str:
    source_context = _extract_source_context(prompt)
    warnings = source_context.get("warnings")
    if not isinstance(warnings, list) or not warnings:
        return ""

    messages = []
    for warning in warnings:
        if not isinstance(warning, dict):
            continue
        source = warning.get("source", "source")
        message = warning.get("message", "unreadable source")
        messages.append(f"{source}: {message}")

    if not messages:
        return ""
    return "Source warnings: " + "; ".join(messages)


def _file_manifest_payload(
    mode: ModelMode,
    fallback_reason: str | None,
    idea: str,
    prompt: str,
) -> dict:
    title = _project_title(idea, prompt)
    resolved_stack = _extract_resolved_stack_summary(prompt)
    warning_summary = _source_warning_summary(prompt)
    warning_note = f"\n\n{warning_summary}" if warning_summary else ""
    return FileManifestOutput(
        artifacts=[
            {
                "name": "README.md",
                "kind": "markdown",
                "summary": "Generated setup and MVP overview.",
                "content": (
                    f"# {title}\n\nGenerated demo package for: {idea}\n\n"
                    f"Resolved stack: {resolved_stack}.\n\n"
                    "## What This MVP Does\n\n"
                    "- Accepts a project idea.\n"
                    "- Retrieves build context before planning.\n"
                    "- Generates a small repo package and records the outcome.\n\n"
                    "## Run\n\n"
                    "```bash\n"
                    "pip install -r requirements.txt\n"
                    "python -m src.app\n"
                    "```\n"
                    f"{warning_note}"
                ),
            },
            {
                "name": "requirements.txt",
                "kind": "text",
                "summary": "Generated Python dependencies for install and health checks.",
                "content": "fastapi\nuvicorn\npytest\n",
            },
            {
                "name": "src/app.py",
                "kind": "python",
                "summary": "Generated minimal Python entrypoint.",
                "content": (
                    '"""Generated MVP entrypoint."""\n\n'
                    "from src.core.agent import build_summary\n\n\n"
                    "def main() -> None:\n"
                    f"    print(build_summary({json.dumps(title)}, {json.dumps(idea)}))\n\n\n"
                    'if __name__ == "__main__":\n'
                    "    main()\n"
                ),
            },
            {
                "name": "src/core/agent.py",
                "kind": "python",
                "summary": "Generated minimal agent core.",
                "content": (
                    '"""Tiny generated agent core for the hackathon MVP package."""\n\n\n'
                    "def build_summary(title: str, idea: str) -> str:\n"
                    "    return f\"{title}: scoped demo package for {idea}\"\n"
                ),
            },
            {
                "name": "tests/test_app.py",
                "kind": "python",
                "summary": "Generated smoke test for the agent core.",
                "content": (
                    "from src.core.agent import build_summary\n\n\n"
                    "def test_build_summary_contains_title_and_idea():\n"
                    "    output = build_summary('Demo', 'ship an MVP')\n"
                    "    assert 'Demo' in output\n"
                    "    assert 'ship an MVP' in output\n"
                ),
            },
            {
                "name": "docs/ARCHITECTURE.md",
                "kind": "markdown",
                "summary": "Generated architecture notes grounded in the plan.",
                "content": (
                    "# Architecture\n\n"
                    f"Project: {title}\n\n"
                    "## Stack\n\n"
                    f"{resolved_stack}\n\n"
                    "## Agent Flow\n\n"
                    "Frontend submits the idea, the orchestrator retrieves RAG context, "
                    "Nemotron planning generates the package, GitHub commits files, "
                    "and Black Box memory stores the result."
                    f"{warning_note}"
                ),
            },
            {
                "name": "docs/BUILD_LOG.md",
                "kind": "markdown",
                "summary": "Generated build log stub for Black Box indexing.",
                "content": (
                    "# Build Log\n\n"
                    "- Preflight complete.\n"
                    "- RAG context retrieved before planning.\n"
                    "- Repository package generated by MVPilot.\n"
                ),
            },
            {
                "name": "demo/demo_script.md",
                "kind": "markdown",
                "summary": "Generated a three-minute demo script.",
                "content": (
                    "# Demo Script\n\n"
                    f"Show {title}: {idea}.\n\n"
                    "1. Launch from the frontend.\n"
                    "2. Show Radar Scan evidence.\n"
                    "3. Show Flight Plan and GitHub commit links.\n"
                    f"{warning_note}"
                ),
            },
            {
                "name": ".env.example",
                "kind": "text",
                "summary": "Generated placeholder environment file.",
                "content": (
                    "NVIDIA_API_KEY=\n"
                    "SUPABASE_URL=\n"
                    "SUPABASE_SERVICE_ROLE_KEY=\n"
                    "GITHUB_TOKEN=\n"
                ),
            },
        ],
        mode=mode,
        decision_trace=_trace(
            mode,
            fallback_reason,
            [
                f"Mapped {title} into README, app, docs, tests, demo, and env placeholder artifacts.",
                f"Used resolved stack summary: {resolved_stack}.",
                "Kept artifact content compact, commit-safe, and health-checkable.",
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


def _final_readme_payload(
    mode: ModelMode,
    fallback_reason: str | None,
    idea: str,
    prompt: str,
) -> dict:
    title = _project_title(idea, prompt)
    resolved_stack = _extract_resolved_stack_summary(prompt)
    warning_summary = _source_warning_summary(prompt)
    warning_note = f"\n\n{warning_summary}" if warning_summary else ""
    return FinalReadmeOutput(
        title=title,
        content=(
            f"# {title}\n\n"
            f"MVPilot turned this submitted idea into a small demo package: {idea}\n\n"
            f"Resolved stack: {resolved_stack}.\n\n"
            "The package includes scoped requirements, generated artifacts, build "
            "verification, blocker recovery, and a judge-ready final summary."
            f"{warning_note}"
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
                f"Summarized the workflow around {title}.",
                f"Included resolved stack summary: {resolved_stack}.",
                "Included setup steps that work without live external services.",
            ],
        ),
    ).model_dump()


def _demo_script_payload(
    mode: ModelMode,
    fallback_reason: str | None,
    idea: str,
    prompt: str,
) -> dict:
    title = _project_title(idea, prompt)
    warning_summary = _source_warning_summary(prompt)
    warning_note = f" Mention source warnings: {warning_summary}." if warning_summary else ""
    return DemoScriptOutput(
        title=f"Three-minute {title} demo",
        content=(
            f"Open with the submitted idea: {idea}. "
            "Show MVPilot retrieving context, scoping the MVP, generating repo "
            "artifacts, hitting a build blocker, applying recovery, and ending "
            "with README, script, and pitch content."
            f"{warning_note}"
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
                f"Built the script around observable {title} dashboard moments.",
                "Kept the blocker in the story instead of hiding it.",
            ],
        ),
    ).model_dump()


def _pitch_payload(
    mode: ModelMode,
    fallback_reason: str | None,
    idea: str,
    prompt: str,
) -> dict:
    label = _idea_label(idea)
    title = _project_title(idea, prompt)
    warning_summary = _source_warning_summary(prompt)
    content = (
        f"MVPilot helps teams move from idea to credible MVP evidence fast. "
        f"For {title}, {label}, it scopes the workflow, plans "
        "the repo, generates artifacts, catches a build blocker, recovers, "
        "and produces the final README, demo script, and pitch."
    )
    if warning_summary:
        content = f"{content} {warning_summary}"
    return PitchOutput(
        title=title,
        tagline="An AI teammate that turns messy hackathon ideas into demo packages.",
        content=content,
        proof_points=[
            "Stable FastAPI task contracts for frontend integration.",
            "Structured Nemotron-style reasoning on model-backed steps.",
            "Visible blocker analysis and recovery before final packaging.",
        ],
        decision_trace=_trace(
            mode,
            fallback_reason,
            [
                f"Focused the {title} pitch on speed, traceability, and recovery.",
                "Used generated artifacts as the proof instead of broad claims.",
            ],
        ),
    ).model_dump()
