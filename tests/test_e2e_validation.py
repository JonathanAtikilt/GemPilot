"""
E2E-style validation tests for GemPilot covering three representative
project prompts plus edge-case project types.

These tests exercise the full generation → import-repair → validation
pipeline without a running server, using the same code paths the
live workflow runs.
"""
from __future__ import annotations

import pytest
from agent.generated_project import build_project_artifacts
from agent.mvp_depth import enrich_mvp_scope
from agent.mvp_validation import validate_mvp_output
from agent.project_generation import (
    detect_project_manifest,
    ensure_imports_resolve,
)
from agent.project_validation import (
    _artifact_map,
    _detect_stack_from_artifacts,
    _files_not_placeholder,
    _implementation_files_complete,
    _imports_resolve,
    validate_project_output,
)
from agent.project_depth import PROJECT_ARCHETYPES


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _run_full_pipeline(idea, title, stack, features, archetype, depth="Starter Project"):
    """Build → repair → validate, return the validation dict."""
    scope = enrich_mvp_scope(
        {"must_have": features, "core_features": features},
        idea=idea,
        intake={"title": title, "requiredFeatures": features},
    )
    if archetype in PROJECT_ARCHETYPES:
        scope["project_archetype"] = archetype
    scope["project_depth"] = depth

    artifacts = build_project_artifacts(
        idea=idea, title=title, resolved_stack=stack, required_features=features
    )
    artifacts = ensure_imports_resolve(
        artifacts, idea=idea, title=title, resolved_stack=stack, required_features=features
    )
    repo_plan = {
        "implementation_steps": ["Build frontend", "Build backend", "Connect DB"],
        "frontend": "React",
        "backend": "FastAPI",
        "data": "SQLite",
        "auth": "JWT",
    }
    return validate_mvp_output(
        idea=idea,
        intake={"title": title, "requiredFeatures": features},
        mvp_scope=scope,
        repo_plan=repo_plan,
        generated_artifacts=artifacts,
        model_modes=["live"],
    )


# ─────────────────────────────────────────────────────────────────────────────
# Prompt 1: SaaS Dashboard App
# ─────────────────────────────────────────────────────────────────────────────

class TestSaasDashboard:
    IDEA = (
        "TeamFlow: A SaaS project management dashboard for remote teams. "
        "Includes Kanban boards, sprint planning, and team productivity analytics."
    )
    TITLE = "TeamFlow"
    STACK = "React, FastAPI"
    FEATURES = [
        "Kanban task board",
        "Sprint planning",
        "Team analytics dashboard",
        "User authentication",
        "Real-time notifications",
        "Project creation and management",
        "Team member assignment",
    ]
    ARCHETYPE = "dashboard"

    @pytest.fixture(scope="class")
    def validation(self):
        return _run_full_pipeline(
            self.IDEA, self.TITLE, self.STACK, self.FEATURES, self.ARCHETYPE
        )

    def test_validation_passes(self, validation):
        failed = [c["name"] for c in validation["checks"] if not c["passed"]]
        assert validation["passed"] is True, f"Failed checks: {failed}"

    def test_all_checks_pass(self, validation):
        assert all(c["passed"] for c in validation["checks"]), (
            [c["name"] for c in validation["checks"] if not c["passed"]]
        )

    def test_project_title_matches(self, validation):
        assert validation["project_title"] == "TeamFlow"

    def test_detected_as_fullstack(self, validation):
        # The scaffold produces src/ and backend/ — must be detected as fullstack
        artifacts = build_project_artifacts(
            idea=self.IDEA, title=self.TITLE, resolved_stack=self.STACK,
            required_features=self.FEATURES
        )
        stack = _detect_stack_from_artifacts(artifacts)
        assert stack["project_type"] == "fullstack"
        assert stack["has_frontend"] is True
        assert stack["has_web_backend"] is True

    def test_imports_resolve_after_repair(self, validation):
        imports_check = next(
            c for c in validation["checks"] if c["name"] == "imports_resolve"
        )
        assert imports_check["passed"] is True

    def test_frontend_routes_present(self, validation):
        routes_check = next(
            c for c in validation["checks"] if c["name"] == "frontend_routes_or_pages_exist"
        )
        assert routes_check["passed"] is True

    def test_backend_routes_present(self, validation):
        routes_check = next(
            c for c in validation["checks"] if c["name"] == "backend_routes_exist"
        )
        assert routes_check["passed"] is True

    def test_database_models_present(self, validation):
        db_check = next(
            c for c in validation["checks"] if c["name"] == "database_models_used"
        )
        assert db_check["passed"] is True

    def test_demo_materials_generated(self, validation):
        demo_check = next(
            c for c in validation["checks"] if c["name"] == "demo_materials_generated"
        )
        assert demo_check["passed"] is True

    def test_seed_data_present(self, validation):
        seed_check = next(c for c in validation["checks"] if c["name"] == "seed_data_present")
        assert seed_check["passed"] is True

    def test_no_placeholder_content(self, validation):
        ph_check = next(
            c for c in validation["checks"] if c["name"] == "generated_files_not_placeholders"
        )
        assert ph_check["passed"] is True

    def test_readme_has_setup_and_features(self, validation):
        readme_check = next(
            c for c in validation["checks"] if c["name"] == "readme_setup_features_demo"
        )
        assert readme_check["passed"] is True


