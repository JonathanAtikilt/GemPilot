from agent.prompts import build_plan_repo_prompt, build_scope_mvp_prompt


def _default_build_context() -> dict:
    return {
        "requiredDeliverables": [],
        "allowedToolsAndAPIs": [],
        "requiredRepositoryFormat": [],
        "requiredDemoFormat": [],
        "requiredTechStackPieces": [],
        "resolvedTechStack": {
            "source": "default",
            "items": [
                "Next.js",
                "React",
                "TypeScript",
                "Tailwind CSS",
                "Python 3.12",
                "FastAPI",
                "Uvicorn",
                "Supabase Postgres",
                "pgvector",
                "NVIDIA Nemotron",
                "pytest",
                "npm run build",
            ],
            "requiredItems": [],
            "defaultItems": [
                "Next.js",
                "React",
                "TypeScript",
                "Tailwind CSS",
                "Python 3.12",
                "FastAPI",
                "Uvicorn",
                "Supabase Postgres",
                "pgvector",
                "NVIDIA Nemotron",
                "pytest",
                "npm run build",
            ],
            "reason": "No required or preferred stack was found.",
        },
    }


def test_scope_mvp_prompt_includes_resolved_tech_stack_and_override_rule() -> None:
    prompt = build_scope_mvp_prompt(
        idea="Build a judge helper",
        build_context=_default_build_context(),
        memory_matches=[],
    )

    assert "resolvedTechStack" in prompt
    assert "required stack items override MVPilot defaults" in prompt
    assert "Retrieved docs" not in prompt


def test_plan_repo_prompt_includes_default_stack_when_rag_is_silent() -> None:
    prompt = build_plan_repo_prompt(
        idea="Build a judge helper",
        mvp_scope={"must_have": ["intake"]},
        build_context=_default_build_context(),
    )

    assert "Next.js" in prompt
    assert "FastAPI" in prompt
    assert "Supabase Postgres" in prompt
    assert "required stack items override MVPilot defaults" in prompt
    assert "generated files, tests, and architecture" in prompt
