from agent.rag.url_utils import collect_source_urls
from agent.schemas import RunAgentRequest


def test_collect_source_urls_dedupes_and_normalizes() -> None:
    urls = collect_source_urls(
        primary_rules_url="https://Example.com/rules/",
        additional_urls=[
            "https://example.com/rules",
            "https://docs.nvidia.com/nemotron/",
        ],
    )

    assert "https://example.com/rules" in urls
    assert "https://docs.nvidia.com/nemotron" in urls
    assert len(urls) == 2


def test_run_agent_request_accepts_source_urls_json_field() -> None:
    request = RunAgentRequest.model_validate(
        {
            "idea": "Build a planner",
            "repo_visibility": "public",
            "source_urls": ["https://rules.example.com/hackathon"],
        }
    )

    assert request.source_urls == ["https://rules.example.com/hackathon"]


def test_run_agent_request_merges_frontend_url_fields() -> None:
    request = RunAgentRequest.model_validate(
        {
            "idea": "Build a planner",
            "repo_visibility": "public",
            "rules_url": "https://hackathon.example.com/rules",
            "additional_urls": ["https://docs.nvidia.com/models/"],
        }
    )

    assert request.source_urls == [
        "https://hackathon.example.com/rules",
        "https://docs.nvidia.com/models",
    ]
