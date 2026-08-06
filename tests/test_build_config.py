import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
VERSION_RESOURCE = "tools/generated/commmonit-version.txt"


class BuildConfigTests(unittest.TestCase):
    def test_both_specs_reference_generated_version_resource(self):
        for name in ("CommMonit.spec", "CommMonit-folder.spec"):
            content = (ROOT / name).read_text(encoding="utf-8")
            self.assertIn(f'version="{VERSION_RESOURCE}"', content)

    def test_build_generates_version_resource_before_tests(self):
        content = (ROOT / "build.ps1").read_text(encoding="utf-8")
        generator = content.index("tools\\make_version_info.py")
        tests = content.index('"unittest", "discover"')
        self.assertLess(generator, tests)


if __name__ == "__main__":
    unittest.main()
