from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, replace
from time import perf_counter
from typing import Any, Literal, Protocol, TypeVar

import httpx
from pydantic import BaseModel, ValidationError

from agent.config import Settings
from agent.generated_project import build_project_artifacts
from agent.model_outputs import (
    BlockerAnalysisOutput,
    DemoScriptOutput,
    FileManifestOutput,
    FinalReadmeOutput,
    GeneratedFileBatchOutput,
    GeneratedFileWithContent,
    MvpScopeOutput,
    PitchOutput,
    RecommendedStackOutput,
    RepoPlanOutput,
)


OutputT = TypeVar("OutputT", bound=BaseModel)
ModelMode = Literal["mock", "live", "degraded", "partial"]


class ModelClientError(Exception):
    def __init__(self, safe_message: str) -> None:
        super().__init__(safe_message)
        self.safe_message = safe_message


class RetryableModelClientError(ModelClientError):
    pass


def _strip_json_fences(text: str) -> str:
    stripped = text.strip()
    if not stripped.startswith("```"):
        return stripped

    lines = stripped.splitlines()
    if lines and lines[0].startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]
    return "\n".join(lines).strip()


def _extract_json_object(text: str) -> str | None:
    cleaned = _strip_json_fences(text)
    start = cleaned.find("{")
    if start < 0:
        return None

    depth = 0
    in_string = False
    escape = False
    for index in range(start, len(cleaned)):
        char = cleaned[index]
        if in_string:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return cleaned[start : index + 1]
    return None


def _parse_json_text(raw: str) -> Any:
    candidates: list[str] = []
    stripped = _strip_json_fences(raw)
    candidates.append(stripped)
    extracted = _extract_json_object(stripped)
    if extracted and extracted not in candidates:
        candidates.insert(0, extracted)

    last_error: json.JSONDecodeError | None = None
    for candidate in candidates:
        try:
            return json.loads(candidate)
        except json.JSONDecodeError as exc:
            last_error = exc

    if last_error is not None:
        raise last_error
    raise json.JSONDecodeError("No JSON object found in model response.", raw, 0)


def _json_decode_looks_truncated(exc: BaseException | None) -> bool:
    if not isinstance(exc, json.JSONDecodeError):
        return False
    return "unterminated" in str(exc).lower()


def _bump_max_tokens(current: int, *, cap: int = 12_000) -> int:
    return min(max(current * 2, current + 2000), cap)


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


