from pathlib import Path
from typing import Sequence

from .core.engine import MetaHarnessEngine
from .core.protocols import EvaluatorProtocol, ValidatorProtocol
from .models import OptimizeResult
from .proposer.base import ProposerBackend


class NoOpValidator:
    def validate(self, workspace: Path):  # pragma: no cover - trivial
        from .models import ValidationResult

        return ValidationResult(ok=True, summary="No validator configured.")


def optimize_harness(
    baseline: str | Path,
    proposer: ProposerBackend,
    evaluator: EvaluatorProtocol,
    run_dir: str | Path,
    budget: int,
    objective: str,
    validator: ValidatorProtocol | None = None,
    constraints: Sequence[str] | None = None,
    allowed_write_paths: Sequence[str] | None = None,
) -> OptimizeResult:
    engine = MetaHarnessEngine(
        baseline=Path(baseline),
        proposer=proposer,
        evaluator=evaluator,
        validator=validator or NoOpValidator(),
        run_dir=Path(run_dir),
        budget=budget,
        objective=objective,
        constraints=list(constraints or []),
        allowed_write_paths=list(allowed_write_paths or []),
    )
    return engine.run()
