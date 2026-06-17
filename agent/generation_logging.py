"""Structured logging for adaptive project generation."""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger("gempilot.generation")


def log_classification(classification: dict[str, Any], *, idea: str) -> None:
    logger.info(
        "project_classification idea=%r project_type=%s complexity=%s "
        "frontend=%s backend=%s database=%s realtime=%s ai=%s deployment=%s",
        idea[:120],
        classification.get("project_type"),
        classification.get("complexity"),
        classification.get("frontend_needed"),
        classification.get("backend_needed"),
        classification.get("database_needed"),
        classification.get("realtime_needed"),
        classification.get("ai_needed"),
        classification.get("deployment_strategy"),
    )


def log_architecture(plan: dict[str, Any], *, project_type: str) -> None:
    tree = plan.get("file_tree") or plan.get("files") or []
    logger.info(
        "architecture_chosen project_type=%s file_count=%d entrypoints=%s stages=%s",
        project_type,
        len(tree),
        plan.get("entrypoints") or [],
        plan.get("implementation_stages") or [],
    )


def log_features(*, required: list[str], excluded: list[str]) -> None:
    logger.info(
        "features_generated required=%d excluded=%d required_list=%s",
        len(required),
        len(excluded),
        required[:8],
    )


def log_repairs(*, repairs: list[str]) -> None:
    if repairs:
        logger.info("import_repairs_performed count=%d details=%s", len(repairs), repairs[:10])


def log_validation(*, passed: bool, project_type: str, failed_checks: list[str]) -> None:
    if passed:
        logger.info("validation_passed project_type=%s", project_type)
    else:
        logger.warning(
            "validation_failed project_type=%s failed=%s",
            project_type,
            failed_checks[:6],
        )
