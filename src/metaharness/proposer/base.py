from __future__ import annotations

from typing import Protocol

from ..models import ProposalExecution, ProposalRequest, ProposalResult


class ProposerBackend(Protocol):
    name: str

    def prepare(self, request: ProposalRequest) -> ProposalRequest: ...

    def invoke(self, request: ProposalRequest) -> ProposalExecution: ...

    def collect(self, execution: ProposalExecution) -> ProposalResult: ...
