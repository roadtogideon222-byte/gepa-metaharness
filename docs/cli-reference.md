# CLI Reference

## Overview

The `metaharness` CLI is the main entry point for project scaffolding, optimization runs, smoke checks, and reporting.

Show help:

```bash
uv run metaharness --help
```

Many reporting commands support:

- plain text output by default
- `--json` for machine-readable output
- `--tsv` for spreadsheet-friendly export where supported

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

## `experiment`

Run a benchmark x backend x budget x trial matrix:

```bash
uv run metaharness experiment ./examples/python_fixture_benchmark --backend fake --trials 3
```

Run from a saved config file:

```bash
uv run metaharness experiment --config ./examples/experiment_configs/fake-benchmarks.json
```

Multiple budgets:

```bash
uv run metaharness experiment ./examples/python_fixture_benchmark --backend fake --budget 1 --budget 2 --trials 2
```

TSV export of the aggregate results:

```bash
uv run metaharness experiment ./examples/python_fixture_benchmark --backend fake --trials 3 --tsv
```

This command writes:

- `experiment.json`
- `trials.json`
- `aggregates.json`
- `trials.tsv`
- `aggregates.tsv`

You can keep the matrix definition in a JSON config file with fields such as:

- `project_dirs`
- `backends`
- `budgets`
- `trial_count`
- `models`
- `results_dir`
- `backend_overrides`

If a config file is provided, relative paths are resolved from the config file location.
CLI flags override the corresponding config values.

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

This is the best quick look at candidate outcomes, validity, proposal application, and any scope violations.

## `ledger`

Export the per-candidate ledger for one run:

```bash
uv run metaharness ledger ./examples/python_fixture_benchmark/runs/hosted-codex-20260401
```

TSV export:

```bash
uv run metaharness ledger ./examples/python_fixture_benchmark/runs/hosted-codex-20260401 --tsv
```

## `summarize`

Summarize all runs in a project:

```bash
uv run metaharness summarize ./examples/python_fixture_benchmark
```

TSV export:

```bash
uv run metaharness summarize ./examples/python_fixture_benchmark --tsv
```

## `compare`

Compare specific run directories:

```bash
uv run metaharness compare \
  ./examples/python_fixture_benchmark/runs/hosted-codex-20260401 \
  ./examples/python_fixture_benchmark/runs/ollama-20b-20260401 \
  ./examples/python_fixture_benchmark/runs/ollama-120b-20260401
```

TSV export:

```bash
uv run metaharness compare \
  ./examples/python_fixture_benchmark/runs/hosted-codex-20260401 \
  ./examples/python_fixture_benchmark/runs/ollama-120b-20260401 \
  --tsv
```

## Output Files To Know

The most useful stored artifacts are usually:

- `run_config.json`
- `indexes/leaderboard.json`
- `manifest.json`
- `proposal/result.json`
- `proposal/workspace.diff`
- `validation/result.json`
- `evaluation/result.json`
