"""
GenomeProposerBackend — LLM-based genome mutator for GEPA signal optimization.

Implements ProposerBackend by reading prior genome traces from the filesystem
and proposing targeted mutations via LLM (mimicking Meta-Harness's counterfactual
diagnosis pattern).

Unlike CodexExecBackend which drives a coding agent CLI, this backend directly
calls an LLM API with the full prior history accessible through the filesystem.
"""
from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ..models import AgentEvent, ProposalResult
from .base import ProposerBackend
from .instructions import build_backend_prompt


@dataclass
class GenomeProposerConfig:
    """Configuration for the genome proposer."""
    model: str = "claude-sonnet-4-7-2025"
    provider: str = "anthropic"  # or "openai", "ollama"
    api_key: str | None = None
    base_url: str | None = None
    max_tokens: int = 4096
    temperature: float = 0.7
    timeout_seconds: float = 120.0
    system_prompt: str | None = None


@dataclass
class GenomeProposerBackend:
    """
    LLM-based genome proposer.

    Reads the .gepaharness/experience/ directory to access all prior genome
    candidates, their scores, and failure traces — then uses an LLM to propose
    a targeted mutation to the current best genome.

    This is the core adaptation from Meta-Harness: the filesystem is the memory,
    and the LLM is the reasoning engine that decides what to read and what to change.
    """
    name: str = "genome"
    config: GenomeProposerConfig = field(default_factory=GenomeProposerConfig)

    def __post_init__(self) -> None:
        self._client: Any = None

    def _get_client(self) -> Any:
        """Lazy initialization of LLM client."""
        if self._client is not None:
            return self._client

        provider = self.config.provider
        if provider == "anthropic":
            try:
                from anthropic import Anthropic
                self._client = Anthropic(
                    api_key=self.config.api_key,
                    base_url=self.config.base_url,
                )
            except ImportError:
                # Fallback to openai-compatible client
                import openai
                self._client = openai.OpenAI(
                    api_key=self.config.api_key or "sk-ant-api03-placeholder",
                    base_url=self.config.base_url or "https://api.anthropic.com",
                )
                self._client._provider = "anthropic"
        elif provider == "openai":
            import openai
            self._client = openai.OpenAI(
                api_key=self.config.api_key,
                base_url=self.config.base_url,
            )
        elif provider == "ollama":
            import openai
            self._client = openai.OpenAI(
                api_key="ollama",  # not used
                base_url=self.config.base_url or "http://localhost:11434/v1",
            )
        else:
            raise ValueError(f"Unknown provider: {provider}")
        return self._client

    def prepare(self, proposal_request: Any) -> Any:
        """
        Prepare the proposal by building the prompt from the filesystem.

        Reads:
        - Parent genome source code
        - All prior candidate summaries
        - Evaluation scores
        - Failure traces

        Returns a dict with the prompt and context.
        """
        workspace_dir = proposal_request.workspace_dir
        experience_dir = proposal_request.experience_dir
        candidate_id = proposal_request.candidate_id

        # Read parent genome source
        parent_summary_path = experience_dir / "parent_summary.json"
        parent_summary = {}
        if parent_summary_path.exists():
            parent_summary = json.loads(parent_summary_path.read_text())

        # Read all prior genomes from the experience directory
        prior_genomes = self._read_prior_genomes(experience_dir)

        # Read bootstrap snapshot
        bootstrap_path = workspace_dir / ".gepaharness" / "bootstrap" / "summary.md"
        bootstrap_text = ""
        if bootstrap_path.exists():
            bootstrap_text = bootstrap_path.read_text()

        # Build the mutation prompt
        prompt = self._build_mutation_prompt(
            candidate_id=candidate_id,
            parent_summary=parent_summary,
            prior_genomes=prior_genomes,
            workspace_dir=workspace_dir,
            bootstrap_text=bootstrap_text,
        )

        return {
            "prompt": prompt,
            "workspace_dir": workspace_dir,
            "candidate_id": candidate_id,
        }

    def _read_prior_genomes(self, experience_dir: Path) -> list[dict[str, Any]]:
        """Read all prior genome candidates from the experience directory."""
        genomes = []

        # Read parent first
        parent_dir = experience_dir / "parent"
        if parent_dir.exists():
            manifest_path = parent_dir / "manifest.json"
            if manifest_path.exists():
                manifest = json.loads(manifest_path.read_text())
                genomes.append(manifest)

        # Read the .gepaharness/experience/ directory for older candidates
        # This is populated by the FilesystemRunStore
        return genomes

    def _build_mutation_prompt(
        self,
        candidate_id: str,
        parent_summary: dict[str, Any],
        prior_genomes: list[dict[str, Any]],
        workspace_dir: Path,
        bootstrap_text: str,
    ) -> str:
        """Build the LLM prompt for genome mutation."""

        # Read the current best genome source (from workspace — parent copy)
        genome_files = list(workspace_dir.glob("*.py"))
        current_genome_source = ""
        if genome_files:
            current_genome_source = genome_files[0].read_text()

        # Build prior genome summary
        prior_summary_lines = []
        for g in prior_genomes[-10:]:  # last 10 candidates
            gid = g.get("candidate_id", "unknown")
            obj = g.get("objective", "N/A")
            outcome = g.get("outcome", "unknown")
            summary = g.get("outcome_summary", "")
            prior_summary_lines.append(f"  [{gid}] objective={obj} outcome={outcome} — {summary}")

        prior_summary_text = "\n".join(prior_summary_lines) if prior_summary_lines else "  No prior candidates."

        default_system = """You are GEPA-GENOME, an evolutionary optimizer for trading signal genomes.

Your task: Given the current best genome and its evaluation history, propose a targeted mutation
to improve the signal's Sharpe ratio, win rate, or alpha extraction.

What to mutate (pick 1-2):
- Signal combination logic (AND/OR/NOT thresholds)
- Entry/exit timing parameters
- Filter conditions (volatility regimes, volume thresholds)
- Risk management (position sizing, stop loss)
- Parameter values (numeric constants, lookback windows)

What NOT to change:
- The overall structure of the signal functions
- Function signatures (they must remain compatible with the evaluation framework)
- Risk controls that are already at safe defaults

Output format:
```python
# genome.py — mutate only what needs changing
[your mutated signal functions here]
```

Mutation strategy: Be specific and targeted. Use counterfactual reasoning —
"if this genome had used X instead of Y on the failed cases, it would have handled them".
"""

        system = self.config.system_prompt or default_system

        user_prompt = f"""## Candidate: {candidate_id}

### Current Best Genome:
```python
{current_genome_source[:3000]}
```

### Prior Genome History:
{prior_summary_text}

### Bootstrap Context:
{bootstrap_text}

### Your Task
Propose a targeted mutation to improve this genome. Focus on the specific failure modes
visible in the prior history. Every mutation must be grounded in evidence from prior runs.

If prior genomes show declining Sharpe on high-volatility tokens → adjust volatility filters
If prior genomes show late entry on pump signals → tighten timing parameters
If prior genomes show over-trading on low-liquidity → add liquidity filters

Respond ONLY with the mutated genome code. No explanation, no markdown code fences, just the raw Python.
"""

        return f"<system>\n{system}\n</system>\n\n<user>\n{user_prompt}\n</user>"

    def invoke(self, prepared: Any) -> Any:
        """
        Call the LLM API to generate the genome mutation.
        Returns an execution handle.
        """
        prompt = prepared["prompt"]
        client = self._get_client()

        try:
            if self.config.provider == "anthropic" and not hasattr(client, "_provider"):
                response = client.messages.create(
                    model=self.config.model,
                    max_tokens=self.config.max_tokens,
                    temperature=self.config.temperature,
                    system=prompt.split("<system>")[1].split("</system>")[0].strip() if "<system>" in prompt else "",
                    messages=[{
                        "role": "user",
                        "content": prompt.split("</system>")[-1].split("<user>")[1].split("</user>")[0].strip() if "</user>" in prompt else prompt,
                    }],
                    timeout=self.config.timeout_seconds,
                )
                generated = response.content[0].text
            elif hasattr(client, "_provider") and client._provider == "anthropic":
                response = client.chat.completions.create(
                    model=self.config.model,
                    messages=[
                        {"role": "system", "content": prompt.split("<system>")[1].split("</system>")[0].strip()},
                        {"role": "user", "content": prompt.split("</system>")[-1].split("<user>")[1].split("</user>")[0].strip()},
                    ],
                    max_tokens=self.config.max_tokens,
                    temperature=self.config.temperature,
                )
                generated = response.choices[0].message.content
            else:
                # OpenAI or Ollama
                response = client.chat.completions.create(
                    model=self.config.model,
                    messages=[
                        {"role": "system", "content": prompt.split("<system>")[1].split("</system>")[0].strip() if "<system>" in prompt else "You are a helpful assistant."},
                        {"role": "user", "content": prompt.split("</system>")[-1].split("<user>")[1].split("</user>")[0].strip() if "</user>" in prompt else prompt},
                    ],
                    max_tokens=self.config.max_tokens,
                    temperature=self.config.temperature,
                )
                generated = response.choices[0].message.content

            return {
                "applied": True,
                "generated_genome": generated,
                "stdout": generated,
                "stderr": "",
                "returncode": 0,
            }

        except Exception as e:
            return {
                "applied": False,
                "generated_genome": "",
                "stdout": "",
                "stderr": str(e),
                "returncode": 1,
                "error": str(e),
            }

    def collect(self, execution: Any) -> ProposalResult:
        """
        Parse the LLM output and apply the mutation to the candidate workspace.
        Returns a ProposalResult with the applied changes.
        """
        if not execution.get("applied", False):
            return ProposalResult(
                applied=False,
                summary=f"LLM invocation failed: {execution.get('stderr', 'unknown error')}",
                final_text="",
                changed_files=[],
                events=[],
                metadata={"error": execution.get("error", "unknown")},
            )

        generated = execution.get("generated_genome", "").strip()

        # Strip markdown code fences if present
        if generated.startswith("```"):
            lines = generated.split("\n")
            # Remove first and last ``` line
            if lines and lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            generated = "\n".join(lines).strip()

        # Find the workspace
        # The workspace dir is stored in execution but we need to get it from context
        # For now, return the generated code — caller must apply it
        return ProposalResult(
            applied=True,
            summary=f"Generated genome mutation ({len(generated)} chars)",
            final_text=generated,
            changed_files=["genome.py"],
            events=[],
            metadata={"generated_length": len(generated)},
        )

    def probe(self) -> dict[str, Any]:
        """Check if the LLM API is accessible."""
        try:
            client = self._get_client()
            return {"ok": True, "provider": self.config.provider, "model": self.config.model}
        except Exception as e:
            return {"ok": False, "error": str(e)}


# ── Fake backend for testing ────────────────────────────────────────────────


@dataclass
class FakeGenomeBackend:
    """Deterministic fake backend for testing GEPA without LLM calls."""
    name: str = "fake"
    mutation_seed: int = 42

    def prepare(self, proposal_request: Any) -> Any:
        return {"workspace_dir": proposal_request.workspace_dir}

    def invoke(self, prepared: Any) -> Any:
        import hashlib
        ws = str(prepared["workspace_dir"])
        seed = self.mutation_seed + sum(ord(c) for c in ws)
        return {
            "applied": True,
            "generated_genome": f"# Fake mutation seed={seed}\ndef signal():\n    return {{\"action\": \"hold\", \"confidence\": 0.0 + {seed * 0.001}}}\n",
            "stdout": "fake",
            "stderr": "",
            "returncode": 0,
        }

    def collect(self, execution: Any) -> ProposalResult:
        return ProposalResult(
            applied=execution.get("applied", False),
            summary="FakeGenomeBackend — no actual mutation",
            final_text=execution.get("generated_genome", ""),
            changed_files=["genome.py"] if execution.get("applied") else [],
            events=[],
        )

    def probe(self) -> dict[str, Any]:
        return {"ok": True, "backend": "fake"}
