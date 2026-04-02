import tempfile
import unittest
from pathlib import Path

from metaharness.bootstrap import collect_environment_bootstrap


class BootstrapTests(unittest.TestCase):
    def test_collect_environment_bootstrap_captures_workspace_summary(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir)
            (workspace / "pyproject.toml").write_text("[project]\nname='demo'\n", encoding="utf-8")
            (workspace / "src").mkdir()
            (workspace / "README.md").write_text("# Demo\n", encoding="utf-8")

            bootstrap = collect_environment_bootstrap(workspace)

            self.assertEqual(str(workspace.resolve()), bootstrap.snapshot["working_directory"])
            self.assertIn("pyproject.toml", bootstrap.snapshot["package_files"])
            self.assertIn("Environment Bootstrap", bootstrap.summary_text)
            self.assertIn("Top-Level Workspace Entries", bootstrap.summary_text)
            entry_names = {item["name"] for item in bootstrap.snapshot["top_level_entries"]}
            self.assertIn("src", entry_names)
            self.assertIn("README.md", entry_names)


if __name__ == "__main__":
    unittest.main()
