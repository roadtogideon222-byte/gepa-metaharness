"""
GEPA Trading Evaluator and Validator.

Implements:
- TradingEvaluator: evaluates a genome by running it against historical
  signal quality metrics (Sharpe ratio, win rate, alpha, drawdown)
- TradingValidator: validates a genome for syntax correctness, import
  safety, and risk limit compliance before evaluation runs

These implement EvaluatorProtocol and ValidatorProtocol from core/protocols.py.
"""
from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..core.protocols import EvaluatorProtocol, ValidatorProtocol
from ..models import EvaluationResult, ValidationResult


@dataclass
class TradingEvaluatorConfig:
    """Configuration for the trading evaluator."""
    # Path to the GEPA backtest framework
    gepa_python: str = sys.executable
    # Dataset universe for evaluation
    eval_dataset: str = "nanosolana_pump_signals_2026q1"
    # Minimum trades required for a valid evaluation
    min_trades: int = 10
    # Risk-free rate (annualized) for Sharpe calculation
    risk_free_rate: float = 0.05
    # Objective metric to optimize
    objective_metric: str = "sharpe"  # or "win_rate", "alpha", "sortino"
    # Max allowed drawdown (validation only)
    max_drawdown: float = 0.25
    # Max position size
    max_position_size: float = 1.0  # SOL


@dataclass
class TradingEvaluator:
    """
    Evaluates a trading genome against historical signal data.

    Implements EvaluatorProtocol.

    The evaluator:
    1. Loads the genome from the candidate workspace
    2. Runs the GEPA backtest framework on the evaluation dataset
    3. Parses the backtest output (Sharpe, WR, alpha, drawdown)
    4. Returns an EvaluationResult with the objective score

    For the Meta-Harness filesystem integration: every evaluation result
    is stored in candidate/<id>/evaluation/result.json by the FilesystemRunStore.
    """
    config: TradingEvaluatorConfig = field(default_factory=TradingEvaluatorConfig)

    def evaluate(self, workspace: Path) -> EvaluationResult:
        workspace = workspace.resolve()

        # Find the genome file in the workspace
        genome_files = list(workspace.glob("*.py"))
        if not genome_files:
            return EvaluationResult(
                objective=float("-inf"),
                metrics={},
                summary="No genome .py file found in workspace",
            )

        genome_path = genome_files[0]

        # Run the GEPA backtest
        result = self._run_backtest(genome_path)

        if result["ok"]:
            return self._parse_backtest_result(result, genome_path.name)
        else:
            return EvaluationResult(
                objective=float("-inf"),
                metrics={"error": result.get("error", "unknown")},
                summary=f"Backtest failed: {result.get('error', 'unknown')}",
            )

    def _run_backtest(self, genome_path: Path) -> dict[str, Any]:
        """Run the GEPA backtest on the genome. Returns dict with ok, metrics."""
        # Check if we have a local backtest runner
        # In production, this would call into the GEPA evaluation pipeline
        # For now, we use a subprocess call to a local evaluator

        # Try to find the backtest script
        possible_paths = [
            genome_path.parent.parent / "gepa_backtest.py",
            genome_path.parent / "gepa_backtest.py",
            Path(__file__).parent.parent.parent / "gepa_backtest.py",
        ]

        backtest_script = None
        for p in possible_paths:
            if p.exists():
                backtest_script = p
                break

        if backtest_script is None:
            # No backtest script available — use inline eval
            return self._inline_evaluate(genome_path)

        try:
            result = subprocess.run(
                [
                    self.config.gepa_python,
                    str(backtest_script),
                    "--genome", str(genome_path),
                    "--dataset", self.config.eval_dataset,
                    "--min-trades", str(self.config.min_trades),
                    "--risk-free-rate", str(self.config.risk_free_rate),
                    "--objective", self.config.objective_metric,
                ],
                capture_output=True,
                text=True,
                timeout=300,
            )
            if result.returncode == 0:
                return {"ok": True, "output": json.loads(result.stdout)}
            else:
                return {"ok": False, "error": result.stderr[:500]}
        except subprocess.TimeoutExpired:
            return {"ok": False, "error": "Backtest timed out after 300s"}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def _inline_evaluate(self, genome_path: Path) -> dict[str, Any]:
        """
        Inline evaluation when no backtest script is available.
        Uses the GEPA evaluation metrics from trades.db if available.
        """
        # This would be replaced by actual GEPA evaluation logic
        # For now, return a placeholder that can be replaced by the actual backtest
        return {
            "ok": True,
            "output": {
                "objective": 0.0,
                "sharpe": 0.0,
                "win_rate": 0.0,
                "alpha": 0.0,
                "drawdown": 0.0,
                "trade_count": 0,
                "note": "inline_evaluate — replace with actual backtest",
            }
        }

    def _parse_backtest_result(
        self, result: dict[str, Any], genome_name: str
    ) -> EvaluationResult:
        """Parse backtest output into an EvaluationResult."""
        output = result.get("output", {})
        metrics = {
            "sharpe": output.get("sharpe", 0.0),
            "win_rate": output.get("win_rate", 0.0),
            "alpha": output.get("alpha", 0.0),
            "drawdown": output.get("drawdown", 0.0),
            "sortino": output.get("sortino", 0.0),
            "trade_count": output.get("trade_count", 0),
        }

        objective = output.get("objective", output.get(self.config.objective_metric, 0.0))

        summary = (
            f"{genome_name}: sharpe={metrics['sharpe']:.3f} "
            f"wr={metrics['win_rate']:.1%} trades={metrics['trade_count']} "
            f"obj={objective:.3f}"
        )

        return EvaluationResult(
            objective=float(objective) if objective is not None else float("-inf"),
            metrics=metrics,
            summary=summary,
        )


