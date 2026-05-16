import unittest

from tools.blocker_detector import detect_blocker


class Person3BlockerDetectorTests(unittest.TestCase):
    def test_route_mismatch_detected(self):
        result = detect_blocker(
            [
                {"frontend": "fetch('/api/analyze')"},
                {"backend": "registered route /api/analyze-referral"},
            ]
        )

        self.assertEqual(result["status"], "success")
        self.assertTrue(result["output"]["has_blocker"])
        self.assertEqual(result["output"]["blocker_type"], "route_mismatch")
        self.assertIn("recommended_fix", result["output"])

    def test_missing_dependency_detected(self):
        result = detect_blocker([{"error": "ModuleNotFoundError: No module named 'fastapi'"}])

        self.assertTrue(result["output"]["has_blocker"])
        self.assertEqual(result["output"]["blocker_type"], "missing_dependency")

    def test_missing_env_var_detected(self):
        result = detect_blocker([{"error": "KeyError: GITHUB_TOKEN environment variable"}])

        self.assertTrue(result["output"]["has_blocker"])
        self.assertEqual(result["output"]["blocker_type"], "missing_env_var")

    def test_github_api_failure_detected(self):
        result = detect_blocker([{"tool": "GitHub API HTTP 403 failed: rate limit"}])

        self.assertTrue(result["output"]["has_blocker"])
        self.assertEqual(result["output"]["blocker_type"], "github_api_failure")

    def test_clean_logs_have_no_blocker(self):
        result = detect_blocker([{"message": "Build completed successfully"}])

        self.assertFalse(result["output"]["has_blocker"])

    def test_empty_logs_are_handled(self):
        result = detect_blocker([])

        self.assertEqual(result["status"], "success")
        self.assertFalse(result["output"]["has_blocker"])


if __name__ == "__main__":
    unittest.main()
