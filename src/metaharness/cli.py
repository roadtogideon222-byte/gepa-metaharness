from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .integrations.coding_tool.config import load_coding_tool_project
from .integrations.coding_tool.runtime import resolve_backend_options, run_coding_tool_project
from .proposer.codex_exec import probe_codex_cli, probe_ollama_server
from .reporting import compare_runs, render_comparison_table, render_run_summary, summarize_project_runs, summarize_run
from .scaffold import create_coding_tool_scaffold


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="metaharness")
    subparsers = parser.add_subparsers(dest="command", required=True)

    scaffold_parser = subparsers.add_parser("scaffold", help="Create a starter project scaffold.")
    scaffold_parser.add_argument("template", choices=["coding-tool"])
    scaffold_parser.add_argument("target_dir")
    scaffold_parser.add_argument(
        "--profile",
        choices=["standard", "local-oss-smoke", "local-oss-medium"],
        default="standard",
    )

    run_parser = subparsers.add_parser("run", help="Run an optimization project.")
    run_parser.add_argument("project_dir")
    run_parser.add_argument("--backend", choices=["fake", "codex", "gemini"], default="fake")
    run_parser.add_argument("--budget", type=int, default=None)
    run_parser.add_argument("--run-name", default=None)
    run_parser.add_argument("--hosted", action="store_true")
    run_parser.add_argument("--oss", action="store_true")
    run_parser.add_argument("--local-provider", choices=["ollama", "lmstudio"], default=None)
    run_parser.add_argument("--model", default=None)
    run_parser.add_argument("--proposal-timeout", type=float, default=None)

    smoke_parser = subparsers.add_parser("smoke", help="Run a backend smoke check.")
    smoke_subparsers = smoke_parser.add_subparsers(dest="smoke_backend", required=True)

    smoke_codex_parser = smoke_subparsers.add_parser("codex", help="Probe and optionally run Codex.")
    smoke_codex_parser.add_argument("project_dir")
    smoke_codex_parser.add_argument("--probe-only", action="store_true")
    smoke_codex_parser.add_argument("--budget", type=int, default=1)
    smoke_codex_parser.add_argument("--run-name", default="codex-smoke")
    smoke_codex_parser.add_argument("--hosted", action="store_true")
    smoke_codex_parser.add_argument("--oss", action="store_true")
    smoke_codex_parser.add_argument("--local-provider", choices=["ollama", "lmstudio"], default=None)
    smoke_codex_parser.add_argument("--model", default=None)
    smoke_codex_parser.add_argument("--proposal-timeout", type=float, default=None)

    inspect_parser = subparsers.add_parser("inspect", help="Inspect a run directory.")
    inspect_parser.add_argument("run_dir")
    inspect_parser.add_argument("--json", action="store_true", dest="json_output")

    summarize_parser = subparsers.add_parser("summarize", help="Summarize all runs in a project.")
    summarize_parser.add_argument("project_dir")
    summarize_parser.add_argument("--json", action="store_true", dest="json_output")

    compare_parser = subparsers.add_parser("compare", help="Compare one or more run directories.")
    compare_parser.add_argument("run_dirs", nargs="+")
    compare_parser.add_argument("--json", action="store_true", dest="json_output")

    args = parser.parse_args(argv)

    if args.command == "scaffold":
        return _cmd_scaffold(args.template, Path(args.target_dir), args.profile)
    if args.command == "run":
        return _cmd_run(
            project_dir=Path(args.project_dir),
            backend=args.backend,
            budget=args.budget,
            run_name=args.run_name,
            backend_overrides=_backend_overrides_from_args(args),
        )
    if args.command == "smoke":
        if args.smoke_backend == "codex":
            return _cmd_smoke_codex(
                project_dir=Path(args.project_dir),
                probe_only=args.probe_only,
                budget=args.budget,
                run_name=args.run_name,
                backend_overrides=_backend_overrides_from_args(args),
            )
    if args.command == "inspect":
        return _cmd_inspect(Path(args.run_dir), args.json_output)
    if args.command == "summarize":
        return _cmd_summarize(Path(args.project_dir), args.json_output)
    if args.command == "compare":
        return _cmd_compare([Path(value) for value in args.run_dirs], args.json_output)
    raise RuntimeError(f"unknown command: {args.command}")


def _cmd_scaffold(template: str, target_dir: Path, profile: str) -> int:
    if template != "coding-tool":
        raise ValueError(f"unsupported template: {template}")
    written = create_coding_tool_scaffold(target_dir, profile=profile)
    print(f"Created coding-tool scaffold in {target_dir}")
    print(f"profile={profile}")
    print(f"Wrote {len(written)} files")
    return 0


def _cmd_run(
    project_dir: Path,
    backend: str,
    budget: int | None,
    run_name: str | None,
    backend_overrides: dict[str, Any] | None,
) -> int:
    project = _load_project(project_dir)
    result = run_coding_tool_project(
        project=project,
        backend_name=backend,
        budget=budget,
        run_name=run_name,
        backend_overrides=backend_overrides,
    )
    print(f"run_dir={result.run_dir}")
    print(f"best_candidate_id={result.best_candidate_id}")
    print(f"best_objective={result.best_objective:.3f}")
    print(f"best_workspace_dir={result.best_workspace_dir}")
    return 0


