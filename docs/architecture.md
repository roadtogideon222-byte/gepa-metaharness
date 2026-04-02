# Architecture

## Core Idea

`metaharness` optimizes executable harnesses by keeping the outer loop simple and making the filesystem the source of truth.

Each run:

1. materializes a baseline candidate
2. asks a proposer backend to mutate the workspace
3. validates the result
4. evaluates the result
5. stores everything on disk

## Main Components

### Optimization Engine

The engine coordinates the loop and picks the best candidate based on the objective score.

Key file:

- `src/metaharness/core/engine.py`

### Run Store

The filesystem run store creates candidate workspaces, captures a compact environment bootstrap, enforces any configured write-scope allowlist, writes manifests, stores proposal output, and records diffs.

Key file:

- `src/metaharness/store/filesystem.py`

### Proposer Backends

A proposer backend is the system that edits the candidate workspace.

Current backends:

- `CodexExecBackend`
- `FakeBackend`
- `GeminiCliBackend` scaffold

Key files:

- `src/metaharness/proposer/codex_exec.py`
- `src/metaharness/proposer/fake.py`
- `src/metaharness/proposer/gemini_cli.py`

### Coding Tool Integration

This integration turns coding-agent instruction files and helper scripts into an optimization target with deterministic task scoring.

Key files:

- `src/metaharness/integrations/coding_tool/config.py`
- `src/metaharness/integrations/coding_tool/runtime.py`

## Run Layout

Every run is stored on disk.

Typical shape:

```text
runs/<run_id>/
  run_config.json
  indexes/
    leaderboard.json
  candidates/
    c0000/
      manifest.json
      workspace/
      validation/result.json
      evaluation/result.json
    c0001/
      manifest.json
      workspace/
        .metaharness/
          AGENTS.md
          bootstrap/
            summary.md
            snapshot.json
          experience/
      proposal/
        prompt.txt
        result.json
        events.json
        workspace.diff
        workspace_changes.json
      validation/result.json
      evaluation/result.json
```

Each candidate manifest records whether the proposal was applied, whether validation passed, the objective score, and the explicit candidate outcome.

## Why Filesystem First Matters

This design makes the system useful for real engineering work:

- proposals are concrete file edits
- failures are inspectable after the run
- diffs can be reviewed by humans
- environment facts are captured before the agent starts editing
- candidate outcomes such as `keep`, `discard`, `crash`, `timeout`, `no-change`, and `scope-violation` are recorded explicitly
- evaluation artifacts are easy to archive
- the optimization history can be re-used by future iterations
- reporting can export both run comparisons and per-candidate ledgers as TSV or JSON
- experiment matrices can aggregate repeated trials across benchmarks, backends, budgets, and models

## How A Coding Tool Project Is Evaluated

The coding-tool integration uses two types of tasks:

- `file_phrase` checks
- `command` checks

This lets you score both instruction quality and executable workflow behavior.

Examples:

- require specific repository safety guidance in `AGENTS.md`
- require context handoff guidance in `GEMINI.md`
- require `scripts/bootstrap.sh` to build a working environment
- require `scripts/test.sh` to pass a deterministic test suite

Projects can also set `allowed_write_paths` in `metaharness.json` so only specific files or directories are mutable during optimization.

## What The Current OSS Version Focuses On

The current package is strongest when the target under optimization is:

- instruction files
- helper scripts
- benchmark harness code
- routing or workflow glue code

It is not trying to be a full paper reproduction of every benchmark domain yet.
It is trying to be a practical and reusable outer-loop harness optimization library.
