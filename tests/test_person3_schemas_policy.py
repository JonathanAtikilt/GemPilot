import os
import unittest
from unittest.mock import patch

from pydantic import ValidationError

from tools.policy import validate_action, validate_generated_repo_name, validate_github_mutation
from tools.schemas import CommitFilesRequest, FilePayload, MAX_TEXT_FILE_BYTES, ToolResult


class Person3SchemasPolicyTests(unittest.TestCase):
    def test_tool_result_success_shape(self):
        result = ToolResult.success(
            "github.create_repo",
            {"repo_name": "mvpilot-generated-demo"},
        )

        self.assertEqual(result.status, "success")
        self.assertEqual(result.verification_status, "verified")
        self.assertIsNone(result.error)

    def test_file_payload_rejects_path_traversal(self):
        with self.assertRaises(ValidationError):
            FilePayload(path="../secret.txt", content="nope")

    def test_file_payload_normalizes_safe_paths(self):
        payload = FilePayload(path=" logs/build_log.md ", content="entry")

        self.assertEqual(payload.path, "logs/build_log.md")

    def test_file_payload_rejects_binary_content(self):
        with self.assertRaises(ValidationError):
            FilePayload(path="data/blob.bin", content="abc\x00def")

    def test_file_payload_rejects_oversized_content(self):
        with self.assertRaises(ValidationError):
            FilePayload(path="README.md", content="x" * (MAX_TEXT_FILE_BYTES + 1))

    def test_commit_request_rejects_empty_files(self):
        with self.assertRaises(ValidationError):
            CommitFilesRequest(
                repo_name="mvpilot-generated-demo",
                files=[],
                message="Add files",
            )

    def test_policy_rejects_non_generated_repo(self):
        result = validate_generated_repo_name("MVPilot")

        self.assertIsNotNone(result)
        self.assertEqual(result.status, "refused")

    def test_policy_accepts_generated_repo(self):
        result = validate_generated_repo_name("mvpilot-generated-referral-agent")

        self.assertIsNone(result)

    def test_policy_rejects_blocked_action(self):
        result = validate_action("delete_repo")

        self.assertIsNotNone(result)
        self.assertEqual(result.status, "refused")

    def test_mutation_rejects_unsafe_file_path(self):
        result = validate_github_mutation(
            "commit_files",
            "mvpilot-generated-demo",
            [{"path": ".git/config", "content": "bad"}],
        )

        self.assertIsNotNone(result)
        self.assertEqual(result.status, "refused")

    def test_custom_repo_prefix_from_env(self):
        with patch.dict(os.environ, {"GITHUB_REPO_PREFIX": "demo-"}):
            self.assertIsNone(validate_generated_repo_name("demo-referral"))
            self.assertEqual(validate_generated_repo_name("mvpilot-generated-referral").status, "refused")


if __name__ == "__main__":
    unittest.main()