# ─────────────────────────────────────────────────────────────────────────────
# Prompt 2: AI/ML App with Backend Inference
# ─────────────────────────────────────────────────────────────────────────────

class TestAiMlApp:
    IDEA = (
        "NeuralQuery: AI-powered document Q&A platform. "
        "Upload PDFs, ask questions in natural language, get instant answers with source citations."
    )
    TITLE = "NeuralQuery"
    STACK = "React, FastAPI"
    FEATURES = [
        "PDF document upload",
        "Vector similarity search",
        "LLM-based question answering",
        "Source citation display",
        "Conversation history",
        "API rate limiting and auth",
    ]
    ARCHETYPE = "ai_system"

    @pytest.fixture(scope="class")
    def validation(self):
        return _run_full_pipeline(
            self.IDEA, self.TITLE, self.STACK, self.FEATURES, self.ARCHETYPE
        )

    def test_validation_passes(self, validation):
        failed = [c["name"] for c in validation["checks"] if not c["passed"]]
        assert validation["passed"] is True, f"Failed checks: {failed}"

    def test_all_checks_pass(self, validation):
        assert all(c["passed"] for c in validation["checks"]), (
            [c["name"] for c in validation["checks"] if not c["passed"]]
        )

    def test_idea_reflected_in_artifacts(self, validation):
        # readme and app source must mention the idea
        readme_check = next(c for c in validation["checks"] if c["name"] == "readme_specific")
        ui_check = next(c for c in validation["checks"] if c["name"] == "ui_specific")
        assert readme_check["passed"] is True
        assert ui_check["passed"] is True

    def test_implementation_files_complete(self, validation):
        check = next(
            c for c in validation["checks"] if c["name"] == "implementation_files_complete"
        )
        assert check["passed"] is True


# ─────────────────────────────────────────────────────────────────────────────
# Prompt 3: Mobile-first Social / Community App
# ─────────────────────────────────────────────────────────────────────────────

