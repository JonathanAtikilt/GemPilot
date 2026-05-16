import unittest
from unittest.mock import patch

from tools.tool_logger import (
    log_audit_event,
    log_generated_artifact,
    log_tool_call,
    redact_secrets,
)


class Person3ToolLoggerTests(unittest.TestCase):
    def test_redact_secrets_nested(self):
        value = {
            "GITHUB_TOKEN": "secret",
            "safe": "value",
            "nested": {"api_key": "secret-key"},
            "items": [{"password": "pw"}],
        }

        redacted = redact_secrets(value)

        self.assertEqual(redacted["GITHUB_TOKEN"], "[REDACTED]")
        self.assertEqual(redacted["safe"], "value")
        self.assertEqual(redacted["nested"]["api_key"], "[REDACTED]")
        self.assertEqual(redacted["items"][0]["password"], "[REDACTED]")

    def test_log_tool_call_degrades_without_supabase(self):
        with patch.dict("os.environ", {}, clear=True):
            result = log_tool_call(
                "task-1",
                "github.create_repo",
                {"GITHUB_TOKEN": "secret"},
                {"status": "success", "verification_status": "verified", "output": {"ok": True}},
            )

        self.assertEqual(result["status"], "success")
        self.assertFalse(result["output"]["logged"])
        self.assertEqual(result["output"]["row"]["input_json"]["GITHUB_TOKEN"], "[REDACTED]")
        self.assertEqual(result["output"]["row"]["verification_status"], "verified")

    def test_log_audit_event_degrades_without_supabase(self):
        with patch.dict("os.environ", {}, clear=True):
            result = log_audit_event(
                "task-1",
                "created_repo",
                "Created generated repository.",
                {"GITHUB_TOKEN": "secret", "repo_name": "mvpilot-generated-demo"},
            )

        self.assertEqual(result["status"], "success")
        self.assertFalse(result["output"]["logged"])
        row = result["output"]["row"]
        self.assertEqual(row["task_id"], "task-1")
        self.assertEqual(row["step"], "created_repo")
        self.assertEqual(row["data"]["GITHUB_TOKEN"], "[REDACTED]")
        self.assertEqual(row["data"]["repo_name"], "mvpilot-generated-demo")

    def test_log_generated_artifact_degrades_without_supabase(self):
        with patch.dict("os.environ", {}, clear=True):
            result = log_generated_artifact(
                "task-1",
                "demo_script",
                "demo/demo_script.md",
                "Run the demo.",
                "abc123",
            )

        self.assertEqual(result["status"], "success")
        self.assertFalse(result["output"]["logged"])
        row = result["output"]["row"]
        self.assertEqual(row["artifact_type"], "demo_script")
        self.assertEqual(row["path"], "demo/demo_script.md")
        self.assertEqual(row["commit_sha"], "abc123")


if __name__ == "__main__":
    unittest.main()
