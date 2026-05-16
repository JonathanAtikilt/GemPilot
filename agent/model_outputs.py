from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


ModelOutputMode = Literal["mock", "live", "fallback"]


class TracedModelOutput(BaseModel):
    decision_trace: list[str] = Field(min_length=1)


class MvpScopeOutput(TracedModelOutput):
    target_user: str
    must_have: list[str] = Field(min_length=1)
    demo_boundary: str
    mode: ModelOutputMode


class RepoPlanOutput(TracedModelOutput):
    files: list[str] = Field(min_length=1)
    test_plan: list[str] = Field(min_length=1)
    architecture_notes: list[str] = Field(default_factory=list)
    mode: ModelOutputMode


class GeneratedArtifactOutput(BaseModel):
    name: str
    kind: str
    summary: str
    content: str | None = None


class FileManifestOutput(TracedModelOutput):
    artifacts: list[GeneratedArtifactOutput] = Field(min_length=1)
    mode: ModelOutputMode


class BlockerAnalysisOutput(TracedModelOutput):
    blocker_type: str
    severity: Literal["low", "medium", "high", "critical"]
    recoverable: bool
    root_cause: str
    recovery_plan: list[str] = Field(min_length=1)


class FinalReadmeOutput(TracedModelOutput):
    title: str
    content: str
    setup_steps: list[str] = Field(min_length=1)


class DemoScriptOutput(TracedModelOutput):
    title: str
    content: str
    beats: list[str] = Field(min_length=1)


class PitchOutput(TracedModelOutput):
    title: str
    tagline: str
    content: str
    proof_points: list[str] = Field(min_length=1)
