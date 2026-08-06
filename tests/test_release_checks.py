import unittest
from pathlib import Path

from tools.release_checks import validate_release_metadata


ROOT = Path(__file__).resolve().parent.parent


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

    def test_windows_powershell_launcher_loads_release_script_as_utf8(self):
        content = (ROOT / "run-release.ps1").read_text(encoding="utf-8")
        self.assertIn("ReadAllText", content)
        self.assertIn("UTF8Encoding", content)
        self.assertIn("-Version $Version", content)


if __name__ == "__main__":
    unittest.main()
