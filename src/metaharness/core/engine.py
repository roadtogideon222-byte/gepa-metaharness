from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Sequence

from ..models import (
    AgentInstructions,
    CandidateRecord,
    OptimizeResult,
)
from ..proposer.base import ProposerBackend
from ..store.filesystem import FilesystemRunStore
from .protocols import EvaluatorProtocol, ValidatorProtocol


class MetaHarnessEngine:
    def __init__(
        self,
        baseline: Path,
        proposer: ProposerBackend,
        evaluator: EvaluatorProtocol,
        validator: ValidatorProtocol,
        run_dir: Path,
        budget: int,
        objective: str,
        constraints: Sequence[str] | None = None,
    ) -> None:
        self.baseline = baseline.resolve()
        self.proposer = proposer
        self.evaluator = evaluator
        self.validator = validator
        self.run_dir = run_dir.resolve()
        self.budget = budget
        self.objective = objective
        self.constraints = list(constraints or [])
        self.store = FilesystemRunStore(self.run_dir)

    def _build_instructions(self, parent: CandidateRecord) -> AgentInstructions:
        return AgentInstructions(
            objective=self.objective,
            constraints=self.constraints,
            workspace_layout=(
                "The candidate workspace is the directory under optimization. "
                "The .metaharness directory contains run metadata and prior results."
            ),
            allowed_actions=[
                "Read and edit files inside the candidate workspace.",
                "Inspect prior candidate artifacts under .metaharness.",
                "Use lightweight commands when needed to understand the workspace.",
            ],
            forbidden_actions=[
                "Do not modify evaluation artifacts outside the current candidate workspace.",
                "Do not fabricate success. The external validator and evaluator decide outcomes.",
            ],
            evaluation_contract=(
                "Your job is to improve the harness so that external validation passes and the "
                "objective score increases relative to the parent candidate "
                f"({parent.candidate_id})."
            ),
        )

    def run(self) -> OptimizeResult:
        self.store.initialize_run(
            {
                "objective": self.objective,
                "constraints": self.constraints,
                "budget": self.budget,
                "proposer": self.proposer.name,
                "baseline": str(self.baseline),
            }
        )

        baseline = self.store.materialize_baseline(self.baseline)
        baseline.proposal_applied = True
        baseline_validation = self.validator.validate(baseline.workspace_dir)
        self.store.write_validation_result(baseline.candidate_id, baseline_validation)
        baseline.valid = baseline_validation.ok
        if baseline.valid:
            baseline_eval = self.evaluator.evaluate(baseline.workspace_dir)
            self.store.write_evaluation_result(baseline.candidate_id, baseline_eval)
            baseline.objective = baseline_eval.objective
        else:
            baseline.objective = float("-inf")
        self.store.write_candidate_manifest(baseline)

        best = baseline
        candidates = [baseline.candidate_id]

        for _ in range(self.budget):
            candidate = self.store.materialize_candidate(best)
            instructions = self._build_instructions(best)
            proposal_request = self.store.write_instruction_bundle(
                candidate=candidate,
                parent=best,
                instructions=instructions,
                proposer_name=self.proposer.name,
            )
            execution = self.proposer.invoke(self.proposer.prepare(proposal_request))
            proposal_result = self.proposer.collect(execution)
            diff_metadata = self.store.capture_workspace_diff(parent=best, candidate=candidate)
            proposal_result.changed_files = sorted(
                set(proposal_result.changed_files) | set(diff_metadata["workspace_changed_files"])
            )
            proposal_result.metadata = {
                **proposal_result.metadata,
                "workspace_diff_path": diff_metadata["workspace_diff_path"],
                "workspace_changes_path": diff_metadata["workspace_changes_path"],
                "workspace_change_count": diff_metadata["workspace_change_count"],
            }
            candidate.proposal_applied = proposal_result.applied
            self.store.write_proposal_result(candidate.candidate_id, proposal_result)

            if proposal_result.applied:
                validation = self.validator.validate(candidate.workspace_dir)
                candidate.valid = validation.ok
                self.store.write_validation_result(candidate.candidate_id, validation)
                if validation.ok:
                    evaluation = self.evaluator.evaluate(candidate.workspace_dir)
                    candidate.objective = evaluation.objective
                    self.store.write_evaluation_result(candidate.candidate_id, evaluation)
                    if best.objective is None or candidate.objective > best.objective:
                        best = candidate
                else:
                    candidate.objective = float("-inf")
            else:
                candidate.valid = False
                candidate.objective = float("-inf")

            self.store.write_candidate_manifest(candidate)
            candidates.append(candidate.candidate_id)

        self.store.write_index(
            {
                "best_candidate_id": best.candidate_id,
                "best_objective": best.objective,
                "candidates": candidates,
                "completed_at": datetime.now(UTC).isoformat(),
            }
        )
        return OptimizeResult(
            run_dir=self.run_dir,
            run_id=self.store.run_id,
            best_candidate_id=best.candidate_id,
            best_workspace_dir=best.workspace_dir,
            best_objective=best.objective if best.objective is not None else float("-inf"),
            candidate_ids=candidates,
        )
