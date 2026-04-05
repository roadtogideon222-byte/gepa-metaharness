"""
GEPA Runner — Constitutional critique + trait monitoring outer loop.

Full CAI-inspired + Anthropic stack GEPA optimization loop:

  Genome Proposal
       ↓
  ConstitutionalCritiqueEngine.critique_with_revision()    ← Layer 3: Validation
       ↓
  Tier 1 veto check ← reject if violations remain
       ↓
  Backtest on historical data
       ↓
  apply_critique_penalties() + score_from_tier3_metrics() ← Layer 3 scoring
       ↓
  TraitMonitor.assess()                                    ← Layer 4: Trait Control
       ↓
  Update Pareto front
  Store all artifacts
       ↓
  Next iteration

Layer 5 (Interpretability) is triggered selectively when trait monitoring
flags unexplained failures.
"""
from __future__ import annotations

import json
import shutil
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ..core.engine import MetaHarnessEngine
from ..core.protocols import EvaluatorProtocol, ValidatorProtocol
from ..models import EvaluationResult, ValidationResult, CandidateRecord, OptimizeResult
from ..proposer.base import ProposerBackend
from .critique import (
    ConstitutionalCritiqueEngine,
    CritiqueConfig,
    CritiqueResult,
    apply_critique_penalties,
    score_from_tier3_metrics,
    veto_summary,
    full_critique_summary,
)
from .trait_monitor import (
    TraitMonitor,
    TraitMonitorConfig,
    TraitReport,
    format_trait_report,
    format_trend_summary,
)
from .config.genome import GEPAProjectConfig


@dataclass
class GEPARunnerConfig:
    """Configuration for the GEPA runner."""
    # Critique
    critique_config: CritiqueConfig = field(default_factory=CritiqueConfig)
    # Trait monitoring
    trait_config: TraitMonitorConfig = field(default_factory=TraitMonitorConfig)
    # Max genomes to evaluate in one run
    max_candidates: int = 50
    # Min score to consider a genome "improving"
    min_improvement: float = 0.01
    # Store critique artifacts
    store_critiques: bool = True
    # Store Pareto front snapshots every N generations
    pareto_snapshot_interval: int = 10


