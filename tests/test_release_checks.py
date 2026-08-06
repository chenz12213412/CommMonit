import unittest

from tools.release_checks import validate_release_metadata


class ReleaseChecksTests(unittest.TestCase):
    def test_accepts_matching_version_and_changelog(self):
        validate_release_metadata("1.0.0", "## [1.0.0] - 2026-08-06")

    def test_rejects_invalid_semantic_version(self):
        with self.assertRaisesRegex(ValueError, "语义化版本"):
            validate_release_metadata("1.0", "## [1.0] - 2026-08-06")

    def test_rejects_version_different_from_application(self):
        with self.assertRaisesRegex(ValueError, "应用版本"):
            validate_release_metadata("1.0.1", "## [1.0.1] - 2026-08-06")

    def test_rejects_missing_changelog_entry(self):
        with self.assertRaisesRegex(ValueError, "更新日志"):
            validate_release_metadata("1.0.0", "# 更新日志")


if __name__ == "__main__":
    unittest.main()
