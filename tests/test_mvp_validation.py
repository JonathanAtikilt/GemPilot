from agent.generated_project import build_project_artifacts
from agent.mvp_depth import enrich_mvp_scope
from agent.mvp_validation import validate_mvp_output


def test_validate_mvp_output_passes_for_idea_specific_artifacts():
    idea = "StudyPilot helps students plan study sessions with spaced repetition."
    scope = enrich_mvp_scope(
        {
            "must_have": [
                "Capture study goals and session length",
                "Generate a spaced-repetition schedule",
            ]
        },
        idea=idea,
        intake={
            "title": "StudyPilot",
            "requiredFeatures": [
                "Capture study goals and session length",
                "Generate a spaced-repetition schedule",
            ],
        },
    )
    artifacts = build_project_artifacts(
        idea=idea,
        title="StudyPilot",
        resolved_stack="React, FastAPI",
        required_features=[
            "Capture study goals and session length",
            "Generate a spaced-repetition schedule",
        ],
        mvp_scope=scope,
    )
    validation = validate_mvp_output(
        idea=idea,
        intake={
            "title": "StudyPilot",
            "requiredFeatures": [
                "Capture study goals and session length",
                "Generate a spaced-repetition schedule",
            ],
        },
        mvp_scope=scope,
        repo_plan={"files": ["README.md", "src/App.jsx"], "implementation_steps": ["a"]},
        generated_artifacts=artifacts,
        model_modes=["partial"],
    )

    assert validation["passed"] is True
    assert validation["project_title"] == "StudyPilot"


def test_validate_mvp_output_allows_degraded_planning_when_manifest_is_live():
    idea = "StudyPilot helps students plan study sessions with spaced repetition."
    scope = enrich_mvp_scope(
        {
            "must_have": [
                "Capture study goals and session length",
                "Generate a spaced-repetition schedule",
            ]
        },
        idea=idea,
        intake={
            "title": "StudyPilot",
            "requiredFeatures": [
                "Capture study goals and session length",
                "Generate a spaced-repetition schedule",
            ],
        },
    )
    artifacts = build_project_artifacts(
        idea=idea,
        title="StudyPilot",
        resolved_stack="React, FastAPI",
        required_features=[
            "Capture study goals and session length",
            "Generate a spaced-repetition schedule",
        ],
        mvp_scope=scope,
    )
    validation = validate_mvp_output(
        idea=idea,
        intake={
            "title": "StudyPilot",
            "requiredFeatures": [
                "Capture study goals and session length",
                "Generate a spaced-repetition schedule",
            ],
        },
        mvp_scope=scope,
        repo_plan={"files": ["README.md", "src/App.jsx"], "implementation_steps": ["a"]},
        generated_artifacts=artifacts,
        model_modes=["degraded", "degraded", "live"],
        require_live_manifest=True,
        manifest_model_mode="live",
    )

    live_check = next(
        check for check in validation["checks"] if check["name"] == "live_manifest_only"
    )
    assert live_check["passed"] is True
    assert validation["passed"] is True


def test_validate_mvp_output_rejects_non_live_manifest_when_required():
    idea = "StudyPilot helps students plan study sessions with spaced repetition."
    scope = enrich_mvp_scope(
        {"must_have": ["Capture study goals", "Generate a schedule"]},
        idea=idea,
        intake={"title": "StudyPilot"},
    )
    artifacts = build_project_artifacts(
        idea=idea,
        title="StudyPilot",
        resolved_stack="React, FastAPI",
        required_features=["Capture study goals", "Generate a schedule"],
        mvp_scope=scope,
    )
    validation = validate_mvp_output(
        idea=idea,
        intake={"title": "StudyPilot"},
        mvp_scope=scope,
        repo_plan={"files": ["README.md"], "implementation_steps": ["a"]},
        generated_artifacts=artifacts,
        model_modes=["degraded", "partial"],
        require_live_manifest=True,
        manifest_model_mode="degraded",
    )

    live_check = next(
        check for check in validation["checks"] if check["name"] == "live_manifest_only"
    )
    assert live_check["passed"] is False
    assert validation["passed"] is False


def test_validate_mvp_output_allows_degraded_manifest_when_partial_enabled():
    idea = "Healthcare referral app for clinics."
    artifacts = [
        {
            "name": "docs/BUILD_LOG.md",
            "content": "# Build Log\n\n- Generation mode: explicit **degraded** path.\n",
        },
        {"name": "README.md", "content": "# HealthRef\n\nHealthcare referral app.\n"},
    ]
    validation = validate_mvp_output(
        idea=idea,
        intake={"title": "HealthRef"},
        mvp_scope={"must_have": ["Route referrals", "Track eligibility", "Audit logs", "Dashboard"]},
        repo_plan={"files": ["README.md"], "implementation_steps": ["Build app"]},
        generated_artifacts=artifacts,
        model_modes=["degraded"],
        require_live_manifest=True,
        manifest_model_mode="degraded",
        allow_degraded_manifest=True,
    )

    live_check = next(
        check for check in validation["checks"] if check["name"] == "live_manifest_only"
    )
    assert live_check["passed"] is True


