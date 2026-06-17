from agent.generated_project import build_project_artifacts
from agent.project_generation import ensure_imports_resolve
from agent.project_validation import _artifact_map, _imports_resolve, validate_project_output


def _validation_for(artifacts):
    idea = "Fleet maintenance copilot for mechanics."
    return validate_project_output(
        idea=idea,
        intake={"title": "Fleet Copilot"},
        project_requirements={
            "must_have": [
                "Capture work orders",
                "Track maintenance history",
                "Mechanic dashboard",
                "Parts inventory alerts",
            ],
            "core_features": [
                "Capture work orders",
                "Track maintenance history",
                "Mechanic dashboard",
                "Parts inventory alerts",
            ],
            "project_depth": "Starter Project",
            "project_archetype": "workflow_automation",
            "user_flows": ["Mechanic logs a work order and reviews dashboard metrics."],
        },
        architecture_plan={"files": ["README.md"], "implementation_steps": ["Build app"]},
        generated_artifacts=artifacts,
        model_modes=["live"],
    )


def test_ensure_imports_resolve_repairs_broken_frontend_import():
    idea = "Fleet maintenance copilot for mechanics."
    broken = [
        {
            "name": "src/App.jsx",
            "content": "import Dashboard from './components/Dashboard.jsx';\nexport default function App(){return <Dashboard/>;}\n",
        },
        {"name": "src/main.jsx", "content": "import App from './App.jsx';\n"},
        {"name": "README.md", "content": "# Fleet Copilot\n\nFleet maintenance copilot for mechanics.\n"},
    ]
    repaired = ensure_imports_resolve(
        broken,
        idea=idea,
        title="Fleet Copilot",
        resolved_stack="React, FastAPI",
        required_features=["Capture work orders", "Track maintenance history"],
    )
    assert _imports_resolve(_artifact_map(repaired))


def test_ensure_imports_resolve_ignores_asset_imports():
    files = {
        "src/App.jsx": "import logo from './assets/logo.svg';\nexport default function App(){return null;}\n",
        "src/main.jsx": "import App from './App.jsx';\n",
    }
    assert _imports_resolve(files)


def test_validate_project_output_passes_after_import_repair():
    idea = "Fleet maintenance copilot for mechanics."
    scaffold = build_project_artifacts(
        idea=idea,
        title="Fleet Copilot",
        resolved_stack="React, FastAPI",
        required_features=[
            "Capture work orders",
            "Track maintenance history",
            "Mechanic dashboard",
            "Parts inventory alerts",
        ],
    )
    by_name = {artifact["name"]: artifact for artifact in scaffold}
    by_name["src/App.jsx"] = {
        **by_name["src/App.jsx"],
        "content": "import Missing from './screens/Missing.jsx';\nexport default function App(){return <Missing/>;}\n",
    }
    repaired = ensure_imports_resolve(
        list(by_name.values()),
        idea=idea,
        title="Fleet Copilot",
        resolved_stack="React, FastAPI",
        required_features=[
            "Capture work orders",
            "Track maintenance history",
            "Mechanic dashboard",
            "Parts inventory alerts",
        ],
    )
    validation = _validation_for(repaired)
    imports_check = next(
        check for check in validation["checks"] if check["name"] == "imports_resolve"
    )
    assert imports_check["passed"] is True