class ProviderModelClient:
    def __init__(
        self,
        settings: Settings,
    ) -> None:
        self._settings = settings

    def _allows_partial_fallback(self, purpose: str) -> bool:
        if not self._settings.allow_idea_aware_partial:
            return False
        if (
            purpose == "file_manifest"
            and self._settings.require_live_file_manifest
            and self._settings.llm_configured
        ):
            return False
        return True

    @staticmethod
    async def _backoff_before_retry(reason: str, attempt: int, *, purpose: str) -> None:
        if not any(code in reason for code in ("429", "500", "502", "503", "504")):
            return
        cap = 90.0 if purpose == "plan_repo" else 45.0
        await asyncio.sleep(min(cap, 2.0 ** (attempt + 1)))

    async def complete_structured(
        self,
        *,
        purpose: str,
        model: str,
        prompt: str,
        response_model: type[OutputT],
        max_tokens: int = 1200,
        reasoning_effort: str | None = None,
    ) -> ModelCallResult[OutputT]:
        del reasoning_effort
        if not self._settings.llm_configured:
            if not self._settings.allow_idea_aware_partial:
                raise ModelClientError(
                    f"Missing {self._settings.llm_missing_api_key_name} for "
                    f"LLM_PROVIDER={self._settings.llm_provider}. "
                    "Live-only mode is enabled; degraded fallback is disabled."
                )
            return await self._idea_specific_partial(
                purpose=purpose,
                model=model,
                prompt=prompt,
                response_model=response_model,
                reason=(
                    f"Missing {self._settings.llm_missing_api_key_name} for "
                    f"LLM_PROVIDER={self._settings.llm_provider}."
                ),
            )

        started = perf_counter()
        attempts = max(0, self._settings.llm_max_retries_for(purpose)) + 1
        last_reason = "LLM request failed."
        effective_max_tokens = max(
            max_tokens,
            self._settings.llm_max_tokens_for(purpose),
        )

        for attempt in range(attempts):
            try:
                parsed = await self._send_completion_request(
                    purpose=purpose,
                    model=model,
                    prompt=prompt,
                    response_model=response_model,
                    max_tokens=effective_max_tokens,
                )
                return self._parse_completion_payload(
                    parsed=parsed,
                    purpose=purpose,
                    model=model,
                    response_model=response_model,
                    started=started,
                )
            except RetryableModelClientError as exc:
                last_reason = exc.safe_message
                if "truncated JSON" in last_reason and effective_max_tokens < 12_000:
                    effective_max_tokens = _bump_max_tokens(effective_max_tokens)
                if attempt + 1 < attempts:
                    await self._backoff_before_retry(
                        last_reason, attempt, purpose=purpose
                    )
                    continue
                if not self._allows_partial_fallback(purpose):
                    raise ModelClientError(
                        f"Live LLM output is required for full project generation ({last_reason}). "
                        f"Set {self._settings.llm_missing_api_key_name} or enable degraded mode explicitly."
                    ) from exc
                return await self._idea_specific_partial(
                    purpose=purpose,
                    model=model,
                    prompt=prompt,
                    response_model=response_model,
                    reason=last_reason,
                    started=started,
                )
            except ModelClientError as exc:
                if not self._allows_partial_fallback(purpose):
                    raise
                return await self._idea_specific_partial(
                    purpose=purpose,
                    model=model,
                    prompt=prompt,
                    response_model=response_model,
                    reason=exc.safe_message,
                    started=started,
                )
            except httpx.TimeoutException as exc:
                last_reason = "LLM request timed out."
                if attempt + 1 < attempts:
                    await self._backoff_before_retry(
                        last_reason, attempt, purpose=purpose
                    )
                    continue
                if not self._allows_partial_fallback(purpose):
                    raise ModelClientError(
                        f"Live LLM output is required for full project generation ({last_reason}). "
                        f"Set {self._settings.llm_missing_api_key_name} or enable degraded mode explicitly."
                    ) from exc
                return await self._idea_specific_partial(
                    purpose=purpose,
                    model=model,
                    prompt=prompt,
                    response_model=response_model,
                    reason=last_reason,
                    started=started,
                )
            except httpx.HTTPError as exc:
                last_reason = "LLM request failed."
                if attempt + 1 < attempts:
                    await self._backoff_before_retry(
                        last_reason, attempt, purpose=purpose
                    )
                    continue
                if not self._allows_partial_fallback(purpose):
                    raise ModelClientError(
                        f"Live LLM output is required for full project generation ({last_reason}). "
                        f"Set {self._settings.llm_missing_api_key_name} or enable degraded mode explicitly."
                    ) from exc
                return await self._idea_specific_partial(
                    purpose=purpose,
                    model=model,
                    prompt=prompt,
                    response_model=response_model,
                    reason=last_reason,
                    started=started,
                )

        if not self._allows_partial_fallback(purpose):
            raise ModelClientError(
                f"Live LLM output is required for full project generation ({last_reason}). "
                f"Set {self._settings.llm_missing_api_key_name} or enable degraded mode explicitly."
            )
        return await self._idea_specific_partial(
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
        purpose: str,
        model: str,
        prompt: str,
        response_model: type[OutputT],
        max_tokens: int,
    ) -> Any:
        from agent.llm.provider import LLMProviderError, generate_json

        if purpose == "file_manifest":
            system_content = (
                "You are GemPilot's full-stack hackathon project repository manifest planner. Return only one "
                "complete JSON object matching the guided schema. List every required "
                "file path with kind and a short summary. Do not include file bodies or "
                "content fields. No markdown fences, prose, or trailing commas."
            )
        else:
            system_content = (
                "You are GemPilot's full-stack hackathon project planning model. Return only "
                "one complete JSON object that matches the guided schema. "
                "No markdown fences, prose, or trailing commas. Close all "
                "strings, arrays, and objects."
            )
        options: dict[str, Any] = {
            "provider": self._settings.llm_provider,
            "model": model,
            "api_key": self._settings.llm_api_key.get_secret_value()
            if self._settings.llm_api_key
            else None,
            "base_url": self._settings.llm_base_url,
            "temperature": 0.2,
            "top_p": 0.95,
            "max_tokens": max_tokens,
            "timeout_seconds": self._settings.llm_read_timeout_seconds(purpose),
        }
        if self._settings.allow_idea_aware_partial:
            options.update(
                {
                    "fallback_provider": "groq"
                    if self._settings.llm_provider != "groq" and self._settings.groq_api_key
                    else None,
                    "fallback_model": self._settings.llm_fallback_model_name,
                    "fallback_api_key": self._settings.groq_api_key.get_secret_value()
                    if self._settings.groq_api_key
                    else None,
                    "fallback_base_url": self._settings.groq_base_url,
                }
            )
        try:
            return await generate_json(
                [
                    {"role": "system", "content": system_content},
                    {"role": "user", "content": prompt},
                ],
                response_model.model_json_schema(),
                options=options,
            )
        except LLMProviderError as exc:
            if exc.retryable:
                raise RetryableModelClientError(exc.safe_message) from exc
            raise ModelClientError(exc.safe_message) from exc

    def _parse_completion_payload(
        self,
        *,
        parsed: Any,
        purpose: str,
        model: str,
        response_model: type[OutputT],
        started: float,
    ) -> ModelCallResult[OutputT]:
        try:
            output = response_model.model_validate(parsed)
        except ValidationError as exc:
            raise RetryableModelClientError(
                "LLM response failed schema validation."
            ) from exc

        return ModelCallResult(
            output=output,
            model=model,
            purpose=purpose,
            mode="live",
            latency_ms=_elapsed_ms(started),
        )

    async def _idea_specific_partial(
        self,
        *,
        purpose: str,
        model: str,
        prompt: str,
        response_model: type[OutputT],
        reason: str,
        started: float | None = None,
    ) -> ModelCallResult[OutputT]:
        if not self._settings.allow_idea_aware_partial:
            raise ModelClientError(
                f"Live LLM output is required for full project generation ({reason}). "
                f"Set {self._settings.llm_missing_api_key_name} or enable degraded mode explicitly."
            )

        from agent.idea_aware_partial import IdeaAwarePartialClient

        partial_reason = reason
        if self._settings.llm_fast_fallback_active:
            partial_reason = (
                f"{reason} Using explicit degraded project output after a short live LLM attempt."
            )

        partial_client = IdeaAwarePartialClient(partial_reason=partial_reason)
        result = await partial_client.complete_structured(
            purpose=purpose,
            model=model,
            prompt=prompt,
            response_model=response_model,
        )
        if started is None:
            return result
        return replace(result, latency_ms=_elapsed_ms(started))


GeminiModelClient = ProviderModelClient


def _elapsed_ms(started: float) -> int:
    return max(0, round((perf_counter() - started) * 1000))


def _trace(
    mode: ModelMode,
    fallback_reason: str | None,
    entries: list[str],
) -> list[str]:
    if mode in {"degraded", "partial"}:
        prefix = f"Degraded mode: {fallback_reason or 'live model unavailable; project-specific scaffold used'}"
        return [prefix, *entries]
    return entries


def _extract_idea(prompt: str) -> str:
    for marker in ("Idea:\n", "Product idea:\n", "PROJECT IDEA:\n"):
        if marker in prompt:
            value = prompt.split(marker, 1)[1].split("\n\n", 1)[0]
            return _clean_idea(value)
    return _clean_idea(prompt)


def _clean_idea(value: str) -> str:
    cleaned = " ".join(value.strip().split())
    return cleaned or "the submitted project idea"


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
    return label[:1].upper() + label[1:] if label else "Submitted Project"