class TestMobileSocialApp:
    IDEA = (
        "VibeCircle: Mobile-first community platform for local interest groups. "
        "Create circles, post events with RSVP, group chat, discover local activity."
    )
    TITLE = "VibeCircle"
    STACK = "React, FastAPI"
    FEATURES = [
        "Create and join circles",
        "Post events with RSVP",
        "Real-time group chat",
        "User profiles and follow",
        "Location-based discovery",
        "Push notifications",
    ]
    ARCHETYPE = "marketplace"

    @pytest.fixture(scope="class")
    def validation(self):
        return _run_full_pipeline(
            self.IDEA, self.TITLE, self.STACK, self.FEATURES, self.ARCHETYPE
        )

    def test_validation_passes(self, validation):
        failed = [c["name"] for c in validation["checks"] if not c["passed"]]
        assert validation["passed"] is True, f"Failed checks: {failed}"

    def test_all_checks_pass(self, validation):
        assert all(c["passed"] for c in validation["checks"]), (
            [c["name"] for c in validation["checks"] if not c["passed"]]
        )

    def test_archetype_selected(self, validation):
        check = next(
            c for c in validation["checks"] if c["name"] == "project_archetype_selected"
        )
        assert check["passed"] is True


# ─────────────────────────────────────────────────────────────────────────────
# Import repair: adaptive behaviour across project types
# ─────────────────────────────────────────────────────────────────────────────

class TestImportRepairAdaptive:
    def test_repair_creates_stub_not_overwrite(self):
        """ensure_imports_resolve must create the missing file, not overwrite App.jsx."""
        original_content = (
            "import Dashboard from './components/Dashboard.jsx';\n"
            "export default function App(){return <Dashboard/>;}\n"
        )
        broken = [
            {"name": "src/App.jsx", "content": original_content},
            {"name": "src/main.jsx", "content": "import App from './App.jsx';\n"},
            {"name": "README.md", "content": "# Test\n"},
        ]
        repaired = ensure_imports_resolve(
            broken, idea="test", title="Test", resolved_stack="React",
        )
        by_name = {a["name"]: a for a in repaired}
        assert "src/components/Dashboard.jsx" in by_name, "stub must be created"
        assert by_name["src/App.jsx"]["content"] == original_content, "App.jsx must not be overwritten"
        assert _imports_resolve(_artifact_map(repaired))

    def test_python_stub_created_not_overwritten(self):
        """ensure_imports_resolve creates missing Python module stubs."""
        broken = [
            {"name": "backend/main.py", "content": "from backend.services import get_tasks\n"},
            {"name": "backend/models.py", "content": "from pydantic import BaseModel\nclass Task(BaseModel): pass\n"},
        ]
        repaired = ensure_imports_resolve(
            broken, idea="task app", title="Tasks", resolved_stack="FastAPI",
        )
        names = [a["name"] for a in repaired]
        assert "backend/services.py" in names
        assert _imports_resolve(_artifact_map(repaired))

    def test_asset_imports_always_ignored(self):
        files = {
            "src/App.jsx": (
                "import logo from './assets/logo.svg';\n"
                "import styles from './App.module.css';\n"
                "import data from './data.json';\n"
                "export default function App(){return null;}\n"
            ),
            "src/main.jsx": "import App from './App.jsx';\n",
        }
        assert _imports_resolve(files) is True

    def test_nextjs_alias_resolves_correctly(self):
        artifacts = [
            {"name": "app/page.tsx", "content": "import Hero from '@/components/Hero';export default function P(){return <Hero/>;}"},
            {"name": "app/components/Hero.tsx", "content": "export default function Hero(){return null;}"},
            {"name": "tsconfig.json", "content": '{"compilerOptions":{"paths":{"@/*":["./app/*"]}}}'},
            {"name": "package.json", "content": '{"dependencies":{"next":"^14","react":"^18"}}'},
        ]
        manifest = detect_project_manifest(artifacts)
        assert manifest["project_type"] == "nextjs"
        assert manifest["js_aliases"]["@/"] == "app/"
        files = _artifact_map(artifacts)
        assert _imports_resolve(files, js_aliases=manifest["js_aliases"]) is True

    def test_custom_vite_alias_resolves(self):
        artifacts = [
            {"name": "src/App.jsx", "content": "import api from '@/lib/api';export default function App(){return null;}"},
            {"name": "src/lib/api.js", "content": "export default {};"},
            {"name": "vite.config.js", "content": "import {resolve} from 'path';\nexport default {resolve:{alias:{'@':resolve(__dirname,'src')}}};"},
            {"name": "package.json", "content": '{"dependencies":{"react":"^18","vite":"^4"}}'},
        ]
        manifest = detect_project_manifest(artifacts)
        assert manifest["js_aliases"]["@/"] == "src/"
        files = _artifact_map(artifacts)
        assert _imports_resolve(files, js_aliases=manifest["js_aliases"]) is True

    def test_flask_app_in_app_directory(self):
        broken = [
            {"name": "app/main.py", "content": "from app.models import User\nfrom flask import Flask\napp=Flask(__name__)\n"},
            {"name": "requirements.txt", "content": "flask\n"},
        ]
        repaired = ensure_imports_resolve(
            broken, idea="flask auth", title="Auth", resolved_stack="Flask",
        )
        names = [a["name"] for a in repaired]
        assert "app/models.py" in names
        assert _imports_resolve(_artifact_map(repaired))

    def test_orphan_unreferenced_file_repaired_not_deleted(self):
        """An orphan JS file's missing import is stubbed by Pass 2, so the file is kept
        (not deleted) because it is no longer *still failing* — satisfying the spec that
        only files that are unreferenced AND still failing are dropped."""
        artifacts = [
            {"name": "src/App.jsx", "content": "export default function App(){return null;}"},
            {"name": "src/main.jsx", "content": "import App from './App.jsx';\n"},
            # orphan: not imported anywhere, but has a broken import inside
            {"name": "src/orphan.jsx", "content": "import X from './nonexistent/deep/path.jsx';\nexport default function Orphan(){return null;}"},
        ]
        repaired = ensure_imports_resolve(
            artifacts, idea="app", title="App", resolved_stack="React",
        )
        names = [a["name"] for a in repaired]
        # Pass 2 stubs the missing import → orphan is no longer "still failing" → kept
        assert "src/orphan.jsx" in names
        assert _imports_resolve(_artifact_map(repaired))

    def test_entrypoint_kept_even_if_broken(self):
        """main.jsx is an entrypoint; it must never be deleted even if it has an import issue."""
        artifacts = [
            {"name": "src/App.jsx", "content": "export default function App(){return null;}"},
            {"name": "src/main.jsx", "content": "import App from './App.jsx';\nimport Missing from './missing.jsx';\n"},
        ]
        repaired = ensure_imports_resolve(
            artifacts, idea="app", title="App", resolved_stack="React",
        )
        names = [a["name"] for a in repaired]
        assert "src/main.jsx" in names, "entrypoint must not be deleted"


