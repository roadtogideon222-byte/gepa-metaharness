import tempfile
import unittest
from pathlib import Path

from metaharness import EvaluationResult, FakeBackend, ValidationResult, optimize_harness
from metaharness.reporting import (
    candidate_ledger,
    compare_runs,
    ledger_tsv_columns,
    render_candidate_ledger_table,
    render_tsv,
    summarize_project_runs,
    summarize_run,
    summary_tsv_columns,
)


class ReportingValidator:
    def validate(self, workspace: Path) -> ValidationResult:
        exists = (workspace / "message.txt").exists()
        return ValidationResult(ok=exists, summary="message.txt must exist")


class ReportingEvaluator:
    def evaluate(self, workspace: Path) -> EvaluationResult:
        text = (workspace / "message.txt").read_text(encoding="utf-8")
        score = 1.0 if "better" in text else 0.0
        return EvaluationResult(objective=score, metrics={"score": score}, summary="reporting evaluator")


class ReportingTests(unittest.TestCase):
    def test_summarize_run_and_project(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            baseline = root / "demo_project" / "baseline"
            baseline.mkdir(parents=True)
            (baseline / "message.txt").write_text("baseline\n", encoding="utf-8")
            run_dir = root / "demo_project" / "runs" / "demo"

            optimize_harness(
                baseline=baseline,
                proposer=FakeBackend(
                    mutation=lambda request: {
                        "relative_path": "message.txt",
                        "content": "this is better\n",
                    }
                ),
                validator=ReportingValidator(),
                evaluator=ReportingEvaluator(),
                run_dir=run_dir,
                budget=1,
                objective="Improve reporting benchmark.",
            )

            run_summary = summarize_run(run_dir)
            self.assertEqual("demo", run_summary["run_id"])
            self.assertEqual("demo_project", run_summary["benchmark_name"])
            self.assertEqual(1.0, run_summary["best_objective"])
            self.assertTrue(run_summary["improved"])
            self.assertEqual("c0001", run_summary["first_improving_candidate_id"])
            self.assertIsNotNone(run_summary["time_to_first_improvement_seconds"])
            self.assertIsNotNone(run_summary["started_at"])
            self.assertIsNotNone(run_summary["completed_at"])

            project_summary = summarize_project_runs(root / "demo_project")
            self.assertEqual(1, len(project_summary))
            self.assertEqual("demo", project_summary[0]["run_id"])

            comparison = compare_runs([run_dir])
            self.assertEqual(1, len(comparison))
            self.assertEqual("demo", comparison[0]["run_id"])

            ledger = candidate_ledger(run_dir)
            self.assertEqual(2, len(ledger))
            self.assertEqual("c0000", ledger[0]["candidate_id"])
            self.assertEqual("c0001", ledger[1]["candidate_id"])
            self.assertEqual("keep", ledger[1]["outcome"])
            self.assertEqual(1, ledger[1]["changed_file_count"])
            self.assertIn("message.txt", ledger[1]["changed_files"])

            ledger_tsv = render_tsv(ledger, ledger_tsv_columns())
            self.assertIn("candidate_id", ledger_tsv.splitlines()[0])
            self.assertIn("c0001", ledger_tsv)

            summary_tsv = render_tsv(project_summary, summary_tsv_columns())
            self.assertIn("run_id", summary_tsv.splitlines()[0])
            self.assertIn("demo", summary_tsv)

            ledger_table = render_candidate_ledger_table(ledger)
            self.assertIn("candidate_id", ledger_table)
            self.assertIn("c0001", ledger_table)

    def test_summarize_run_filters_transient_changed_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            baseline = root / "demo_project" / "baseline"
            baseline.mkdir(parents=True)
            (baseline / "message.txt").write_text("baseline\n", encoding="utf-8")
            run_dir = root / "demo_project" / "runs" / "demo"

            optimize_harness(
                baseline=baseline,
                proposer=FakeBackend(
                    mutation=lambda request: {
                        "files": [
                            {"relative_path": "message.txt", "content": "this is better\n"},
                            {"relative_path": ".venv/bin/python", "content": "shim\n"},
                            {"relative_path": "__pycache__/module.pyc", "content": "compiled\n"},
                        ]
                    }
                ),
                validator=ReportingValidator(),
                evaluator=ReportingEvaluator(),
                run_dir=run_dir,
                budget=1,
                objective="Improve reporting benchmark.",
            )

            run_summary = summarize_run(run_dir)
            self.assertEqual(["message.txt"], run_summary["best_changed_files"])
            self.assertEqual(1, run_summary["best_changed_file_count"])
            self.assertEqual(2, run_summary["best_transient_files_omitted_count"])


if __name__ == "__main__":
    unittest.main()
