import os
import subprocess
import tempfile
import unittest
from pathlib import Path


@unittest.skipUnless(
    os.environ.get("METAHARNESS_RUN_LIVE_CODEX") == "1",
    "set METAHARNESS_RUN_LIVE_CODEX=1 to run live Codex smoke test",
)
class LiveCodexSmokeTests(unittest.TestCase):
    def test_live_codex_smoke_run(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir) / "coding-tool-project"
            env = {**os.environ, "PYTHONPATH": "src"}

            scaffold = subprocess.run(
                ["python", "-m", "metaharness.cli", "scaffold", "coding-tool", str(project_dir)],
                cwd=repo_root,
                env=env,
                text=True,
                capture_output=True,
            )
            self.assertEqual(0, scaffold.returncode, scaffold.stderr)

            smoke = subprocess.run(
                [
                    "python",
                    "-m",
                    "metaharness.cli",
                    "smoke",
                    "codex",
                    str(project_dir),
                    "--budget",
                    "1",
                    "--run-name",
                    "live-smoke",
                ],
                cwd=repo_root,
                env=env,
                text=True,
                capture_output=True,
            )
            self.assertEqual(0, smoke.returncode, smoke.stderr)
            self.assertIn("run_dir=", smoke.stdout)
            self.assertTrue((project_dir / "runs" / "live-smoke").exists())


if __name__ == "__main__":
    unittest.main()