def _deterministic_payload(
    purpose: str,
    mode: ModelMode,
    fallback_reason: str | None,
    prompt: str,
) -> dict:
    idea = _extract_idea(prompt)
    if purpose == "recommend_stack":
        return _stack_recommendation_payload(mode, fallback_reason, idea, prompt)
    if purpose in {"plan_repo", "architecture_plan"}:
        return _repo_plan_payload(mode, fallback_reason, idea, prompt)
    if purpose == "file_manifest":
        return _file_manifest_payload(mode, fallback_reason, idea, prompt)
    if purpose == "final_readme":
        return _final_readme_payload(mode, fallback_reason, idea, prompt)
    if purpose in {"demo_script", "walkthrough"}:
        return _demo_script_payload(mode, fallback_reason, idea, prompt)
    if purpose == "pitch":
        return _pitch_payload(mode, fallback_reason, idea, prompt)
    if purpose in {
        "generate_database",
        "generate_backend",
        "generate_frontend",
        "generate_docs",
        "generate_demo_video",
    }:
        return _code_generation_payload(mode, fallback_reason, idea, purpose)

    payloads = {
        "scope_mvp": _scope_payload,
        "requirement_expansion": _scope_payload,
        "blocker_analysis": _blocker_analysis_payload,
    }
    try:
        return payloads[purpose](mode, fallback_reason, idea, prompt)
    except KeyError as exc:
        raise ModelClientError(f"Unsupported model purpose: {purpose}.") from exc


def _scope_payload(
    mode: ModelMode,
    fallback_reason: str | None,
    idea: str,
    prompt: str = "",
) -> dict:
    from agent.idea_context import extract_json_section, features_from_context, target_users_from_context

    label = _idea_label(idea)
    intake = extract_json_section(prompt, "Frontend intake:\n")
    features = features_from_context(idea=idea, intake=intake)
    from agent.project_depth import enrich_project_requirements

    target = target_users_from_context(intake) or "users described in the submitted project"
    requirements = enrich_project_requirements(
        {
            "target_users": target,
            "user_personas": [target, "Admin or operator"],
            "core_features": features,
            "advanced_features": [
                "Authenticated workspace",
                "Operational dashboard",
                "Generated project evidence log",
            ],
            "success_criteria": [
                "The primary user can complete the end-to-end workflow.",
                "The codebase includes frontend, backend, database schema, tests, and docs.",
            ],
            "project_depth": intake.get("projectDepth") or "Advanced Project",
            "target_platform": intake.get("targetPlatform") or "web app",
            "mode": mode,
            "decision_trace": _trace(
                mode,
                fallback_reason,
                [
                    f"Grounded requirements in the submitted idea: {label}.",
                    "Expanded the idea into a multi-feature project brief.",
                    "Kept fallback behavior explicit as degraded mode when live generation is unavailable.",
                ],
            ),
        },
        idea=idea,
        intake=intake,
    )
    requirements["mode"] = mode
    requirements["decision_trace"] = _trace(
        mode,
        fallback_reason,
        [
            f"Grounded requirements in the submitted idea: {label}.",
            "Expanded the idea into a multi-feature project brief.",
            "Kept fallback behavior explicit as degraded mode when live generation is unavailable.",
        ],
    )
    return MvpScopeOutput.model_validate(requirements).model_dump()


def _stack_recommendation_payload(
    mode: ModelMode,
    fallback_reason: str | None,
    idea: str,
    prompt: str,
) -> dict:
    from agent.idea_context import extract_json_section
    from agent.stack_recommendation import recommend_stack_heuristic

    intake = extract_json_section(prompt, "Frontend intake:\n")
    requirements = extract_json_section(prompt, "Project requirements:\n")
    build_context = extract_json_section(prompt, "Structured build context:\n")
    payload = recommend_stack_heuristic(
        idea=idea,
        project_requirements=requirements,
        build_context=build_context if isinstance(build_context, dict) else {},
    )
    payload["mode"] = mode
    payload["decision_trace"] = _trace(
        mode,
        fallback_reason,
        [
            f"Stack Selector Agent grounded stack in: {_idea_label(idea)}.",
            "Did not copy GemPilot host platform defaults.",
            "Aligned stack with idea, depth, platform, and RAG hints.",
        ],
    )
    return RecommendedStackOutput.model_validate(payload).model_dump()