class GEPARunner:
    """
    GEPA outer loop with constitutional critique.

    Usage:
        config = GEPARunnerConfig(
            critique_config=CritiqueConfig(
                llm=CritiqueLLMConfig(model="claude-sonnet-4-7-2025")
            )
        )
        runner = GEPARunner(
            runner_config=config,
            baseline_genome=Path("genome_v1.py"),
            proposer=GenomeProposerBackend(),
            evaluator=TradingEvaluator(),
            validator=TradingValidator(),
            run_dir=Path("runs/gepa_run_001"),
        )
        result = runner.run()
    """

    def __init__(
        self,
        runner_config: GEPARunnerConfig,
        baseline_genome: Path,
        proposer: ProposerBackend,
        evaluator: EvaluatorProtocol,
        validator: ValidatorProtocol,
        run_dir: Path,
        project_config: GEPAProjectConfig | None = None,
    ):
        self.config = runner_config
        self.baseline_genome = baseline_genome
        self.proposer = proposer
        self.evaluator = evaluator
        self.validator = validator
        self.run_dir = run_dir.resolve()
        self.project_config = project_config or GEPAProjectConfig(
            baseline_genome=str(baseline_genome),
            budget=runner_config.max_candidates,
        )

        # Inner MetaHarness engine for filesystem management
        self._engine = MetaHarnessEngine(
            baseline=baseline_genome,
            proposer=proposer,
            evaluator=evaluator,
            validator=validator,
            run_dir=run_dir,
            budget=runner_config.max_candidates,
            objective=project_config.objective_metric if project_config else "sharpe",
        )

        # Critique engine
        self._critique = ConstitutionalCritiqueEngine(runner_config.critique_config)

        # Trait monitor (Layer 4)
        trait_history_path = run_dir / "trait_history.json"
        self._trait_monitor = TraitMonitor(
            config=runner_config.trait_config,
            history_path=trait_history_path,
        )

        # Pareto front
        self._pareto: list[dict[str, Any]] = []

    def run(self) -> OptimizeResult:
        """
        Run the full GEPA outer loop:

        1. Baseline evaluation (no critique needed — it's the reference)
        2. For each candidate:
           a. Critique against constitution (up to N iterations)
           b. If veto fails → reject, store as failed candidate
           c. If veto passes → backtest
           d. Apply Tier 2 penalties + Tier 3 optimization
           e. Update Pareto front
           f. Snapshot if needed
        3. Return best genome
        """
        self.run_dir.mkdir(parents=True, exist_ok=True)

        # Write constitution to run directory
        self._store_constitution()

        # Step 1: Evaluate baseline
        baseline_eval = self._evaluate_baseline()
        self._update_pareto(baseline_eval, candidate_id="c0000")

        # Log baseline
        self._write_run_log({
            "event": "baseline",
            "candidate_id": "c0000",
            "score": baseline_eval.objective,
            "veto_passed": True,
            "critique_iterations": 0,
        })

        best = baseline_eval
        best_id = "c0000"

        for i in range(self.config.max_candidates):
            candidate_id = f"c{i+1:04d}"
            self.run_dir.mkdir(parents=True, exist_ok=True)

            # Propose a genome
            proposed_genome = self._propose_genome(candidate_id, best_id)

            # Critique it
            critique = self._critique.critique_with_revision(proposed_genome)

            # Store critique result
            if self.config.store_critiques:
                self._store_critique(candidate_id, critique)

            # Log critique
            self._write_run_log({
                "event": "critique",
                "candidate_id": candidate_id,
                "veto_passed": critique.veto_passed,
                "revision_needed": critique.revision_needed,
                "tier1_violations": [v.principle_id for v in critique.tier1_violations],
                "tier2_flags": [f.principle_id for f in critique.tier2_flags],
                "critique_iterations": critique.iteration,
                "critique_notes": critique.critique_notes[:200],
            })

            # Tier 1 veto — reject without backtest
            if not critique.veto_passed:
                self._write_candidate_manifest(
                    candidate_id=candidate_id,
                    veto_failed=True,
                    violations=[v.principle_id for v in critique.tier1_violations],
                    score=0.0,
                    critique=critique,
                )
                continue

            # Tier 1 passed — use revised genome if LLM revised
            genome_to_eval = critique.revised_genome if critique.revision_needed else proposed_genome

            # Validate
            validation = self._validate_genome(genome_to_eval, candidate_id)
            if not validation.ok:
                self._write_candidate_manifest(
                    candidate_id=candidate_id,
                    veto_failed=False,
                    validation_failed=True,
                    validation_summary=validation.summary,
                    score=0.0,
                    critique=critique,
                )
                continue

            # Backtest
            backtest_result = self._backtest_genome(genome_to_eval, candidate_id)

            # Apply Tier 2 penalties
            penalized_score = apply_critique_penalties(
                base_score=backtest_result.objective,
                critique=critique,
            )

            # Apply Tier 3 optimization bonus
            final_score = score_from_tier3_metrics(
                metrics=critique.tier3_metrics,
                base_score=penalized_score,
            )

            # Check if this is an improvement
            improvement = final_score - best.objective if best.objective is not None else final_score
            is_keep = improvement >= self.config.min_improvement

            # Store backtest + final score
            self._write_candidate_manifest(
                candidate_id=candidate_id,
                veto_failed=False,
                validation_failed=False,
                backtest_score=backtest_result.objective,
                penalized_score=penalized_score,
                final_score=final_score,
                is_keep=is_keep,
                critique=critique,
                backtest_result=backtest_result,
            )

            # ── LAYER 4: Trait Monitoring ──────────────────────────────
            # Assess champion genome's behavioral traits periodically
            champion_changed = candidate_id == best_id and is_keep
            should_trait_check = (
                (i + 1) % self.config.trait_config.assessment_interval == 0
                or champion_changed
            )

            trait_report: TraitReport | None = None
            if should_trait_check:
                backtest_summary = {
                    "sharpe": backtest_result.metrics.get("sharpe"),
                    "win_rate": backtest_result.metrics.get("win_rate"),
                    "max_drawdown": backtest_result.metrics.get("max_drawdown"),
                }
                trait_report = self._trait_monitor.assess(
                    genome_source=genome_to_eval,
                    generation=i + 1,
                    backtest_summary=backtest_summary,
                )

                # Store trait report
                if self.config.store_critiques:
                    self._store_trait_report(candidate_id, trait_report)

                # Log trait assessment
                self._write_run_log({
                    "event": "trait_assessment",
                    "candidate_id": candidate_id,
                    "overall_trait_score": trait_report.overall_trait_score,
                    "intervention_recommended": trait_report.intervention_recommended,
                    "most_drifted_trait": trait_report.most_drifted_trait,
                    "trait_recommendations": trait_report.recommendations,
                })

                # Determine intervention type
                if self._trait_monitor.should_intervene(trait_report):
                    intervention = self._trait_monitor.get_intervention_type(trait_report)
                    self._write_run_log({
                        "event": "trait_intervention",
                        "candidate_id": candidate_id,
                        "intervention_type": intervention,
                        "trait_report_summary": format_trait_report(trait_report)[:500],
                    })

            # Update Pareto front
            if is_keep:
                self._update_pareto(backtest_result, candidate_id, final_score)
                if final_score > (best.objective or 0):
                    best = backtest_result
                    best_id = candidate_id

            # Log this iteration
            self._write_run_log({
                "event": "evaluated",
                "candidate_id": candidate_id,
                "backtest_score": backtest_result.objective,
                "penalized_score": penalized_score,
                "final_score": final_score,
                "is_keep": is_keep,
                "is_new_best": candidate_id == best_id,
                "improvement": improvement,
            })

            # Snapshot Pareto front
            if (i + 1) % self.config.pareto_snapshot_interval == 0:
                self._snapshot_pareto(generation=i + 1)

        # Final summary
        self._write_final_report(best_id, best)

        return OptimizeResult(
            run_dir=self.run_dir,
            run_id=self.run_dir.name,
            best_candidate_id=best_id,
            best_workspace_dir=self.run_dir / "candidates" / best_id / "workspace",
            best_objective=best.objective or 0.0,
            candidate_ids=[f"c{i:04d}" for i in range(self.config.max_candidates + 1)],
        )

    def _store_constitution(self) -> None:
        """Write the constitution to the run directory."""
        from .constitution import CONSTITUTION, get_principles_by_tier, PrincipleTier
        constitution_path = self.run_dir / "constitution.json"
        veto_p = get_principles_by_tier(PrincipleTier.VETO)
        penalty_p = get_principles_by_tier(PrincipleTier.PENALTY)
        optimize_p = get_principles_by_tier(PrincipleTier.OPTIMIZE)

        data = {
            "version": "1.0",
            "stored_at": datetime.now(UTC).isoformat(),
            "tier1_veto": [{"id": p.id, "description": p.description} for p in veto_p],
            "tier2_penalty": [{"id": p.id, "description": p.description, "weight": p.weight} for p in penalty_p],
            "tier3_optimize": [{"id": p.id, "description": p.description, "weight": p.weight, "direction": p.direction.value if p.direction else None} for p in optimize_p],
        }
        constitution_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def _evaluate_baseline(self) -> EvaluationResult:
        """Evaluate the baseline genome — no critique needed."""
        if not self.baseline_genome.exists():
            return EvaluationResult(objective=0.0, summary="Baseline genome not found")
        return self.evaluator.evaluate(self.baseline_genome)

    def _propose_genome(self, candidate_id: str, best_id: str) -> str:
        """Use the proposer to generate a genome mutation."""
        # This is a simplified wrapper — the actual proposer
        # reads from the filesystem via FilesystemRunStore
        class _FakeProposalRequest:
            candidate_id = candidate_id
            workspace_dir = self.run_dir / "candidates" / best_id / "workspace"
            experience_dir = self.run_dir / "candidates" / best_id / ".gepaharness" / "experience"
            candidate_dir = self.run_dir / "candidates" / candidate_id

        prepared = self.proposer.prepare(_FakeProposalRequest())
        execution = self.proposer.invoke(prepared)
        result = self.proposer.collect(execution)
        return result.final_text

    def _validate_genome(self, genome_source: str, candidate_id: str) -> ValidationResult:
        """Write genome to temp workspace and validate it."""
        workspace_dir = self.run_dir / "candidates" / candidate_id / "workspace"
        workspace_dir.mkdir(parents=True, exist_ok=True)

        genome_path = workspace_dir / "genome.py"
        genome_path.write_text(genome_source, encoding="utf-8")

        return self.validator.validate(workspace_dir)

    def _backtest_genome(self, genome_source: str, candidate_id: str) -> EvaluationResult:
        """Evaluate the genome on historical data."""
        workspace_dir = self.run_dir / "candidates" / candidate_id / "workspace"
        genome_path = workspace_dir / "genome.py"

        if not genome_path.exists():
            genome_path.write_text(genome_source, encoding="utf-8")

        return self.evaluator.evaluate(workspace_dir)

    def _update_pareto(
        self,
        backtest_result: EvaluationResult,
        candidate_id: str,
        final_score: float | None = None,
    ) -> None:
        """Update the Pareto front."""
        self._pareto.append({
            "candidate_id": candidate_id,
            "objective": backtest_result.objective,
            "final_score": final_score,
            "metrics": backtest_result.metrics,
            "added_at": datetime.now(UTC).isoformat(),
        })
        # Sort by objective descending
        self._pareto.sort(key=lambda x: x.get("objective") or 0, reverse=True)
        # Keep Pareto front — non-dominated solutions
        pareto_path = self.run_dir / "pareto_front.jsonl"
        with open(pareto_path, "a", encoding="utf-8") as f:
            f.write(json.dumps({
                "candidate_id": candidate_id,
                "objective": backtest_result.objective,
                "final_score": final_score,
                "metrics": backtest_result.metrics,
                "timestamp": datetime.now(UTC).isoformat(),
            }) + "\n")

    def _store_critique(self, candidate_id: str, critique: CritiqueResult) -> None:
        """Write critique result to filesystem."""
        critique_dir = self.run_dir / "candidates" / candidate_id / "critique"
        critique_dir.mkdir(parents=True, exist_ok=True)
        (critique_dir / "result.json").write_text(
            json.dumps(critique.to_dict(), indent=2), encoding="utf-8"
        )
        (critique_dir / "raw_response.txt").write_text(
            critique.raw_llm_response, encoding="utf-8"
        )

    def _store_trait_report(self, candidate_id: str, report: TraitReport) -> None:
        """Write trait report to filesystem."""
        trait_dir = self.run_dir / "candidates" / candidate_id / "traits"
        trait_dir.mkdir(parents=True, exist_ok=True)
        (trait_dir / "report.json").write_text(
            json.dumps(report.to_dict(), indent=2), encoding="utf-8"
        )
        (trait_dir / "raw_response.txt").write_text(
            report.raw_llm_response, encoding="utf-8"
        )

    def _write_candidate_manifest(
        self,
        candidate_id: str,
        veto_failed: bool = False,
        validation_failed: bool = False,
        validation_summary: str = "",
        violations: list[str] | None = None,
        score: float = 0.0,
        backtest_score: float | None = None,
        penalized_score: float | None = None,
        final_score: float | None = None,
        is_keep: bool = False,
        critique: CritiqueResult | None = None,
        backtest_result: EvaluationResult | None = None,
    ) -> None:
        """Write a candidate manifest to the filesystem."""
        manifest_dir = self.run_dir / "candidates" / candidate_id
        manifest_dir.mkdir(parents=True, exist_ok=True)

        manifest = {
            "candidate_id": candidate_id,
            "timestamp": datetime.now(UTC).isoformat(),
            "veto_failed": veto_failed,
            "validation_failed": validation_failed,
            "validation_summary": validation_summary,
            "violations": violations or [],
            "score": score,
            "backtest_score": backtest_score,
            "penalized_score": penalized_score,
            "final_score": final_score,
            "is_keep": is_keep,
            "critique_summary": full_critique_summary(critique) if critique else "",
        }
        (manifest_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    def _snapshot_pareto(self, generation: int) -> None:
        """Write a Pareto front snapshot."""
        snapshot_path = self.run_dir / f"pareto_snapshot_gen{generation:04d}.json"
        snapshot_path.write_text(json.dumps({
            "generation": generation,
            "snapshot_at": datetime.now(UTC).isoformat(),
            "pareto": self._pareto,
        }, indent=2), encoding="utf-8")

    def _write_run_log(self, entry: dict[str, Any]) -> None:
        """Append to the run log."""
        log_path = self.run_dir / "run_log.jsonl"
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")

    def _write_final_report(self, best_id: str, best_result: EvaluationResult) -> None:
        """Write final run report."""
        report = {
            "run_id": self.run_dir.name,
            "completed_at": datetime.now(UTC).isoformat(),
            "total_candidates": self.config.max_candidates + 1,
            "best_candidate_id": best_id,
            "best_objective": best_result.objective,
            "best_metrics": best_result.metrics,
            "pareto_size": len(self._pareto),
            "constitution_version": "1.0",
        }
        (self.run_dir / "final_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
