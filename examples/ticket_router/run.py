from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path

from metaharness import (
    CodexExecBackend,
    EvaluationResult,
    FakeBackend,
    ValidationResult,
    optimize_harness,
)


EXAMPLE_DIR = Path(__file__).resolve().parent
DATASET_PATH = EXAMPLE_DIR / "dataset.json"
BASELINE_DIR = EXAMPLE_DIR / "baseline"
RUNS_DIR = EXAMPLE_DIR / "runs"


def load_dataset() -> list[dict[str, str]]:
    return json.loads(DATASET_PATH.read_text(encoding="utf-8"))


def load_router_module(workspace: Path):
    router_path = workspace / "router.py"
    spec = importlib.util.spec_from_file_location("candidate_router", router_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load router module from {router_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TicketRouterValidator:
    def validate(self, workspace: Path) -> ValidationResult:
        router_path = workspace / "router.py"
        if not router_path.exists():
            return ValidationResult(ok=False, summary="router.py is missing")

        try:
            source = router_path.read_text(encoding="utf-8")
            compile(source, str(router_path), "exec")
            module = load_router_module(workspace)
            route_ticket = getattr(module, "route_ticket", None)
            if route_ticket is None or not callable(route_ticket):
                return ValidationResult(ok=False, summary="route_ticket(text) is missing")
            sample = route_ticket("Please refund the duplicate charge on my invoice.")
            if not isinstance(sample, str):
                return ValidationResult(ok=False, summary="route_ticket must return a string label")
        except Exception as exc:  # noqa: BLE001
            return ValidationResult(ok=False, summary=f"validator error: {exc}")

        return ValidationResult(ok=True, summary="router.py compiled and exposed route_ticket")


class TicketRouterEvaluator:
    def __init__(self, dataset: list[dict[str, str]]) -> None:
        self.dataset = dataset

    def evaluate(self, workspace: Path) -> EvaluationResult:
        module = load_router_module(workspace)
        route_ticket = getattr(module, "route_ticket")

        correct = 0
        mistakes: list[dict[str, str]] = []
        for row in self.dataset:
            prediction = str(route_ticket(row["text"]))
            if prediction == row["label"]:
                correct += 1
            else:
                mistakes.append(
                    {
                        "text": row["text"],
                        "expected": row["label"],
                        "predicted": prediction,
                    }
                )

        total = len(self.dataset)
        accuracy = correct / total if total else 0.0
        summary = f"Accuracy {correct}/{total} = {accuracy:.3f}"
        if mistakes:
            rendered = []
            for mistake in mistakes[:5]:
                rendered.append(
                    f"expected={mistake['expected']} predicted={mistake['predicted']} text={mistake['text']}"
                )
            summary += "\nMistakes:\n" + "\n".join(rendered)

        return EvaluationResult(
            objective=accuracy,
            metrics={"accuracy": accuracy, "correct": float(correct), "total": float(total)},
            summary=summary,
            metadata={"mistakes": mistakes},
        )


def make_backend(name: str):
    if name == "codex":
        return CodexExecBackend()
    if name == "fake":
        return FakeBackend(
            mutation=lambda request: {
                "relative_path": "router.py",
                "content": (
                    "from __future__ import annotations\n\n"
                    'LABELS = {"billing", "bug", "feature", "security"}\n\n'
                    "def route_ticket(text: str) -> str:\n"
                    "    lower = text.lower()\n"
                    '    if any(token in lower for token in ["shared link", "api key", "leak", "access another user", "browser console"]):\n'
                    '        return "security"\n'
                    '    if any(token in lower for token in ["invoice", "refund", "charged", "billing", "team plan"]):\n'
                    '        return "billing"\n'
                    '    if any(token in lower for token in ["crash", "spins forever", "never downloads", "export button"]):\n'
                    '        return "bug"\n'
                    '    if any(token in lower for token in ["sso", "saml", "scheduled email reports", "would help", "please add"]):\n'
                    '        return "feature"\n'
                    '    return "bug"\n\n'
                    "def validate_label(label: str) -> str:\n"
                    "    if label not in LABELS:\n"
                    '        raise ValueError(f"unexpected label: {label}")\n'
                    "    return label\n"
                ),
                "summary": f"Updated router heuristics for {request.candidate_id}.",
                "final_text": "Improved ticket routing heuristics.",
            }
        )
    raise ValueError(f"unknown backend: {name}")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--backend", choices=["fake", "codex"], default="fake")
    parser.add_argument("--budget", type=int, default=1)
    parser.add_argument("--run-name", default=None)
    args = parser.parse_args(argv)

    dataset = load_dataset()
    run_name = args.run_name or f"{args.backend}-run"
    run_dir = RUNS_DIR / run_name

    result = optimize_harness(
        baseline=BASELINE_DIR,
        proposer=make_backend(args.backend),
        evaluator=TicketRouterEvaluator(dataset),
        validator=TicketRouterValidator(),
        run_dir=run_dir,
        budget=args.budget,
        objective="Improve support ticket routing accuracy across billing, bug, feature, and security tickets.",
        constraints=[
            "Keep the harness deterministic.",
            "Do not call external APIs.",
            "Return only one of: billing, bug, feature, security.",
        ],
    )

    print(f"run_dir={result.run_dir}")
    print(f"best_candidate_id={result.best_candidate_id}")
    print(f"best_objective={result.best_objective:.3f}")
    print(f"best_workspace_dir={result.best_workspace_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
