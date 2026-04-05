"""
GEPA Genome Project configuration.

Defines the structure of a GEPA genome optimization project and
loads/resolves project configurations.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class GEPAProjectConfig:
    """
    Configuration for a GEPA genome optimization project.

    Loaded from <project_dir>/gepaharness.json (or .json5).
    """
    project_name: str = "gepa-genome-project"
    project_version: str = "0.1.0"

    # Baseline genome path
    baseline_genome: Path | None = None

    # Evaluation dataset
    eval_dataset: str = "nanosolana_pump_signals_2026q1"

    # Optimization budget
    budget: int = 10

    # Proposer config
    proposer_model: str = "claude-sonnet-4-7-2025"
    proposer_provider: str = "anthropic"
    proposer_temperature: float = 0.7
    proposer_max_tokens: int = 4096

    # Objective
    objective_metric: str = "sharpe"  # sharpe | win_rate | alpha | sortino

    # Constraints
    max_drawdown: float = 0.25
    max_position_size: float = 1.0  # SOL
    min_win_rate: float = 0.50
    min_trades_per_eval: int = 10

    # Allowed genome mutations (scope constraint)
    allowed_mutations: list[str] = field(default_factory=lambda: [
        "signal_threshold",
        "entry_timing",
        "exit_timing",
        "filter_volatility",
        "filter_volume",
        "filter_liquidity",
        "position_sizing",
        "stop_loss",
        "signal_combination",
    ])

    # Run store
    run_store_dir: Path | None = None

    # Experiment matrix
    trials: int = 1

    # Raw config dict for extensions
    raw: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def load(cls, path: Path) -> GEPAProjectConfig:
        """Load a GEPA project config from a JSON file."""
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"Project config not found: {path}")

        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Resolve paths relative to config file's parent
        base_dir = path.parent
        if "baseline_genome" in data and data["baseline_genome"]:
            data["baseline_genome"] = str(base_dir / data["baseline_genome"])

        config = cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})
        config.raw = data
        return config

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict for JSON."""
        result = {}
        for key, value in self.__dict__.items():
            if key == "raw":
                continue
            if isinstance(value, Path):
                result[key] = str(value)
            else:
                result[key] = value
        return result


def load_gepa_project(project_dir: Path) -> GEPAProjectConfig:
    """
    Load a GEPA project from a directory.

    Looks for:
    1. <project_dir>/gepaharness.json
    2. <project_dir>/gepa.json
    3. <project_dir>/project.json
    """
    project_dir = Path(project_dir)

    candidates = [
        project_dir / "gepaharness.json",
        project_dir / "gepa.json",
        project_dir / "project.json",
    ]

    for path in candidates:
        if path.exists():
            return GEPAProjectConfig.load(path)

    raise FileNotFoundError(
        f"No GEPA project config found in {project_dir}. "
        f"Looked for: {[str(p) for p in candidates]}"
    )
