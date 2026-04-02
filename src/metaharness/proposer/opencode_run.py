from __future__ import annotations

import subprocess
from shutil import which
from typing import Any

from ..models import ProposalExecution, ProposalRequest, ProposalResult
from .base import ProposerBackend
from .parsers.opencode import parse_opencode_jsonl


class OpenCodeRunBackend(ProposerBackend):
    name = "opencode"

    def __init__(
        self,
        opencode_binary: str = "opencode",
        model: str | None = None,
        agent: str | None = None,
        variant: str | None = None,
        output_format: str = "json",
        extra_args: list[str] | None = None,
        timeout_seconds: float | None = None,
    ) -> None:
        self.opencode_binary = opencode_binary
        self.model = model
        self.agent = agent
        self.variant = variant
        self.output_format = output_format
        self.extra_args = extra_args or []
        self.timeout_seconds = timeout_seconds

    def prepare(self, request: ProposalRequest) -> ProposalRequest:
        return request

    def invoke(self, request: ProposalRequest) -> ProposalExecution:
        proposal_dir = request.candidate_dir / "proposal"
        proposal_dir.mkdir(parents=True, exist_ok=True)
        stdout_path = proposal_dir / "stdout.jsonl"
        stderr_path = proposal_dir / "stderr.txt"
        prompt = request.prompt_path.read_text(encoding="utf-8")

        command = [self.opencode_binary, "run"]
        if self.output_format:
            command.extend(["--format", self.output_format])
        if self.model:
            command.extend(["--model", self.model])
        if self.agent:
            command.extend(["--agent", self.agent])
        if self.variant:
            command.extend(["--variant", self.variant])
        command.extend(self.extra_args)
        command.append(prompt)

        timed_out = False
        timeout_message = ""
        try:
            completed = subprocess.run(
                command,
                cwd=request.workspace_dir,
                text=True,
                capture_output=True,
                timeout=self.timeout_seconds,
            )
            stdout = completed.stdout
            stderr = completed.stderr
            returncode = completed.returncode
        except subprocess.TimeoutExpired as exc:
            timed_out = True
            stdout = _coerce_timeout_stream(exc.stdout)
            stderr = _coerce_timeout_stream(exc.stderr)
            timeout_message = (
                f"OpenCode proposal timed out after {self.timeout_seconds:g}s."
                if self.timeout_seconds is not None
                else "OpenCode proposal timed out."
            )
            if timeout_message not in stderr:
                stderr = f"{stderr}\n{timeout_message}".strip()
            returncode = 124

        stdout_path.write_text(stdout, encoding="utf-8")
        stderr_path.write_text(stderr, encoding="utf-8")

        return ProposalExecution(
            command=command,
            cwd=request.workspace_dir,
            stdout_path=stdout_path,
            stderr_path=stderr_path,
            returncode=returncode,
            metadata={"timed_out": timed_out, "timeout_message": timeout_message},
        )

    def collect(self, execution: ProposalExecution) -> ProposalResult:
        events, final_text, changed_files = parse_opencode_jsonl(execution.stdout_path)
        timed_out = bool(execution.metadata.get("timed_out"))
        applied = execution.returncode == 0 and not timed_out
        summary = "OpenCode execution completed."
        if timed_out:
            summary = str(execution.metadata.get("timeout_message") or "OpenCode execution timed out.")
        elif not applied:
            summary = "OpenCode execution failed."
        return ProposalResult(
            applied=applied,
            summary=summary,
            final_text=final_text,
            changed_files=changed_files,
            events=events,
            raw_stdout_path=execution.stdout_path,
            raw_stderr_path=execution.stderr_path,
            metadata={
                "command": execution.command,
                "returncode": execution.returncode,
                "model": self.model,
                "agent": self.agent,
                "variant": self.variant,
                "output_format": self.output_format,
                "timeout_seconds": self.timeout_seconds,
                "timed_out": timed_out,
            },
        )


def probe_opencode_cli(opencode_binary: str = "opencode", timeout_seconds: int = 5) -> dict[str, Any]:
    resolved_binary = which(opencode_binary)
    if resolved_binary is None:
        return {
            "ok": False,
            "binary": opencode_binary,
            "resolved_binary": None,
            "version": None,
            "returncode": None,
            "raw_output": "",
            "error": f"Could not find binary: {opencode_binary}",
        }

    try:
        completed = subprocess.run(
            [opencode_binary, "--version"],
            text=True,
            capture_output=True,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired:
        return {
            "ok": False,
            "binary": opencode_binary,
            "resolved_binary": resolved_binary,
            "version": None,
            "returncode": None,
            "raw_output": "",
            "error": f"Timed out after {timeout_seconds}s probing {opencode_binary}",
        }

    raw_output = "\n".join(
        value for value in [completed.stdout.strip(), completed.stderr.strip()] if value
    ).strip()
    version = raw_output.splitlines()[0].strip() if raw_output else None
    return {
        "ok": completed.returncode == 0,
        "binary": opencode_binary,
        "resolved_binary": resolved_binary,
        "version": version,
        "returncode": completed.returncode,
        "raw_output": raw_output,
        "error": None if completed.returncode == 0 else raw_output or f"{opencode_binary} --version failed",
    }


def _coerce_timeout_stream(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value