# ─────────────────────────────────────────────────────────────────────────────
# Stack-aware validation edge cases
# ─────────────────────────────────────────────────────────────────────────────

class TestStackAwareValidation:
    def test_nextjs_frontend_only_passes_without_backend_checks(self):
        """A Next.js-only project should not fail on backend_routes_exist or database_models_used."""
        arts = [
            {"name": "app/page.tsx", "content": "export default function Page(){return <div>VibeCheck</div>;}"},
            {"name": "app/layout.tsx", "content": "export default function Layout({children}){return <html><body>{children}</body></html>;}"},
            {"name": "app/globals.css", "content": "body{}"},
            {"name": "README.md", "content": "# VibeCheck\n\nVibeCheck frontend app for mood tracking.\n\n## Setup\nnpx next dev\n\n## Features\n- Mood board\n## Demo\ndemo/script.md"},
            {"name": "docs/ARCHITECTURE.md", "content": "# VibeCheck Architecture\n\n## Frontend\nNext.js app\n## Backend\nNone\n## Data\nLocalStorage\n## Auth\nNone"},
            {"name": "docs/API_SPEC.md", "content": "# API: N/A — static frontend"},
            {"name": "docs/DATABASE_SCHEMA.sql", "content": "-- No DB; data is in localStorage\nCREATE TABLE moods (id INTEGER PRIMARY KEY);"},
            {"name": "docs/DEPLOY.md", "content": "# Deploy\nnpx next build"},
            {"name": "tests/test_backend.py", "content": "def test_page_renders(): assert True"},
            {"name": "data/seed.json", "content": '[{"id":1,"mood":"happy"}]'},
            {"name": "scripts/seed_data.py", "content": "import json\ndata=json.load(open('data/seed.json'))"},
            {"name": "demo/script.md", "content": "# Demo VibeCheck mood tracking"},
            {"name": "demo/storyboard.md", "content": "# Storyboard VibeCheck"},
            {"name": "demo/demo_walkthrough.md", "content": "# Walkthrough VibeCheck mood board"},
            {"name": "demo/video_outline.md", "content": "# Video VibeCheck demo"},
            {"name": "next.config.js", "content": "module.exports={};"},
            {"name": "package.json", "content": '{"dependencies":{"next":"^14","react":"^18"}}'},
        ]
        validation = validate_project_output(
            idea="VibeCheck: a mood tracking app for daily emotional journaling.",
            intake={"title": "VibeCheck"},
            project_requirements={
                "core_features": ["Mood board", "Daily journal", "Streak tracking", "Shareable card"],
                "project_archetype": "dashboard",
                "project_depth": "Starter Project",
                "user_flows": [
                    {"step": "1", "action": "Log mood", "screen": "Home", "api": "N/A"},
                    {"step": "2", "action": "View history", "screen": "History", "api": "N/A"},
                ],
            },
            architecture_plan={"implementation_steps": ["Build Next.js"], "frontend": "Next.js", "backend": "None", "data": "localStorage", "auth": "None"},
            generated_artifacts=arts,
            model_modes=["live"],
        )
        stack = _detect_stack_from_artifacts(arts)
        assert stack["has_web_backend"] is False
        # Neither of these should be critical for a frontend-only project
        for check_name in ("backend_routes_exist", "database_models_used"):
            check = next(c for c in validation["checks"] if c["name"] == check_name)
            # The check passes trivially when has_web_backend is False
            assert check["passed"] is True, f"{check_name} should pass for frontend-only project"

    def test_python_cli_passes_without_frontend_or_api_checks(self):
        """A Python CLI project must not be failed for missing frontend or HTTP routes."""
        arts = [
            {"name": "main.py", "content": "from cli.runner import run\nif __name__ == '__main__': run()"},
            {"name": "cli/__init__.py", "content": ""},
            {"name": "cli/runner.py", "content": "def run():\n    print('Processing data')"},
            {"name": "README.md", "content": "# DataCLI\n\nData processing CLI.\n\n## Setup\npip install .\n\n## Features\n- ingest\n- transform\n## Demo\ndemo/script.md"},
            {"name": "docs/ARCHITECTURE.md", "content": "# Architecture\n## Frontend\nCLI\n## Backend\nPython\n## Data\nFile\n## Auth\nNone"},
            {"name": "docs/API_SPEC.md", "content": "# CLI: python main.py"},
            {"name": "docs/DATABASE_SCHEMA.sql", "content": "CREATE TABLE runs (id INTEGER PRIMARY KEY);"},
            {"name": "docs/DEPLOY.md", "content": "# Deploy\npip install -e ."},
            {"name": "tests/test_backend.py", "content": "from cli.runner import run\ndef test_run(): run()"},
            {"name": "data/seed.json", "content": '[{"id":1,"value":"sample"}]'},
            {"name": "scripts/seed_data.py", "content": "import json\ndata=json.load(open('data/seed.json'))"},
            {"name": "demo/script.md", "content": "# Demo DataCLI pipeline"},
            {"name": "demo/storyboard.md", "content": "# Storyboard DataCLI"},
            {"name": "demo/demo_walkthrough.md", "content": "# Walkthrough DataCLI ingestion"},
            {"name": "demo/video_outline.md", "content": "# Video DataCLI demo"},
            {"name": "pyproject.toml", "content": "[project]\nname='datacli'\n"},
        ]
        validation = validate_project_output(
            idea="DataCLI: a Python CLI tool for ingesting and transforming CSV files.",
            intake={"title": "DataCLI"},
            project_requirements={
                "core_features": ["Data ingestion", "Transform pipeline", "Output formatting", "Config management"],
                "project_archetype": "workflow",
                "project_depth": "Starter Project",
                "user_flows": [
                    {"step": "1", "action": "ingest", "screen": "CLI", "api": "N/A"},
                    {"step": "2", "action": "transform", "screen": "CLI", "api": "N/A"},
                ],
            },
            architecture_plan={"implementation_steps": ["Build CLI"], "frontend": "CLI", "backend": "Python", "data": "File", "auth": "None"},
            generated_artifacts=arts,
            model_modes=["live"],
        )
        assert validation["passed"] is True, (
            [c["name"] for c in validation["checks"] if not c["passed"]]
        )
        stack = _detect_stack_from_artifacts(arts)
        assert stack["has_web_backend"] is False
        assert stack["has_frontend"] is False

    def test_empty_init_py_allowed_in_any_package(self):
        files = {
            "myapp/__init__.py": "",
            "myapp/utils/__init__.py": "",
            "myapp/utils/helpers.py": "def helper(): return True",
        }
        assert _files_not_placeholder(files) is True

    def test_implementation_files_complete_for_web_fullstack(self):
        artifacts = build_project_artifacts(
            idea="task tracker", title="Tasks",
            resolved_stack="React, FastAPI", required_features=["create tasks", "view tasks", "delete tasks", "user auth"],
        )
        stack = _detect_stack_from_artifacts(artifacts)
        assert stack["has_web_backend"] is True
        assert _implementation_files_complete(artifacts, stack) is True

    def test_implementation_files_complete_for_python_cli(self):
        arts = [
            {"name": "main.py", "content": "print('cli')"},
            {"name": "pyproject.toml", "content": "[project]\nname='cli'\n"},
        ]
        stack = _detect_stack_from_artifacts(arts)
        assert stack["has_web_backend"] is False
        # CLI doesn't need model/service files
        assert _implementation_files_complete(arts, stack) is True


