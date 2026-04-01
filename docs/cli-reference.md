# CLI Reference

## Overview

The `metaharness` CLI is the main entry point for project scaffolding, optimization runs, smoke checks, and reporting.

Show help:

```bash
uv run metaharness --help
```

## `scaffold`

Create a new coding-tool project:

```bash
uv run metaharness scaffold coding-tool ./my-coding-tool-optimizer
```

Profiles:

- `standard`
- `local-oss-smoke`
- `local-oss-medium`

Examples:

```bash
uv run metaharness scaffold coding-tool ./my-local-oss-smoke --profile local-oss-smoke
uv run metaharness scaffold coding-tool ./my-local-oss-medium --profile local-oss-medium
```

## `run`

Run an optimization project:

```bash
uv run metaharness run ./my-coding-tool-optimizer --backend fake --budget 1
```

Hosted Codex:

```bash
uv run metaharness run ./my-coding-tool-optimizer --backend codex --hosted --budget 1
```

Local Ollama:

```bash
uv run metaharness run ./my-coding-tool-optimizer --backend codex --oss --local-provider ollama --model gpt-oss:20b --proposal-timeout 240 --budget 1
```

Useful options:

- `--backend`
- `--budget`
- `--run-name`
- `--hosted`
- `--oss`
- `--local-provider`
- `--model`
- `--proposal-timeout`

## `smoke codex`

Probe the environment before a real run:

```bash
uv run metaharness smoke codex ./my-coding-tool-optimizer --probe-only
```

Probe the local Ollama path:

```bash
uv run metaharness smoke codex ./my-coding-tool-optimizer --probe-only --oss --local-provider ollama --model gpt-oss:20b
```

## `inspect`

Inspect one completed run:

```bash
uv run metaharness inspect ./examples/python_fixture_benchmark/runs/hosted-codex-20260401
```

## `summarize`

Summarize all runs in a project:

```bash
uv run metaharness summarize ./examples/python_fixture_benchmark
```

## `compare`

Compare specific run directories:

```bash
uv run metaharness compare \
  ./examples/python_fixture_benchmark/runs/hosted-codex-20260401 \
  ./examples/python_fixture_benchmark/runs/ollama-20b-20260401 \
  ./examples/python_fixture_benchmark/runs/ollama-120b-20260401
```

## Output Files To Know

The most useful stored artifacts are usually:

- `run_config.json`
- `indexes/leaderboard.json`
- `proposal/result.json`
- `proposal/workspace.diff`
- `validation/result.json`
- `evaluation/result.json`