def test_validate_mvp_output_patches_sparse_architecture_doc():
    idea = "Fleet maintenance copilot for mechanics."
    artifacts = [
        {
            "name": "docs/ARCHITECTURE.md",
            "content": "# Fleet Copilot\n\nClient and server overview only.\n",
        },
        {"name": "README.md", "content": "# Fleet Copilot\n\nFleet maintenance copilot for mechanics.\n"},
    ]
    validation = validate_mvp_output(
        idea=idea,
        intake={"title": "Fleet Copilot"},
        mvp_scope={
            "must_have": [
                "Capture work orders",
                "Track maintenance history",
                "Mechanic dashboard",
                "Parts inventory alerts",
            ]
        },
        repo_plan={"files": ["README.md"], "implementation_steps": ["Build app"]},
        generated_artifacts=artifacts,
        model_modes=["degraded"],
    )

    arch_check = next(
        check for check in validation["checks"] if check["name"] == "architecture_documents_full_system"
    )
    assert arch_check["passed"] is True


def test_validate_mvp_output_accepts_architecture_synonyms():
    idea = "Fleet maintenance copilot for mechanics."
    artifacts = [
        {
            "name": "docs/ARCHITECTURE.md",
            "content": (
                "# Fleet Copilot\n\n"
                "## Client-side\nReact UI.\n\n"
                "## Server\nFastAPI services.\n\n"
                "## Database\nPostgreSQL schema.\n\n"
                "## Authentication\nJWT login.\n"
            ),
        },
        {"name": "README.md", "content": "# Fleet Copilot\n\nFleet maintenance copilot for mechanics.\n"},
    ]
    validation = validate_mvp_output(
        idea=idea,
        intake={"title": "Fleet Copilot"},
        mvp_scope={
            "must_have": [
                "Capture work orders",
                "Track maintenance history",
                "Mechanic dashboard",
                "Parts inventory alerts",
            ]
        },
        repo_plan={"files": ["README.md"], "implementation_steps": ["Build app"]},
        generated_artifacts=artifacts,
        model_modes=["live"],
    )

    arch_check = next(
        check for check in validation["checks"] if check["name"] == "architecture_documents_full_system"
    )
    assert arch_check["passed"] is True


def test_validate_mvp_output_documents_degraded_mode_in_logs():
    from agent.project_validation import ensure_degraded_mode_documented

    idea = "Healthcare referral app for clinics."
    artifacts = [
        {
            "name": "docs/BUILD_LOG.md",
            "content": "# Build Log\n\n- Generated project files.\n",
        },
        {
            "name": "README.md",
            "content": "# HealthRef\n\nHealthcare referral coordination app.\n",
        },
    ]
    validation = validate_mvp_output(
        idea=idea,
        intake={"title": "HealthRef"},
        mvp_scope={"must_have": ["Route referrals", "Track eligibility", "Audit logs", "Dashboard"]},
        repo_plan={"files": ["README.md"], "implementation_steps": ["Build app"]},
        generated_artifacts=artifacts,
        model_modes=["live", "degraded"],
    )

    degraded_check = next(
        check for check in validation["checks"] if check["name"] == "degraded_mode_explicit"
    )
    assert degraded_check["passed"] is True
    patched = ensure_degraded_mode_documented(artifacts, ["degraded"])
    assert "degraded" in patched[0]["content"].lower()


def test_validate_mvp_output_rejects_generic_feature_trio():
    idea = "Fleet maintenance copilot for mechanics."
    validation = validate_mvp_output(
        idea=idea,
        intake={"title": "Fleet Copilot"},
        mvp_scope={
            "must_have": [
                "Capture intake details for the target workflow",
                "Generate a prioritized mvp action plan",
                "Expose demo data through a small fastapi surface",
            ]
        },
        repo_plan={"files": ["README.md"]},
        generated_artifacts=[],
        model_modes=["fallback"],
    )

    assert validation["passed"] is False
    assert any(check["name"] == "no_generic_fallback_features" for check in validation["checks"])


def test_validate_mvp_output_prefers_latest_repair_artifact():
    idea = "Fleet maintenance copilot for mechanics."
    scope = enrich_mvp_scope(
        {"must_have": ["Track fleet maintenance requests", "Prioritize mechanic repair work"]},
        idea=idea,
        intake={
            "title": "Fleet Maintenance Copilot",
            "requiredFeatures": ["Track fleet maintenance requests", "Prioritize mechanic repair work"],
        },
    )
    repaired = build_project_artifacts(
        idea=idea,
        title="Fleet Maintenance Copilot",
        resolved_stack="React, FastAPI",
        required_features=["Track fleet maintenance requests", "Prioritize mechanic repair work"],
        mvp_scope=scope,
    )
    validation = validate_mvp_output(
        idea=idea,
        intake={
            "title": "Fleet Maintenance Copilot",
            "requiredFeatures": ["Track fleet maintenance requests", "Prioritize mechanic repair work"],
        },
        mvp_scope=scope,
        repo_plan={"files": ["README.md", "src/App.jsx"], "implementation_steps": ["Generate workflow"]},
        generated_artifacts=[
            {
                "name": "README.md",
                "content": "# Starter app\n\nA generic todo app.",
            },
            *repaired,
        ],
        model_modes=["partial"],
    )

    assert validation["passed"] is True
