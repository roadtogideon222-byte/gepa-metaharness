from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Sequence

_TRANSIENT_PREFIXES = (
    ".venv/",
    "__pycache__/",
    ".pytest_cache/",
    ".mypy_cache/",
    ".ruff_cache/",
)

_TRANSIENT_SUFFIXES = (
    ".pyc",
    ".pyo",
)

_MAX_REPORTED_CHANGED_FILES = 20


def summarize_run(run_dir: str | Path) -> dict[str, Any]:
    run_dir = Path(run_dir).resolve()
    run_config = _read_json(run_dir / "run_config.json")
    leaderboard = _read_json(run_dir / "indexes" / "leaderboard.json")
    candidates = _load_candidate_manifests(run_dir / "candidates")
    baseline = _find_candidate(candidates, "c0000")
    best = _find_candidate(candidates, str(leaderboard.get("best_candidate_id", "c0000")))
    proposal = _load_first_candidate_proposal(run_dir / "candidates")
    best_proposal = _load_candidate_proposal(run_dir / "candidates", str(leaderboard.get("best_candidate_id", "c0000")))

    baseline_objective = _as_float(baseline.get("objective"))
    best_objective = _as_float(leaderboard.get("best_objective"))
    started_at = run_config.get("started_at")
    completed_at = leaderboard.get("completed_at")
    duration_seconds = _duration_seconds(started_at, completed_at)

    first_improving_candidate = None
    if baseline_objective is not None:
        for candidate in sorted(candidates, key=lambda item: item["candidate_id"]):
            objective = _as_float(candidate.get("objective"))
            if objective is not None and objective > baseline_objective:
                first_improving_candidate = candidate["candidate_id"]
                break

    backend = _extract_backend_summary(run_config, proposal)
    raw_best_changed_files: list[str] = []
    if isinstance(best_proposal, dict):
        raw_best_changed_files = [str(value) for value in best_proposal.get("changed_files", [])]
    filtered_changed_files = _filter_changed_files(raw_best_changed_files)
    best_changed_files = filtered_changed_files[:_MAX_REPORTED_CHANGED_FILES]

    return {
        "run_dir": str(run_dir),
        "run_id": run_dir.name,
        "benchmark_name": _benchmark_name_from_run_config(run_config),
        "objective": run_config.get("objective"),
        "proposer": run_config.get("proposer"),
        "backend_label": backend["backend_label"],
        "model": backend["model"],
        "use_oss": backend["use_oss"],
        "local_provider": backend["local_provider"],
        "proposal_timeout_seconds": backend["proposal_timeout_seconds"],
        "baseline_objective": baseline_objective,
        "best_candidate_id": leaderboard.get("best_candidate_id"),
        "best_objective": best_objective,
        "improved": leaderboard.get("best_candidate_id") != "c0000",
        "first_improving_candidate_id": first_improving_candidate,
        "candidate_count": len(candidates),
        "proposal_applied_count": sum(1 for item in candidates if item.get("proposal_applied")),
        "valid_candidate_count": sum(1 for item in candidates if item.get("valid")),
        "best_changed_files": best_changed_files,
        "best_changed_file_count": len(filtered_changed_files),
        "best_changed_files_truncated_count": max(0, len(filtered_changed_files) - len(best_changed_files)),
        "best_transient_files_omitted_count": max(0, len(raw_best_changed_files) - len(filtered_changed_files)),
        "duration_seconds": duration_seconds,
        "started_at": started_at,
        "completed_at": completed_at,
        "best_summary": _proposal_summary(best_proposal),
        "best_workspace_dir": best.get("workspace_dir") if isinstance(best, dict) else None,
    }


def summarize_project_runs(project_dir: str | Path) -> list[dict[str, Any]]:
    project_dir = Path(project_dir).resolve()
    runs_dir = project_dir / "runs"
    if not runs_dir.exists():
        return []

    summaries = [summarize_run(path) for path in sorted(runs_dir.iterdir()) if path.is_dir()]
    summaries.sort(key=lambda item: (_sort_float(item.get("best_objective")), item["run_id"]), reverse=True)
    return summaries


def compare_runs(run_dirs: Sequence[str | Path]) -> list[dict[str, Any]]:
    return [summarize_run(run_dir) for run_dir in run_dirs]


def render_run_summary(summary: dict[str, Any]) -> str:
    lines = [
        f"run_dir={summary['run_dir']}",
        f"benchmark={summary['benchmark_name']}",
        f"backend={summary['backend_label']}",
        f"best_candidate_id={summary['best_candidate_id']}",
        f"best_objective={summary['best_objective']}",
        f"baseline_objective={summary['baseline_objective']}",
        f"improved={summary['improved']}",
        f"candidate_count={summary['candidate_count']}",
    ]
    if summary.get("duration_seconds") is not None:
        lines.append(f"duration_seconds={summary['duration_seconds']:.3f}")
    if summary.get("best_changed_files"):
        lines.append(f"best_changed_files={','.join(summary['best_changed_files'])}")
    if summary.get("best_changed_files_truncated_count"):
        lines.append(f"best_changed_files_truncated={summary['best_changed_files_truncated_count']}")
    if summary.get("best_transient_files_omitted_count"):
        lines.append(f"best_transient_files_omitted={summary['best_transient_files_omitted_count']}")
    if summary.get("best_summary"):
        lines.append(f"best_summary={summary['best_summary']}")
    return "\n".join(lines)