def _cmd_smoke_codex(
    project_dir: Path,
    probe_only: bool,
    budget: int,
    run_name: str,
    backend_overrides: dict[str, Any] | None,
) -> int:
    project = _load_project(project_dir)
    resolved_options = resolve_backend_options("codex", project, overrides=backend_overrides)
    probe = probe_codex_cli()
    if not probe["ok"]:
        error = probe.get("error") or "Codex probe failed."
        raise SystemExit(f"Codex unavailable: {error}")

    print(f"codex_binary={probe['resolved_binary']}")
    print(f"codex_version={probe['version'] or 'unknown'}")
    if probe.get("raw_output"):
        print(f"codex_probe_output={probe['raw_output']}")

    use_oss = bool(resolved_options.get("use_oss", False) or resolved_options.get("local_provider"))
    local_provider = resolved_options.get("local_provider")
    model = resolved_options.get("model")
    if use_oss:
        print(f"codex_oss=true")
    if local_provider:
        print(f"codex_local_provider={local_provider}")
    if model:
        print(f"codex_model={model}")
    if resolved_options.get("proposal_timeout_seconds") is not None:
        print(f"codex_proposal_timeout={resolved_options['proposal_timeout_seconds']}")

    if use_oss and local_provider == "ollama":
        ollama_probe = probe_ollama_server()
        if not ollama_probe["ok"]:
            raise SystemExit(f"Ollama unavailable: {ollama_probe['error']}")
        print(f"ollama_base_url={ollama_probe['base_url']}")
        print(f"ollama_version={ollama_probe['version'] or 'unknown'}")
        print(f"ollama_models={','.join(ollama_probe['models'])}")
        if model and model not in ollama_probe["models"]:
            raise SystemExit(f"Configured model not found in Ollama: {model}")

    if probe_only:
        return 0

    result = run_coding_tool_project(
        project=project,
        backend_name="codex",
        budget=budget,
        run_name=run_name,
        backend_overrides=backend_overrides,
    )
    print(f"run_dir={result.run_dir}")
    print(f"best_candidate_id={result.best_candidate_id}")
    print(f"best_objective={result.best_objective:.3f}")
    print(f"best_workspace_dir={result.best_workspace_dir}")
    return 0


def _cmd_inspect(run_dir: Path, json_output: bool) -> int:
    data = inspect_run(run_dir)
    if json_output:
        print(json.dumps(data, indent=2, sort_keys=True))
        return 0

    print(f"run_dir={data['run_dir']}")
    print(f"run_id={data['run_id']}")
    print(f"best_candidate_id={data['best_candidate_id']}")
    print(f"best_objective={data['best_objective']}")
    print("candidates:")
    for candidate in data["candidates"]:
        print(
            f"  {candidate['candidate_id']}: objective={candidate['objective']} "
            f"valid={candidate['valid']} proposal_applied={candidate['proposal_applied']}"
        )
    return 0


def _cmd_summarize(project_dir: Path, json_output: bool) -> int:
    data = summarize_project_runs(project_dir)
    if json_output:
        print(json.dumps(data, indent=2, sort_keys=True))
        return 0

    print(render_comparison_table(data))
    return 0


def _cmd_compare(run_dirs: list[Path], json_output: bool) -> int:
    data = compare_runs(run_dirs)
    if json_output:
        print(json.dumps(data, indent=2, sort_keys=True))
        return 0

    print(render_comparison_table(data))
    print()
    for summary in data:
        print(render_run_summary(summary))
        print()
    return 0


def inspect_run(run_dir: Path) -> dict[str, Any]:
    run_dir = run_dir.resolve()
    leaderboard = _read_json(run_dir / "indexes" / "leaderboard.json")
    candidates_dir = run_dir / "candidates"
    candidates = []
    if candidates_dir.exists():
        for candidate_dir in sorted(path for path in candidates_dir.iterdir() if path.is_dir()):
            manifest_path = candidate_dir / "manifest.json"
            if not manifest_path.exists():
                continue
            manifest = _read_json(manifest_path)
            candidates.append(manifest)

    candidates.sort(
        key=lambda item: (
            float(item["objective"]) if item.get("objective") is not None else float("-inf"),
            item["candidate_id"],
        ),
        reverse=True,
    )
    return {
        "run_dir": str(run_dir),
        "run_id": run_dir.name,
        "best_candidate_id": leaderboard.get("best_candidate_id"),
        "best_objective": leaderboard.get("best_objective"),
        "candidates": candidates,
    }


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_project(project_dir: Path):
    try:
        return load_coding_tool_project(project_dir)
    except FileNotFoundError as exc:
        missing = exc.filename or str(project_dir / "metaharness.json")
        raise SystemExit(f"Missing project file: {missing}") from exc


def _backend_overrides_from_args(args: argparse.Namespace) -> dict[str, Any] | None:
    if getattr(args, "hosted", False) and getattr(args, "oss", False):
        raise SystemExit("--hosted cannot be combined with --oss")

    if getattr(args, "hosted", False):
        overrides = {
            "use_oss": False,
            "local_provider": "",
            "model": getattr(args, "model", None) if getattr(args, "model", None) is not None else "",
            "proposal_timeout_seconds": getattr(args, "proposal_timeout", None),
        }
        return overrides

    overrides = {
        "use_oss": getattr(args, "oss", None) or None,
        "local_provider": getattr(args, "local_provider", None),
        "model": getattr(args, "model", None),
        "proposal_timeout_seconds": getattr(args, "proposal_timeout", None),
    }
    filtered = {key: value for key, value in overrides.items() if value is not None}
    return filtered or None


if __name__ == "__main__":
    raise SystemExit(main())