# ─────────────────────────────────────────────────────────────────────────────
# GitHub upload contract (pure request/response shape, no network calls)
# ─────────────────────────────────────────────────────────────────────────────

class TestGitHubUploadContract:
    """Validate the Pydantic model that the frontend POSTs to /api/github/upload-project."""

    def test_upload_request_rejects_empty_files(self):
        try:
            from agent.routers.github import GitHubUploadProjectRequest
        except ImportError:
            pytest.skip("server deps not installed in this environment")
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            GitHubUploadProjectRequest(
                projectId="proj-123",
                repoPreference="create_new_repo",
                repoName="test-repo",
                files=[],  # min_length=1 must reject this
            )

    def test_upload_request_valid_payload(self):
        try:
            from agent.routers.github import GitHubUploadFile, GitHubUploadProjectRequest
        except ImportError:
            pytest.skip("server deps not installed in this environment")
        req = GitHubUploadProjectRequest(
            projectId="proj-abc",
            repoPreference="create_new_repo",
            repoName="my-saas-app",
            repoDescription="Generated by GemPilot",
            visibility="private",
            files=[GitHubUploadFile(path="README.md", content="# Hello")],
            githubConnectionId="conn-xyz",
        )
        assert req.projectId == "proj-abc"
        assert req.visibility == "private"
        assert len(req.files) == 1

    def test_upload_request_rejects_extra_fields(self):
        try:
            from agent.routers.github import GitHubUploadProjectRequest
        except ImportError:
            pytest.skip("server deps not installed in this environment")
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            GitHubUploadProjectRequest(
                projectId="p",
                files=[{"path": "README.md", "content": "x"}],
                unknown_field="should fail",
            )