def render_comparison_table(summaries: Sequence[dict[str, Any]]) -> str:
    if not summaries:
        return "No runs found."

    headers = [
        "run_id",
        "benchmark",
        "backend",
        "best_objective",
        "baseline_objective",
        "improved",
        "duration_s",
    ]
    rows = []
    for summary in summaries:
        rows.append(
            [
                str(summary["run_id"]),
                str(summary["benchmark_name"]),
                str(summary["backend_label"]),
                _format_float(summary.get("best_objective")),
                _format_float(summary.get("baseline_objective")),
                "yes" if summary.get("improved") else "no",
                _format_float(summary.get("duration_seconds")),
            ]
        )

    widths = [len(header) for header in headers]
    for row in rows:
        for index, value in enumerate(row):
            widths[index] = max(widths[index], len(value))

    rendered = [
        "  ".join(header.ljust(widths[index]) for index, header in enumerate(headers)),
        "  ".join("-" * widths[index] for index in range(len(headers))),
    ]
    for row in rows:
        rendered.append("  ".join(value.ljust(widths[index]) for index, value in enumerate(row)))
    return "\n".join(rendered)


def _extract_backend_summary(run_config: dict[str, Any], proposal: dict[str, Any] | None) -> dict[str, Any]:
    proposer = str(run_config.get("proposer", "unknown"))
    metadata = proposal.get("metadata", {}) if isinstance(proposal, dict) else {}
    model = None
    if isinstance(metadata, dict):
        command = metadata.get("command", [])
        if isinstance(command, list):
            model = _extract_command_flag(command, "-m")

    use_oss = bool(metadata.get("use_oss")) if isinstance(metadata, dict) else False
    local_provider = metadata.get("local_provider") if isinstance(metadata, dict) else None
    timeout_seconds = metadata.get("timeout_seconds") if isinstance(metadata, dict) else None

    backend_label = proposer
    if use_oss and local_provider:
        backend_label = f"{proposer}:{local_provider}:{model or 'default'}"
    elif model:
        backend_label = f"{proposer}:{model}"

    return {
        "backend_label": backend_label,
        "model": model,
        "use_oss": use_oss,
        "local_provider": local_provider,
        "proposal_timeout_seconds": timeout_seconds,
    }


def _benchmark_name_from_run_config(run_config: dict[str, Any]) -> str:
    baseline = run_config.get("baseline")
    if not baseline:
        return "unknown"
    return Path(str(baseline)).resolve().parent.name


def _proposal_summary(proposal: dict[str, Any] | None) -> str | None:
    if not isinstance(proposal, dict):
        return None
    summary = proposal.get("summary")
    return str(summary) if summary is not None else None


def _load_candidate_manifests(candidates_dir: Path) -> list[dict[str, Any]]:
    manifests = []
    if not candidates_dir.exists():
        return manifests
    for candidate_dir in sorted(path for path in candidates_dir.iterdir() if path.is_dir()):
        manifest_path = candidate_dir / "manifest.json"
        if manifest_path.exists():
            manifests.append(_read_json(manifest_path))
    return manifests


def _load_first_candidate_proposal(candidates_dir: Path) -> dict[str, Any] | None:
    if not candidates_dir.exists():
        return None
    for candidate_dir in sorted(path for path in candidates_dir.iterdir() if path.is_dir() and path.name != "c0000"):
        proposal = _load_candidate_proposal(candidates_dir, candidate_dir.name)
        if proposal is not None:
            return proposal
    return None


def _load_candidate_proposal(candidates_dir: Path, candidate_id: str) -> dict[str, Any] | None:
    proposal_path = candidates_dir / candidate_id / "proposal" / "result.json"
    if not proposal_path.exists():
        return None
    return _read_json(proposal_path)


def _find_candidate(candidates: list[dict[str, Any]], candidate_id: str) -> dict[str, Any]:
    for candidate in candidates:
        if candidate.get("candidate_id") == candidate_id:
            return candidate
    return {}


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _duration_seconds(started_at: Any, completed_at: Any) -> float | None:
    if not started_at or not completed_at:
        return None
    try:
        started = datetime.fromisoformat(str(started_at))
        completed = datetime.fromisoformat(str(completed_at))
    except ValueError:
        return None
    return max(0.0, (completed - started).total_seconds())


def _extract_command_flag(command: list[Any], flag: str) -> str | None:
    for index, value in enumerate(command):
        if value == flag and index + 1 < len(command):
            return str(command[index + 1])
    return None


def _as_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _sort_float(value: Any) -> float:
    parsed = _as_float(value)
    return parsed if parsed is not None else float("-inf")


def _format_float(value: Any) -> str:
    parsed = _as_float(value)
    if parsed is None:
        return "-"
    return f"{parsed:.3f}"


def _filter_changed_files(paths: Sequence[str]) -> list[str]:
    filtered: list[str] = []
    for path in paths:
        if path.startswith(_TRANSIENT_PREFIXES):
            continue
        if path.endswith(_TRANSIENT_SUFFIXES):
            continue
        filtered.append(path)
    return filtered
