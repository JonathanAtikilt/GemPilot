#!/usr/bin/env python3
"""Smoke test for the Person 3 tool layer."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from uuid import uuid4

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from tools.blocker_detector import detect_blocker
from tools.build_checker import check_repo_health
from tools.github_tool import check_github_auth, commit_files, create_repo
from tools.repo_writer import append_build_log
from tools.verifier import verify_commit


def require_ok(step: str, result: dict) -> None:
    if result["status"] not in {"success", "mock"}:
        print(f"[failed] {step}: {result}", file=sys.stderr)
        raise SystemExit(1)
    print(f"[ok] {step}: {result['status']}")


def main() -> int:
    os.environ.setdefault("MVPILOT_MOCK_TOOLS", "true")
    os.environ.setdefault("GITHUB_REPO_PREFIX", "mvpilot-generated-")

    short_id = uuid4().hex[:8]
    task_id = f"smoke-{short_id}"
    repo_name = f"mvpilot-generated-smoke-{short_id}"

    auth = check_github_auth()
    require_ok("check_github_auth", auth)

    repo = create_repo(repo_name, "MVPilot Person 3 smoke test repo", "public")
    require_ok("create_repo", repo)

    files = [
        {"path": "README.md", "content": "# Smoke Test MVP\n"},
        {"path": "logs/build_log.md", "content": "# MVPilot Build Log\n\n"},
        {"path": "demo/demo_script.md", "content": "Run the generated MVP and show the audit log.\n"},
        {"path": "requirements.txt", "content": "pydantic\n"},
        {"path": "src/main.py", "content": "print('MVPilot smoke test')\n"},
    ]
    commit = commit_files(repo_name, files, "Add smoke test scaffold")
    require_ok("commit_files", commit)

    log = append_build_log(task_id, repo_name, "Committed smoke test scaffold", {"files": len(files)})
    require_ok("append_build_log", log)

    verified = verify_commit(repo_name, commit["output"]["commit_sha"])
    require_ok("verify_commit", verified)

    health = check_repo_health(repo_name)
    require_ok("check_repo_health", health)

    blocker = detect_blocker(
        [
            {"frontend": "fetch('/api/analyze')"},
            {"backend": "registered route /api/analyze-referral"},
        ]
    )
    require_ok("detect_blocker", blocker)

    repo_url = repo["output"]["repo_url"]
    print(f"repo_url={repo_url}")
    print(f"commit_sha={commit['output']['commit_sha']}")
    print(f"blocker_type={blocker['output'].get('blocker_type')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