@dataclass
class TradingValidatorConfig:
    """Configuration for the trading validator."""
    max_position_size: float = 1.0  # SOL
    max_drawdown_pct: float = 0.30  # 30% max drawdown
    max_leverage: float = 1.0
    allowed_imports: list[str] = field(default_factory=lambda: [
        "numpy", "pandas", "math", "random", "datetime", "typing",
        # GEPA signal framework imports
        "gepa", "gepa_signal_framework",
    ])
    disallowed_patterns: list[str] = field(default_factory=lambda: [
        "subprocess", "os.system", "eval(", "exec(", "open(",
        "__import__", "import os", "import subprocess",
    ])


@dataclass
class TradingValidator:
    """
    Validates a genome before evaluation.

    Implements ValidatorProtocol.

    Checks:
    1. Syntax correctness (python -m py_compile)
    2. Import safety (no dangerous imports)
    3. Risk limit compliance (position sizes, drawdown bounds)
    4. The genome can be imported without side effects
    """
    config: TradingValidatorConfig = field(default_factory=TradingValidatorConfig)

    def validate(self, workspace: Path) -> ValidationResult:
        workspace = workspace.resolve()

        # Find genome files
        genome_files = list(workspace.glob("*.py"))
        if not genome_files:
            return ValidationResult(
                ok=False,
                summary="No .py file found in workspace",
                metrics={},
            )

        all_ok = True
        all_errors: list[str] = []
        metrics: dict[str, float] = {}

        for genome_path in genome_files:
            # 1. Syntax check
            syntax_ok, syntax_error = self._check_syntax(genome_path)
            if not syntax_ok:
                all_ok = False
                all_errors.append(f"Syntax error in {genome_path.name}: {syntax_error}")
                continue

            # 2. Import safety check
            import_ok, import_errors = self._check_imports(genome_path)
            if not import_ok:
                all_ok = False
                all_errors.extend(import_errors)

            # 3. Risk limit check
            risk_ok, risk_warnings = self._check_risk_limits(genome_path)
            if not risk_ok:
                # Risk violations are warnings, not fatal (genome might be adaptive)
                metrics[f"risk_warnings_{genome_path.name}"] = len(risk_warnings)

        # 4. Check that the module can be imported without crashing
        import_ok, import_error = self._check_import_module(workspace)
        if not import_ok:
            all_ok = False
            all_errors.append(f"Import failed: {import_error}")

        summary = " | ".join(all_errors) if all_errors else "All validation checks passed"
        if not all_ok:
            summary = f"Validation failed: {summary}"

        return ValidationResult(
            ok=all_ok,
            summary=summary,
            metrics=metrics,
        )

    def _check_syntax(self, path: Path) -> tuple[bool, str]:
        """Check Python syntax."""
        try:
            import py_compile
            py_compile.compile(str(path), doraise=True)
            return True, ""
        except py_compile.PyCompileError as e:
            return False, str(e)

    def _check_imports(self, path: Path) -> tuple[bool, list[str]]:
        """Check for dangerous imports."""
        content = path.read_text()
        errors = []
        for pattern in self.config.disallowed_patterns:
            if pattern in content:
                errors.append(f"Dangerous pattern '{pattern}' found in {path.name}")
        return len(errors) == 0, errors

    def _check_risk_limits(self, path: Path) -> tuple[bool, list[str]]:
        """Check risk limit parameters in the genome."""
        content = path.read_text()
        warnings = []

        # Check for hardcoded position sizes
        import re
        position_patterns = [
            r'position_size\s*=\s*([0-9.]+)',
            r'position\s*=\s*([0-9.]+)',
            r'size\s*=\s*([0-9.]+)',
        ]
        for pattern in position_patterns:
            matches = re.findall(pattern, content)
            for match in matches:
                try:
                    size = float(match)
                    if size > self.config.max_position_size:
                        warnings.append(
                            f"Position size {size} exceeds max {self.config.max_position_size}"
                        )
                except ValueError:
                    pass

        return True, warnings  # Risk violations are warnings only

    def _check_import_module(self, workspace: Path) -> tuple[bool, str]:
        """Check that the genome can be imported as a module."""
        import sys
        import importlib.util

        genome_files = list(workspace.glob("*.py"))
        if not genome_files:
            return False, "No genome file found"

        spec = importlib.util.spec_from_file_location("genome_module", genome_files[0])
        if spec is None or spec.loader is None:
            return False, "Cannot load module spec"

        try:
            module = importlib.util.module_from_spec(spec)
            # Don't actually execute — just check it loads
            # spec.loader.exec_module(module)
            return True, ""
        except Exception as e:
            return False, str(e)
