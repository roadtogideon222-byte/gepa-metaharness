from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Sequence

from ..bootstrap import collect_environment_bootstrap
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
        allowed_write_paths: Sequence[str] | None = None,
    ) -> None:
        self.baseline = baseline.resolve()
        self.proposer = proposer
        self.evaluator = evaluator
        self.validator = validator
        self.run_dir = run_dir.resolve()
        self.budget = budget
        self.objective = objective
        self.constraints = list(constraints or [])
        self.allowed_write_paths = [self._normalize_allowed_path(value) for value in (allowed_write_paths or []) if str(value).strip()]
        self.store = FilesystemRunStore(self.run_dir)

    def _build_instructions(self, parent: CandidateRecord) -> AgentInstructions:
        return AgentInstructions(
            objective=self.objective,
            constraints=self._instruction_constraints(),
            workspace_layout=(
                "The candidate workspace is the directory under optimization. "
                "The .metaharness directory contains run metadata, a compact environment bootstrap, "
                "and prior results."
            ),
            allowed_actions=[
                "Read and edit files inside the candidate workspace.",
                "Use the bootstrap snapshot under .metaharness/bootstrap to avoid redundant exploration.",
                "Inspect prior candidate artifacts under .metaharness.",
                "Use lightweight commands when needed to understand the workspace.",
            ],
            forbidden_actions=[
                "Do not modify evaluation artifacts outside the current candidate workspace.",
                *self._write_scope_forbidden_actions(),
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
                "allowed_write_paths": self.allowed_write_paths,
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
        baseline.outcome = "baseline"
        baseline.outcome_summary = "Baseline candidate."
        self.store.write_candidate_manifest(baseline)

        best = baseline
        candidates = [baseline.candidate_id]

        for _ in range(self.budget):
            parent = best
            candidate = self.store.materialize_candidate(parent)
            instructions = self._build_instructions(parent)
            bootstrap = collect_environment_bootstrap(candidate.workspace_dir)
            proposal_request = self.store.write_instruction_bundle(
                candidate=candidate,
                parent=parent,
                instructions=instructions,
                proposer_name=self.proposer.name,
                bootstrap=bootstrap,
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
            workspace_change_count = int(diff_metadata["workspace_change_count"])
            candidate.proposal_applied = proposal_result.applied
            self.store.write_proposal_result(candidate.candidate_id, proposal_result)

            if not proposal_result.applied:
                candidate.valid = False
                candidate.objective = float("-inf")
                candidate.outcome = self._classify_failed_proposal(proposal_result)
                candidate.outcome_summary = proposal_result.summary
            elif violation_paths := self._scope_violations(proposal_result.changed_files):
                candidate.valid = False
                candidate.objective = float("-inf")
                candidate.outcome = "scope-violation"
                candidate.scope_violation_paths = violation_paths
                candidate.outcome_summary = (
                    "Changed files outside the allowed write scope: "
                    + ", ".join(violation_paths)
                )
            elif workspace_change_count == 0:
                candidate.valid = parent.valid
                candidate.objective = parent.objective
                candidate.outcome = "no-change"
                candidate.outcome_summary = "No workspace changes detected relative to the parent candidate."
            else:
                validation = self.validator.validate(candidate.workspace_dir)
                candidate.valid = validation.ok
                self.store.write_validation_result(candidate.candidate_id, validation)
                if validation.ok:
                    evaluation = self.evaluator.evaluate(candidate.workspace_dir)
                    candidate.objective = evaluation.objective
                    self.store.write_evaluation_result(candidate.candidate_id, evaluation)
                    if parent.objective is None or candidate.objective > parent.objective:
                        candidate.outcome = "keep"
                        candidate.outcome_summary = self._keep_summary(parent, candidate)
                        best = candidate
                    else:
                        candidate.outcome = "discard"
                        candidate.outcome_summary = self._discard_summary(parent, candidate)
                else:
                    candidate.objective = float("-inf")
                    candidate.outcome = "discard"
                    candidate.outcome_summary = validation.summary

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

    @staticmethod
    def _classify_failed_proposal(result) -> str:
        if bool(result.metadata.get("timed_out")):
            return "timeout"
        return "crash"

    @staticmethod
    def _keep_summary(parent: CandidateRecord, candidate: CandidateRecord) -> str:
        return (
            "Objective improved from "
            f"{MetaHarnessEngine._format_objective(parent.objective)} to "
            f"{MetaHarnessEngine._format_objective(candidate.objective)}."
        )

    @staticmethod
    def _discard_summary(parent: CandidateRecord, candidate: CandidateRecord) -> str:
        return (
            "Objective "
            f"{MetaHarnessEngine._format_objective(candidate.objective)} did not improve over "
            f"{parent.candidate_id} ({MetaHarnessEngine._format_objective(parent.objective)})."
        )

    @staticmethod
    def _format_objective(value: float | None) -> str:
        if value is None:
            return "None"
        return f"{value:.3f}"

    def _instruction_constraints(self) -> list[str]:
        constraints = list(self.constraints)
        if self.allowed_write_paths:
            constraints.append(
                "Only modify files within the allowed write scope: "
                + ", ".join(self.allowed_write_paths)
            )
        return constraints

    def _write_scope_forbidden_actions(self) -> list[str]:
        if not self.allowed_write_paths:
            return []
        return [
            "Do not edit files outside the allowed write scope: "
            + ", ".join(self.allowed_write_paths)
        ]

    def _scope_violations(self, changed_files: Sequence[str]) -> list[str]:
        if not self.allowed_write_paths:
            return []
        violations: list[str] = []
        for path in changed_files:
            normalized_path = self._normalize_relative_path(path)
            if normalized_path is None:
                continue
            if not any(self._path_is_allowed(normalized_path, allowed) for allowed in self.allowed_write_paths):
                violations.append(normalized_path)
        return sorted(set(violations))

    @staticmethod
    def _path_is_allowed(path: str, allowed: str) -> bool:
        if allowed in {"*", "."}:
            return True
        if path == allowed:
            return True
        return path.startswith(f"{allowed}/")

    @staticmethod
    def _normalize_relative_path(value: str) -> str | None:
        text = str(value).replace("\\", "/").strip().strip("/")
        if not text or text in {".", ".."}:
            return None
        parts = [part for part in text.split("/") if part not in {"", "."}]
        if any(part == ".." for part in parts):
            return None
        return "/".join(parts)

    @classmethod
    def _normalize_allowed_path(cls, value: str) -> str:
        normalized = cls._normalize_relative_path(value)
        if normalized is None:
            return "."
        return normalized
