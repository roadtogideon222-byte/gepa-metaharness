from __future__ import annotations

import subprocess
from pathlib import Path

from ..models import ProposalExecution, ProposalRequest, ProposalResult
from .base import ProposerBackend
from .parsers.gemini import parse_gemini_json


class GeminiCliBackend(ProposerBackend):
    name = "gemini"

    def __init__(
        self,
        gemini_binary: str = "gemini",
        model: str | None = None,
        output_format: str = "json",
        sandbox: bool | str | None = None,
        approval_mode: str | None = None,
        extra_args: list[str] | None = None,
    ) -> None:
        self.gemini_binary = gemini_binary
        self.model = model
        self.output_format = output_format
        self.sandbox = sandbox
        self.approval_mode = approval_mode
        self.extra_args = extra_args or []

    def prepare(self, request: ProposalRequest) -> ProposalRequest:
        return request

    def invoke(self, request: ProposalRequest) -> ProposalExecution:
        proposal_dir = request.candidate_dir / "proposal"
        proposal_dir.mkdir(parents=True, exist_ok=True)
        stdout_path = proposal_dir / "stdout.jsonl"
        stderr_path = proposal_dir / "stderr.txt"
        prompt = request.prompt_path.read_text(encoding="utf-8")

        command = [self.gemini_binary]
        if self.model:
            command.extend(["--model", self.model])
        if self.output_format:
            command.extend(["--output-format", self.output_format])
        if self.sandbox is not None:
            command.extend(["--sandbox", str(self.sandbox).lower()])
        if self.approval_mode:
            command.extend(["--approval-mode", self.approval_mode])
        command.extend(self.extra_args)
        command.extend(["-p", prompt])

        completed = subprocess.run(
            command,
            cwd=request.workspace_dir,
            text=True,
            capture_output=True,
        )
        stdout_path.write_text(completed.stdout, encoding="utf-8")
        stderr_path.write_text(completed.stderr, encoding="utf-8")

        return ProposalExecution(
            command=command,
            cwd=request.workspace_dir,
            stdout_path=stdout_path,
            stderr_path=stderr_path,
            returncode=completed.returncode,
        )

    def collect(self, execution: ProposalExecution) -> ProposalResult:
        events, final_text, changed_files = parse_gemini_json(execution.stdout_path)
        applied = execution.returncode == 0
        return ProposalResult(
            applied=applied,
            summary="Gemini CLI execution completed." if applied else "Gemini CLI execution failed.",
            final_text=final_text,
            changed_files=changed_files,
            events=events,
            raw_stdout_path=execution.stdout_path,
            raw_stderr_path=execution.stderr_path,
            metadata={
                "command": execution.command,
                "returncode": execution.returncode,
            },
        )
