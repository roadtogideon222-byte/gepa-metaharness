import os
import subprocess
import tempfile
import unittest
import json
import shutil
from pathlib import Path


class CliTests(unittest.TestCase):
    def test_scaffold_and_inspect_flow(self) -> None:
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
            self.assertIn("profile=standard", scaffold.stdout)
            self.assertTrue((project_dir / "metaharness.json").exists())
            self.assertTrue((project_dir / "tasks.json").exists())
            self.assertTrue((project_dir / "baseline" / "AGENTS.md").exists())

            run = subprocess.run(
                [
                    "python",
                    "-m",
                    "metaharness.cli",
                    "run",
                    str(project_dir),
                    "--backend",
                    "fake",
                    "--budget",
                    "1",
                    "--run-name",
                    "smoke",
                ],
                cwd=repo_root,
                env=env,
                text=True,
                capture_output=True,
            )
            self.assertEqual(0, run.returncode, run.stderr)
            self.assertIn("best_candidate_id=c0001", run.stdout)
            run_dir = project_dir / "runs" / "smoke"
            proposal_result = json.loads(
                (run_dir / "candidates" / "c0001" / "proposal" / "result.json").read_text(encoding="utf-8")
            )
            self.assertEqual(
                {
                    "AGENTS.md",
                    "GEMINI.md",
                    "scripts/bootstrap.sh",
                    "scripts/validate.sh",
                    "scripts/test.sh",
                },
                set(proposal_result["changed_files"]),
            )
            self.assertTrue((run_dir / "candidates" / "c0001" / "proposal" / "workspace.diff").exists())

            inspect = subprocess.run(
                ["python", "-m", "metaharness.cli", "inspect", str(run_dir)],
                cwd=repo_root,
                env=env,
                text=True,
                capture_output=True,
            )
            self.assertEqual(0, inspect.returncode, inspect.stderr)
            self.assertIn("best_candidate_id=c0001", inspect.stdout)

            summarize = subprocess.run(
                ["python", "-m", "metaharness.cli", "summarize", str(project_dir)],
                cwd=repo_root,
                env=env,
                text=True,
                capture_output=True,
            )
            self.assertEqual(0, summarize.returncode, summarize.stderr)
            self.assertIn("run_id", summarize.stdout)
            self.assertIn("smoke", summarize.stdout)

            compare = subprocess.run(
                ["python", "-m", "metaharness.cli", "compare", str(run_dir)],
                cwd=repo_root,
                env=env,
                text=True,
                capture_output=True,
            )
            self.assertEqual(0, compare.returncode, compare.stderr)
            self.assertIn("best_candidate_id=c0001", compare.stdout)
            self.assertIn("backend=fake", compare.stdout)

    def test_scaffold_local_oss_smoke_profile(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir) / "coding-tool-project"
            env = {**os.environ, "PYTHONPATH": "src"}

            scaffold = subprocess.run(
                [
                    "python",
                    "-m",
                    "metaharness.cli",
                    "scaffold",
                    "coding-tool",
                    str(project_dir),
                    "--profile",
                    "local-oss-smoke",
                ],
                cwd=repo_root,
                env=env,
                text=True,
                capture_output=True,
            )
            self.assertEqual(0, scaffold.returncode, scaffold.stderr)
            self.assertIn("profile=local-oss-smoke", scaffold.stdout)

            config = json.loads((project_dir / "metaharness.json").read_text(encoding="utf-8"))
            self.assertTrue(config["backends"]["codex"]["use_oss"])
            self.assertEqual("ollama", config["backends"]["codex"]["local_provider"])
            self.assertEqual("gpt-oss:20b", config["backends"]["codex"]["model"])
            self.assertEqual(120, config["backends"]["codex"]["proposal_timeout_seconds"])
            self.assertTrue((project_dir / "baseline" / "scripts" / "validate.sh").exists())
            self.assertFalse((project_dir / "baseline" / "scripts" / "bootstrap.sh").exists())
            self.assertFalse((project_dir / "baseline" / "scripts" / "test.sh").exists())

    def test_scaffold_local_oss_medium_profile(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir) / "coding-tool-project"
            env = {**os.environ, "PYTHONPATH": "src"}

            scaffold = subprocess.run(
                [
                    "python",
                    "-m",
                    "metaharness.cli",
                    "scaffold",
                    "coding-tool",
                    str(project_dir),
                    "--profile",
                    "local-oss-medium",
                ],
                cwd=repo_root,
                env=env,
                text=True,
                capture_output=True,
            )
            self.assertEqual(0, scaffold.returncode, scaffold.stderr)
            self.assertIn("profile=local-oss-medium", scaffold.stdout)

            config = json.loads((project_dir / "metaharness.json").read_text(encoding="utf-8"))
            self.assertTrue(config["backends"]["codex"]["use_oss"])
            self.assertEqual("ollama", config["backends"]["codex"]["local_provider"])
            self.assertEqual("gpt-oss:20b", config["backends"]["codex"]["model"])
            self.assertEqual(180, config["backends"]["codex"]["proposal_timeout_seconds"])
            self.assertTrue((project_dir / "baseline" / "scripts" / "validate.sh").exists())
            self.assertTrue((project_dir / "baseline" / "scripts" / "bootstrap.sh").exists())
            self.assertTrue((project_dir / "baseline" / "scripts" / "test.sh").exists())

            run = subprocess.run(
                [
                    "python",
                    "-m",
                    "metaharness.cli",
                    "run",
                    str(project_dir),
                    "--backend",
                    "fake",
                    "--budget",
                    "1",
                    "--run-name",
                    "medium-fake",
                ],
                cwd=repo_root,
                env=env,
                text=True,
                capture_output=True,
            )
            self.assertEqual(0, run.returncode, run.stderr)
            self.assertIn("best_candidate_id=c0001", run.stdout)

    def test_codex_smoke_probe_only(self) -> None:
        if shutil.which("codex") is None:
            self.skipTest("codex CLI not installed")

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
                    "--probe-only",
                ],
                cwd=repo_root,
                env=env,
                text=True,
                capture_output=True,
            )
            self.assertEqual(0, smoke.returncode, smoke.stderr)
            self.assertIn("codex_version=", smoke.stdout)


if __name__ == "__main__":
    unittest.main()