def _repo_plan_payload(
    mode: ModelMode,
    fallback_reason: str | None,
    idea: str,
    prompt: str,
) -> dict:
    from agent.architecture_planner import architecture_plan_to_repo_plan, plan_architecture
    from agent.idea_context import extract_json_section
    from agent.project_classifier import classify_project
    from agent.stack_recommendation import align_architecture_plan_with_recommended_stack

    label = _idea_label(idea)
    title = _project_title(idea, prompt)
    resolved_stack = _extract_resolved_stack_summary(prompt)
    warning_summary = _source_warning_summary(prompt)
    build_context = extract_json_section(prompt, "Structured build context:\n")
    intake = extract_json_section(prompt, "Frontend intake:\n") or {}
    recommended = (
        build_context.get("recommendedStack")
        if isinstance(build_context, dict)
        else None
    )
    requirements = extract_json_section(prompt, "Project requirements:\n") or {}
    profile = classify_project(idea, intake=intake, requirements=requirements)
    adaptive = plan_architecture(
        profile,
        idea=idea,
        recommended_stack=recommended if isinstance(recommended, dict) else None,
        requirements=requirements,
    )
    plan_base = architecture_plan_to_repo_plan(adaptive)
    files = list(plan_base.get("file_tree") or plan_base.get("files") or [])
    overview = list(plan_base.get("architecture_overview") or [])
    overview.extend(
        [
            f"Use submitted title as project identity: {title}.",
            f"Use resolvedTechStack for generated files, tests, and architecture: {resolved_stack}.",
            f"Adaptive blueprint category={profile.category}; architecture_type={profile.architecture_type}.",
        ]
    )
    api_design = [
        str(route)
        for route in (requirements.get("api_routes") or [])
        if str(route).strip()
    ]
    if not api_design and profile.backend_required:
        api_design = [
            "GET /api/health",
            *(["POST /api/auth/login"] if profile.auth_required else []),
            "GET /api/data",
            "POST /api/data",
        ]
    plan_payload = RepoPlanOutput(
        files=files,
        file_tree=files,
        selected_stack=[item.strip() for item in resolved_stack.split(",") if item.strip()],
        architecture_overview=overview,
        frontend_architecture=list(plan_base.get("frontend_architecture") or []),
        backend_architecture=list(plan_base.get("backend_architecture") or []),
        data_model=list(plan_base.get("data_model") or []),
        api_design=api_design,
        auth_design=(
            [
                "Development login route for local testing.",
                "Production-ready auth replacement documented when auth is required.",
            ]
            if profile.auth_required
            else ["Authentication omitted — not required for this project profile."]
        ),
        database_schema=(
            [
                "Persistence layer aligned to classified database requirements.",
            ]
            if profile.database_required
            else ["No database layer required for this project profile."]
        ),
        state_management=(
            [
                "Client state for primary user flows and generated artifacts.",
            ]
            if profile.frontend_required
            else ["State managed within CLI/extension/runtime entrypoints."]
        ),
        integration_points=[
            "Provider hooks documented in architecture plan.",
            *(["Persistence boundary in backend/db adapter."] if profile.database_required else []),
        ],
        implementation_steps=list(plan_base.get("implementation_steps") or [])
        or [
            f"Implement stage: {stage}" for stage in adaptive.implementation_stages
        ],
        agent_assignments=[
            "Product Strategist Agent: requirements, personas, features, success criteria",
            "Research/RAG Agent: source URLs, uploaded docs, memory, and context",
            "System Architect Agent: architecture, stack, file tree, integration points",
            "Data/API Agent: models, API routes, validation, auth, storage",
            "Frontend Agent: screens, components, state, user experience",
            "Backend Agent: routes, services, persistence, provider boundaries",
            "QA Agent: validation, test plan, build verification",
            "Documentation Agent: README, setup, env, architecture, usage",
            "GitHub Agent: repo create/update and commit",
            "Logger Agent: live progress and stored logs",
        ],
        github_actions_needed=[
            "create_new_repo or use_existing_repo from frontend intake",
            "commit generated project files",
            "return repoUrl, commitUrl, branch, filesUploaded, and validation status",
        ],
        generated_artifacts=files,
        security_constraints=[
            "Never commit .env files or real secrets.",
            "Only include placeholder values in .env.example.",
            "Keep GitHub and Supabase service credentials server-side.",
        ],
        test_plan=list(plan_base.get("test_plan") or ["unit tests", "integration checks", "repository health validation"]),
        deployment_plan=[
            "Deploy according to classified project profile and stack recommendation.",
            *(["Run database schema and set backend-only secrets."] if profile.database_required else []),
        ],
        documentation_plan=[
            "README with setup and usage",
            "Architecture, testing, deployment, limitations, walkthrough, demo materials, and submission docs",
        ],
        demo_video_plan=[
            "Create demo/script.md with timestamps for the generated product user flow.",
            "Create storyboard, walkthrough, video outline, and optional voiceover files under demo/.",
            "Link demo materials from the README Demo section.",
        ],
        hackathon_submission_plan=[
            "Summarize problem, solution, stack, differentiators, setup, demo flow, and judging proof.",
            "Point judges to README, docs, tests, deployment guide, and demo materials.",
        ],
        mode=mode,
        decision_trace=_trace(
            mode,
            fallback_reason,
            [
                f"Selected adaptive repository blueprint for the submitted idea: {label}.",
                f"Category={profile.category}; stages={', '.join(adaptive.implementation_stages)}.",
                "Planned around the RAG build context before any GitHub action.",
                warning_summary or "No submitted source warnings were present.",
                "Kept generated files secret-safe, testable, and deployable.",
            ],
        ),
    ).model_dump()
    merged = {
        **plan_payload,
        **{k: v for k, v in plan_base.items() if k not in plan_payload or not plan_payload.get(k)},
        "validation_profile": adaptive.validation_profile,
        "project_profile_rationale": adaptive.rationale,
    }
    return align_architecture_plan_with_recommended_stack(
        merged,
        recommended if isinstance(recommended, dict) else None,
    )


def _extract_resolved_stack_summary(prompt: str) -> str:
    marker = "Resolved tech stack:\n"
    if marker not in prompt:
        return "the resolved project stack from build context"

    raw_block = prompt.split(marker, 1)[1].split("\n\n", 1)[0]
    try:
        payload = json.loads(raw_block)
    except json.JSONDecodeError:
        return "the resolved project stack from build context"

    items = payload.get("items") if isinstance(payload, dict) else None
    if not isinstance(items, list):
        return "the resolved project stack from build context"

    stack_items = [item for item in items if isinstance(item, str) and item.strip()]
    if not stack_items:
        return "the resolved project stack from build context"

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
    warnings = _source_warnings(prompt)
    if not warnings:
        return ""

    messages = []
    for warning in warnings:
        source = warning.get("source", "source")
        message = warning.get("message", "unreadable source")
        messages.append(f"{source}: {message}")

    if not messages:
        return ""
    return "Source warnings: " + "; ".join(messages)


def _source_warnings(prompt: str) -> list[dict[str, str]]:
    source_context = _extract_source_context(prompt)
    warnings = source_context.get("warnings")
    if not isinstance(warnings, list) or not warnings:
        return []

    parsed: list[dict[str, str]] = []
    for warning in warnings:
        if not isinstance(warning, dict):
            continue
        source = warning.get("source", "source")
        message = warning.get("message", "unreadable source")
        parsed.append({"source": str(source), "message": str(message)})
    return parsed


def _file_manifest_payload(
    mode: ModelMode,
    fallback_reason: str | None,
    idea: str,
    prompt: str,
) -> dict:
    title = _project_title(idea, prompt)
    resolved_stack = _extract_resolved_stack_summary(prompt)
    warning_summary = _source_warning_summary(prompt)
    source_warnings = _source_warnings(prompt)
    architecture_plan = _extract_json_section(prompt, "Architecture plan:\n") or _extract_json_section(prompt, "Repo plan:\n")
    project_requirements = _extract_json_section(prompt, "Project requirements:\n") or _extract_json_section(prompt, "MVP scope:\n")
    artifacts = build_project_artifacts(
        idea=idea,
        title=title,
        resolved_stack=resolved_stack,
        architecture_plan=architecture_plan,
        source_warnings=source_warnings,
        project_requirements=project_requirements,
    )
    return FileManifestOutput(
        artifacts=artifacts,
        mode=mode,
        decision_trace=_trace(
            mode,
            fallback_reason,
            [
                f"Mapped {title} into complete frontend, backend, database, tests, docs, deployment, and walkthrough artifacts.",
                f"Used resolved stack summary: {resolved_stack}.",
                warning_summary or "No submitted source warnings were present.",
                "Kept artifact content secret-safe, testable, and deployment-ready.",
            ],
        ),
    ).model_dump()


