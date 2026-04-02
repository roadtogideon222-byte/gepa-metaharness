import json
import tempfile
import unittest
from pathlib import Path

from metaharness import EvaluationResult, ValidationResult, optimize_harness
from metaharness.proposer.pi_cli import PiCliBackend


class TimeoutValidator:
    def validate(self, workspace: Path) -> ValidationResult:
        exists = (workspace / "message.txt").exists()
        return ValidationResult(ok=exists, summary="message.txt must exist")


class TimeoutEvaluator:
    def evaluate(self, workspace: Path) -> EvaluationResult:
        return EvaluationResult(
            objective=0.0,
            metrics={"score": 0.0},
            summary="No-op evaluator.",
        )


class PiTimeoutTests(unittest.TestCase):
    def test_pi_backend_timeout_marks_candidate_failed(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            baseline = root / "baseline"
            baseline.mkdir()
            (baseline / "message.txt").write_text("baseline\n", encoding="utf-8")

            fake_pi = root / "fake-pi"
            fake_pi.write_text(
                "#!/usr/bin/env bash\n"
                "sleep 2\n",
                encoding="utf-8",
            )
            fake_pi.chmod(0o755)

            run_dir = root / "runs" / "timeout"
            result = optimize_harness(
                baseline=baseline,
                proposer=PiCliBackend(pi_binary=str(fake_pi), timeout_seconds=0.1),
                validator=TimeoutValidator(),
                evaluator=TimeoutEvaluator(),
                run_dir=run_dir,
                budget=1,
                objective="Exercise timeout handling.",
            )

            self.assertEqual("c0000", result.best_candidate_id)
            proposal = json.loads(
                (run_dir / "candidates" / "c0001" / "proposal" / "result.json").read_text(encoding="utf-8")
            )
            manifest = json.loads(
                (run_dir / "candidates" / "c0001" / "manifest.json").read_text(encoding="utf-8")
            )
            self.assertFalse(proposal["applied"])
            self.assertTrue(proposal["metadata"]["timed_out"])
            self.assertEqual(124, proposal["metadata"]["returncode"])
            self.assertIn("timed out", proposal["summary"])
            self.assertEqual("timeout", manifest["outcome"])


if __name__ == "__main__":
    unittest.main()
