from agent.rag.types import DocType

# Higher authority = preferred when similarity is otherwise close.
DOC_TYPE_AUTHORITY: dict[DocType, float] = {
    "hackathon_rules": 1.0,
    "required_deliverables": 0.98,
    "ai_provider_docs": 0.95,
    "llm_model_docs": 0.95,
    "allowed_tools_apis": 0.93,
    "repository_format": 0.9,
    "demo_format": 0.9,
    "tech_stack": 0.88,
    "agent_architecture": 0.87,
    "implementation_constraints": 0.86,
    "generated_project_doc": 0.85,
    "build_log": 0.75,
    "scope_warning": 0.7,
    "team_notes": 0.5,
    "unknown": 0.5,
}


def authority_score_for_doc_type(doc_type: DocType) -> float:
    return DOC_TYPE_AUTHORITY.get(doc_type, 0.5)