def _blocker_analysis_payload(
    mode: ModelMode,
    fallback_reason: str | None,
    idea: str,
    prompt: str = "",
) -> dict:
    del prompt
    label = _idea_label(idea)
    return BlockerAnalysisOutput(
        blocker_type="repo_health_recovery",
        severity="medium",
        recoverable=True,
        root_cause=(
            "Repository health verification found a missing or incomplete generated artifact "
            "after the full project package was committed."
        ),
        recovery_plan=[
            "Classify the build result as recoverable.",
            "Regenerate or patch only the missing project-specific artifact.",
            "Run build verification again before final packaging.",
        ],
        decision_trace=_trace(
            mode,
            fallback_reason,
            [
                f"Kept blocker analysis tied to the submitted idea: {label}.",
                "Read the build tool result before applying recovery.",
                "Chose a minimal recovery because the repo plan is otherwise sound.",
                "Kept the blocker visible as proof of autonomous validation and recovery.",
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
            f"GemPilot turned this submitted idea into a complete hackathon-ready full-stack project: {idea}\n\n"
            f"Resolved stack: {resolved_stack}.\n\n"
            "The package includes expanded requirements, architecture, source files, API/data plans, "
            "tests, setup instructions, deployment guidance, validation evidence, and a final project report."
            f"{warning_note}"
        ),
        setup_steps=[
            "Install dependencies.",
            "Run the FastAPI backend.",
            "Submit the idea through the dashboard.",
        ],
        decision_trace=_trace(
            mode,
            fallback_reason,
            [
                f"Summarized the workflow around {title}.",
                f"Included resolved stack summary: {resolved_stack}.",
                "Included setup, testing, and deployment steps for a complete project handoff.",
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
        title=f"Three-minute {title} walkthrough",
        content=(
            f"Open the generated {title} app and frame the user problem: {idea}. "
            "Sign in, show the dashboard, complete the primary product workflow, create or upload "
            "sample data, trigger the backend API flow, review database-backed results, and close "
            "on README setup, API docs, tests, deployment notes, and the demo materials in /demo."
            f"{warning_note}"
        ),
        beats=[
            "Open the generated app and sign in with the demo user.",
            "Walk through the product-specific dashboard and primary workflow.",
            "Show the backend/API result and sample data that supports the flow.",
            "Close on setup, tests, deployment instructions, and demo video assets.",
        ],
        decision_trace=_trace(
            mode,
            fallback_reason,
            [
                f"Built the script around observable {title} dashboard moments.",
                "Focused the demo on the generated app's end-to-end user flow and technical proof.",
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
        f"GemPilot helps teams move from idea to complete hackathon-ready full-stack projects. "
        f"For {title}, {label}, it expands requirements, designs the architecture, "
        "generates a full codebase, validates the output, and produces README, setup, "
        "testing, deployment, demo-video assets, and project-report evidence."
    )
    if warning_summary:
        content = f"{content} {warning_summary}"
    return PitchOutput(
        title=title,
        tagline="A configurable AI project studio that turns ideas into committed full-stack repositories.",
        content=content,
        proof_points=[
            "Stable FastAPI task contracts for frontend integration.",
            "Structured provider-backed reasoning on model-backed steps.",
            "Visible validation and recovery before final packaging.",
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


def _code_generation_payload(
    mode: ModelMode,
    fallback_reason: str | None,
    idea: str,
    stage: str,
) -> dict:
    """Mock payload for the 5 staged code-generation purposes."""
    from agent.model_outputs import GeneratedFileBatchOutput, GeneratedFileWithContent

    label = _idea_label(idea)
    stage_short = stage.replace("generate_", "")

    # Minimal but structurally valid file set per stage
    _stage_files: dict[str, list[dict[str, str]]] = {
        "database": [
            {
                "name": "backend/db.py",
                "kind": "python",
                "summary": "SQLAlchemy async engine and session factory.",
                "content": (
                    "from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine\n"
                    "from sqlalchemy.orm import DeclarativeBase, sessionmaker\n"
                    "import os\n\n"
                    "DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite+aiosqlite:///./app.db')\n"
                    "engine = create_async_engine(DATABASE_URL, echo=False)\n"
                    "AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)\n\n"
                    "class Base(DeclarativeBase):\n"
                    "    pass\n\n"
                    "async def get_db():\n"
                    "    async with AsyncSessionLocal() as session:\n"
                    "        yield session\n"
                ),
            },
            {
                "name": "backend/models.py",
                "kind": "python",
                "summary": f"ORM models for {label}.",
                "content": (
                    "from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text\n"
                    "from sqlalchemy.orm import relationship\n"
                    "from sqlalchemy.sql import func\n"
                    "from backend.db import Base\n\n"
                    "class User(Base):\n"
                    "    __tablename__ = 'users'\n"
                    "    id = Column(Integer, primary_key=True, index=True)\n"
                    "    email = Column(String, unique=True, index=True, nullable=False)\n"
                    "    hashed_password = Column(String, nullable=False)\n"
                    "    is_active = Column(Boolean, default=True)\n"
                    "    created_at = Column(DateTime(timezone=True), server_default=func.now())\n\n"
                    f"    def __repr__(self) -> str:\n"
                    f"        return f'<User id={{self.id}} email={{self.email}}>'\n"
                ),
            },
            {
                "name": "docs/DATABASE_SCHEMA.sql",
                "kind": "sql",
                "summary": "DDL for all application tables.",
                "content": (
                    f"-- {label} database schema\n"
                    "CREATE TABLE IF NOT EXISTS users (\n"
                    "    id SERIAL PRIMARY KEY,\n"
                    "    email VARCHAR(255) UNIQUE NOT NULL,\n"
                    "    hashed_password VARCHAR(255) NOT NULL,\n"
                    "    is_active BOOLEAN DEFAULT TRUE,\n"
                    "    created_at TIMESTAMPTZ DEFAULT NOW()\n"
                    ");\n"
                    "CREATE INDEX idx_users_email ON users(email);\n"
                ),
            },
            {
                "name": "scripts/seed_data.py",
                "kind": "python",
                "summary": "Seed sample data for development.",
                "content": (
                    "\"\"\"Seed development data.\"\"\"\n"
                    "import asyncio\n"
                    "from backend.db import AsyncSessionLocal, engine, Base\n"
                    "from backend.models import User\n"
                    "from passlib.context import CryptContext\n\n"
                    "pwd_context = CryptContext(schemes=['bcrypt'], deprecated='auto')\n\n"
                    "async def seed():\n"
                    "    async with engine.begin() as conn:\n"
                    "        await conn.run_sync(Base.metadata.create_all)\n"
                    "    async with AsyncSessionLocal() as db:\n"
                    "        demo = User(email='demo@example.com', hashed_password=pwd_context.hash('demo1234'))\n"
                    "        db.add(demo)\n"
                    "        await db.commit()\n"
                    "    print('Seed complete.')\n\n"
                    "if __name__ == '__main__':\n"
                    "    asyncio.run(seed())\n"
                ),
            },
        ],
        "backend": [
            {
                "name": "backend/main.py",
                "kind": "python",
                "summary": f"FastAPI application for {label}.",
                "content": (
                    "from fastapi import FastAPI\n"
                    "from fastapi.middleware.cors import CORSMiddleware\n"
                    "from backend.routers import auth, items\n\n"
                    f"app = FastAPI(title='{label}', version='1.0.0')\n"
                    "app.add_middleware(CORSMiddleware, allow_origins=['*'], allow_methods=['*'], allow_headers=['*'], allow_credentials=True)\n"
                    "app.include_router(auth.router, prefix='/api/auth', tags=['auth'])\n"
                    "app.include_router(items.router, prefix='/api/items', tags=['items'])\n\n"
                    "@app.get('/health')\n"
                    "def health(): return {'status': 'ok'}\n"
                ),
            },
            {
                "name": "backend/auth.py",
                "kind": "python",
                "summary": "JWT authentication helpers.",
                "content": (
                    "from datetime import datetime, timedelta\n"
                    "from jose import JWTError, jwt\n"
                    "from passlib.context import CryptContext\n"
                    "from fastapi import Depends, HTTPException, status\n"
                    "from fastapi.security import OAuth2PasswordBearer\n"
                    "import os\n\n"
                    "SECRET_KEY = os.getenv('SECRET_KEY', 'change-me-in-production')\n"
                    "ALGORITHM = 'HS256'\n"
                    "ACCESS_TOKEN_EXPIRE_MINUTES = 60\n"
                    "pwd_context = CryptContext(schemes=['bcrypt'], deprecated='auto')\n"
                    "oauth2_scheme = OAuth2PasswordBearer(tokenUrl='/api/auth/token')\n\n"
                    "def create_access_token(data: dict) -> str:\n"
                    "    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)\n"
                    "    return jwt.encode({**data, 'exp': expire}, SECRET_KEY, algorithm=ALGORITHM)\n\n"
                    "def verify_password(plain: str, hashed: str) -> bool:\n"
                    "    return pwd_context.verify(plain, hashed)\n\n"
                    "def hash_password(plain: str) -> str:\n"
                    "    return pwd_context.hash(plain)\n"
                ),
            },
            {
                "name": ".env.example",
                "kind": "text",
                "summary": "Environment variable template.",
                "content": (
                    "# Application\n"
                    f"APP_NAME={label}\n"
                    "SECRET_KEY=your-secret-key-here\n"
                    "DATABASE_URL=sqlite+aiosqlite:///./app.db\n"
                    "# DATABASE_URL=postgresql+asyncpg://user:pass@localhost/dbname\n\n"
                    "# Frontend\n"
                    "VITE_API_URL=http://localhost:8000\n"
                ),
            },
            {
                "name": "requirements.txt",
                "kind": "text",
                "summary": "Python dependencies.",
                "content": (
                    "fastapi>=0.110.0\n"
                    "uvicorn[standard]>=0.27.0\n"
                    "sqlalchemy>=2.0.0\n"
                    "aiosqlite>=0.20.0\n"
                    "alembic>=1.13.0\n"
                    "python-jose[cryptography]>=3.3.0\n"
                    "passlib[bcrypt]>=1.7.4\n"
                    "python-multipart>=0.0.9\n"
                    "pydantic>=2.6.0\n"
                    "pydantic-settings>=2.2.0\n"
                    "httpx>=0.27.0\n"
                    "pytest>=8.0.0\n"
                    "pytest-asyncio>=0.23.0\n"
                ),
            },
            {
                "name": "tests/test_api.py",
                "kind": "python",
                "summary": "API smoke tests.",
                "content": (
                    "import pytest\n"
                    "from httpx import AsyncClient, ASGITransport\n"
                    "from backend.main import app\n\n"
                    "@pytest.mark.asyncio\n"
                    "async def test_health():\n"
                    "    async with AsyncClient(transport=ASGITransport(app=app), base_url='http://test') as client:\n"
                    "        resp = await client.get('/health')\n"
                    "    assert resp.status_code == 200\n"
                    "    assert resp.json()['status'] == 'ok'\n"
                ),
            },
        ],
        "frontend": [
            {
                "name": "index.html",
                "kind": "html",
                "summary": "HTML shell.",
                "content": (
                    "<!DOCTYPE html>\n<html lang='en'>\n<head>\n"
                    "  <meta charset='UTF-8'/>\n"
                    "  <meta name='viewport' content='width=device-width, initial-scale=1.0'/>\n"
                    f"  <title>{label}</title>\n"
                    "</head>\n<body>\n"
                    "  <div id='root'></div>\n"
                    "  <script type='module' src='/src/main.jsx'></script>\n"
                    "</body>\n</html>\n"
                ),
            },
            {
                "name": "package.json",
                "kind": "json",
                "summary": "Frontend dependencies.",
                "content": (
                    "{\n"
                    f'  "name": "{label.lower().replace(" ", "-")}",\n'
                    '  "version": "0.1.0",\n'
                    '  "private": true,\n'
                    '  "scripts": {\n'
                    '    "dev": "vite",\n'
                    '    "build": "vite build",\n'
                    '    "preview": "vite preview"\n'
                    "  },\n"
                    '  "dependencies": {\n'
                    '    "react": "^18.2.0",\n'
                    '    "react-dom": "^18.2.0",\n'
                    '    "react-router-dom": "^6.22.0",\n'
                    '    "axios": "^1.6.0"\n'
                    "  },\n"
                    '  "devDependencies": {\n'
                    '    "@vitejs/plugin-react": "^4.2.0",\n'
                    '    "vite": "^5.1.0",\n'
                    '    "tailwindcss": "^3.4.0"\n'
                    "  }\n"
                    "}\n"
                ),
            },
            {
                "name": "src/main.jsx",
                "kind": "javascript",
                "summary": "React entry point.",
                "content": (
                    "import React from 'react';\n"
                    "import ReactDOM from 'react-dom/client';\n"
                    "import { BrowserRouter } from 'react-router-dom';\n"
                    "import App from './App';\n"
                    "import './styles/globals.css';\n\n"
                    "ReactDOM.createRoot(document.getElementById('root')).render(\n"
                    "  <React.StrictMode>\n"
                    "    <BrowserRouter><App /></BrowserRouter>\n"
                    "  </React.StrictMode>\n"
                    ");\n"
                ),
            },
            {
                "name": "src/App.jsx",
                "kind": "javascript",
                "summary": "Route definitions.",
                "content": (
                    "import { Routes, Route, Navigate } from 'react-router-dom';\n"
                    "import LandingPage from './pages/LandingPage';\n"
                    "import LoginPage from './pages/LoginPage';\n"
                    "import Dashboard from './pages/Dashboard';\n\n"
                    "export default function App() {\n"
                    "  return (\n"
                    "    <Routes>\n"
                    "      <Route path='/' element={<LandingPage />} />\n"
                    "      <Route path='/login' element={<LoginPage />} />\n"
                    "      <Route path='/dashboard' element={<Dashboard />} />\n"
                    "      <Route path='*' element={<Navigate to='/' />} />\n"
                    "    </Routes>\n"
                    "  );\n"
                    "}\n"
                ),
            },
            {
                "name": "src/lib/api.js",
                "kind": "javascript",
                "summary": "Axios API client.",
                "content": (
                    "import axios from 'axios';\n\n"
                    "const api = axios.create({ baseURL: import.meta.env.VITE_API_URL || 'http://localhost:8000' });\n\n"
                    "api.interceptors.request.use(cfg => {\n"
                    "  const token = localStorage.getItem('token');\n"
                    "  if (token) cfg.headers.Authorization = `Bearer ${token}`;\n"
                    "  return cfg;\n"
                    "});\n\n"
                    "export const auth = {\n"
                    "  login: (email, password) => api.post('/api/auth/token', { email, password }),\n"
                    "  register: (email, password) => api.post('/api/auth/register', { email, password }),\n"
                    "};\n\n"
                    "export default api;\n"
                ),
            },
            {
                "name": "src/pages/Dashboard.jsx",
                "kind": "javascript",
                "summary": f"Main dashboard for {label}.",
                "content": (
                    "import React, { useEffect, useState } from 'react';\n"
                    "import api from '../lib/api';\n\n"
                    "export default function Dashboard() {\n"
                    "  const [data, setData] = useState(null);\n"
                    "  const [loading, setLoading] = useState(true);\n"
                    "  const [error, setError] = useState(null);\n\n"
                    "  useEffect(() => {\n"
                    "    api.get('/api/items')\n"
                    "      .then(r => setData(r.data))\n"
                    "      .catch(e => setError(e.message))\n"
                    "      .finally(() => setLoading(false));\n"
                    "  }, []);\n\n"
                    "  if (loading) return <div className='p-8 text-center'>Loading...</div>;\n"
                    "  if (error) return <div className='p-8 text-red-500'>{error}</div>;\n\n"
                    "  return (\n"
                    "    <div className='p-8'>\n"
                    f"      <h1 className='text-2xl font-bold mb-4'>{label} Dashboard</h1>\n"
                    "      <pre className='bg-gray-100 rounded p-4 text-sm overflow-auto'>{JSON.stringify(data, null, 2)}</pre>\n"
                    "    </div>\n"
                    "  );\n"
                    "}\n"
                ),
            },
        ],
        "docs": [
            {
                "name": "README.md",
                "kind": "markdown",
                "summary": f"README for {label}.",
                "content": (
                    f"# {label}\n\n"
                    f"> {idea[:120]}\n\n"
                    "## Quick Start\n\n"
                    "```bash\n"
                    "# Backend\n"
                    "cd backend && pip install -r requirements.txt\n"
                    "cp .env.example .env   # fill in your values\n"
                    "uvicorn backend.main:app --reload --port 8000\n\n"
                    "# Frontend\n"
                    "npm install && npm run dev\n"
                    "```\n\n"
                    "## Tech Stack\n\n"
                    "| Layer | Technology |\n"
                    "|-------|------------|\n"
                    "| Frontend | React + Vite + Tailwind CSS |\n"
                    "| Backend | FastAPI + SQLAlchemy |\n"
                    "| Database | SQLite (dev) / PostgreSQL (prod) |\n"
                    "| Auth | JWT (python-jose + bcrypt) |\n\n"
                    "## Environment Variables\n\n"
                    "See `.env.example` for all required variables.\n"
                ),
            },
            {
                "name": "docs/ARCHITECTURE.md",
                "kind": "markdown",
                "summary": "Architecture overview.",
                "content": (
                    f"# {label} — Architecture\n\n"
                    "```\n"
                    "Browser → React (Vite) → Axios → FastAPI → SQLAlchemy → SQLite/PostgreSQL\n"
                    "```\n\n"
                    "## Frontend\n\n"
                    "- **Frontend** (`src/`): React SPA with React Router, Tailwind CSS, Axios\n\n"
                    "## Backend\n\n"
                    "- **Backend** (`backend/`): FastAPI with async SQLAlchemy and JWT auth\n\n"
                    "## Data\n\n"
                    "- **Database** (`docs/DATABASE_SCHEMA.sql`): relational schema and seed data\n\n"
                    "## Auth\n\n"
                    "- JWT login/register routes with backend-only secret handling\n"
                ),
            },
            {
                "name": "docs/API_SPEC.md",
                "kind": "markdown",
                "summary": "API endpoint reference.",
                "content": (
                    f"# {label} — API Reference\n\n"
                    "## Auth\n\n"
                    "### `POST /api/auth/register`\n"
                    "Register a new user.\n\n"
                    "**Body:** `{ email, password }`  \n"
                    "**Response:** `{ access_token, token_type }`\n\n"
                    "### `POST /api/auth/token`\n"
                    "Login and receive a JWT.\n\n"
                    "**Body:** `{ email, password }`  \n"
                    "**Response:** `{ access_token, token_type }`\n\n"
                    "## Items\n\n"
                    "### `GET /api/items`\n"
                    "List all items. Requires auth.\n\n"
                    "### `POST /api/items`\n"
                    "Create an item. Requires auth.\n\n"
                    "### `GET /api/items/{id}`\n"
                    "Get item by ID.\n\n"
                    "### `PUT /api/items/{id}`\n"
                    "Update item.\n\n"
                    "### `DELETE /api/items/{id}`\n"
                    "Delete item.\n"
                ),
            },
            {
                "name": "docs/DEPLOY.md",
                "kind": "markdown",
                "summary": "Deployment guide.",
                "content": (
                    f"# {label} — Deployment\n\n"
                    "## Frontend → Vercel\n\n"
                    "1. Connect GitHub repo to Vercel\n"
                    "2. Set `VITE_API_URL` to your backend URL\n"
                    "3. Deploy\n\n"
                    "## Backend → Railway / Render\n\n"
                    "1. Set `DATABASE_URL` to your Postgres connection string\n"
                    "2. Set `SECRET_KEY` to a secure random value\n"
                    "3. Start command: `uvicorn backend.main:app --host 0.0.0.0 --port $PORT`\n"
                ),
            },
        ],
        "demo_video": [
            {
                "name": "demo/script.md",
                "kind": "markdown",
                "summary": f"Timestamped recording script for {label}.",
                "content": (
                    f"# {label} Demo Script\n\n"
                    "## 0:00 - Hook\n\n"
                    f"Introduce the user problem behind {idea}.\n\n"
                    "## 0:25 - Product Flow\n\n"
                    "Sign in with the demo account, open the dashboard, create sample data, and complete the core workflow.\n\n"
                    "## 1:30 - Technical Proof\n\n"
                    "Show the frontend route, backend API response, database schema, tests, and deployment guide.\n\n"
                    "## 2:30 - Close\n\n"
                    "Summarize the hackathon-ready value and point judges to README.md and docs/HACKATHON_SUBMISSION.md.\n"
                ),
            },
            {
                "name": "demo/storyboard.md",
                "kind": "markdown",
                "summary": f"Storyboard for the {label} demo recording.",
                "content": (
                    f"# {label} Storyboard\n\n"
                    "| Time | Shot | Proof |\n"
                    "| --- | --- | --- |\n"
                    "| 0:00 | App landing/dashboard | Clear project identity and problem |\n"
                    "| 0:25 | Authenticated workspace | Login and role-aware UI |\n"
                    "| 0:55 | Core workflow | User creates or uploads sample data |\n"
                    "| 1:30 | API/docs/tests | Backend, schema, tests, and deployment proof |\n"
                ),
            },
            {
                "name": "demo/demo_walkthrough.md",
                "kind": "markdown",
                "summary": f"Click-by-click walkthrough for {label}.",
                "content": (
                    f"# {label} Demo Walkthrough\n\n"
                    "1. Install dependencies and copy `.env.example`.\n"
                    "2. Start the backend with `uvicorn backend.main:app --reload`.\n"
                    "3. Start the frontend with `npm run dev`.\n"
                    "4. Sign in, run the core workflow, and show generated/sample data in the dashboard.\n"
                    "5. Open docs/API_SPEC.md, docs/DATABASE_SCHEMA.sql, and tests to show technical completeness.\n"
                ),
            },
            {
                "name": "demo/video_outline.md",
                "kind": "markdown",
                "summary": f"Video outline for {label}.",
                "content": (
                    f"# {label} Video Outline\n\n"
                    "- Opening hook: the user pain and why this project matters.\n"
                    "- Product proof: dashboard, workflow, sample data, and result state.\n"
                    "- Technical proof: frontend, backend routes, database schema, tests, env, deployment.\n"
                    "- Submission close: what is demo-ready today and what comes next.\n"
                ),
            },
            {
                "name": "demo/voiceover.md",
                "kind": "markdown",
                "summary": f"Optional voiceover for {label}.",
                "content": (
                    f"# {label} Voiceover\n\n"
                    f"Today we are showing {label}, a complete full-stack hackathon project for: {idea}. "
                    "The demo starts with a signed-in user, moves through the real product workflow, "
                    "and ends with API, database, test, and deployment proof inside the generated repository.\n"
                ),
            },
        ],
    }

    stage_key = stage.replace("generate_", "")
    files_data = _stage_files.get(stage_key, [])
    files = [
        GeneratedFileWithContent(
            name=f["name"],
            kind=f["kind"],
            summary=f["summary"],
            content=f["content"],
        )
        for f in files_data
    ]

    return GeneratedFileBatchOutput(
        stage=stage_key,
        files=files,
        mode=mode,
        decision_trace=_trace(
            mode,
            fallback_reason,
            [
                f"Mock {stage_key} stage: generated {len(files)} scaffold file(s) for {label}.",
                "Live LLM call will replace these with product-specific implementations.",
            ],
        ),
    ).model_dump()
