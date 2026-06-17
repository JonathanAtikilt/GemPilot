"""Backward-compatible validation imports — delegates to validate_project."""

from __future__ import annotations

from agent.validate_project import validate_project as validate_project_adaptive
from agent.validate_project import validate_project

validate_mvp = validate_project
