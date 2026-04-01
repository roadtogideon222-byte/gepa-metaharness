from __future__ import annotations

from pathlib import Path
from typing import Protocol

from ..models import EvaluationResult, ValidationResult


class EvaluatorProtocol(Protocol):
    def evaluate(self, workspace: Path) -> EvaluationResult: ...


class ValidatorProtocol(Protocol):
    def validate(self, workspace: Path) -> ValidationResult: ...
