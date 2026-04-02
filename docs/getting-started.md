# Getting Started

## Prerequisites

- Python 3.11 or newer
- [`uv`](https://docs.astral.sh/uv/)
- optional: `codex` CLI for live runs
- optional: Ollama with `gpt-oss:20b` or `gpt-oss:120b` for local runs

## Install

Project setup:

```bash
uv sync
```

If you want to build the docs site too:

```bash
uv sync --group dev
```

Check the CLI:

```bash
uv run metaharness --help
```

## First Run

The fastest useful first run is the fake backend on a real benchmark:

```bash
uv run metaharness run examples/python_fixture_benchmark --backend fake --budget 1 --run-name first-run
```

Expected result:

- a run directory under `examples/python_fixture_benchmark/runs/first-run`
- `best_candidate_id=c0001`
- `best_objective=1.000`

## Understand The Output

Inspect a run:

```bash
uv run metaharness inspect examples/python_fixture_benchmark/runs/first-run
```

Summarize all runs for a project:

```bash
uv run metaharness summarize examples/python_fixture_benchmark
```

Export the candidate ledger for one run:

```bash
uv run metaharness ledger examples/python_fixture_benchmark/runs/first-run --tsv
```

Compare specific runs:

```bash
uv run metaharness compare \
  examples/python_fixture_benchmark/runs/hosted-codex-20260401 \
  examples/python_fixture_benchmark/runs/ollama-20b-20260401 \
  examples/python_fixture_benchmark/runs/ollama-120b-20260401
```

Run a saved experiment matrix:

```bash
uv run metaharness experiment --config examples/experiment_configs/fake-benchmarks.json
```

## Use Hosted Codex

Requirements:

- `codex` CLI installed
- authenticated Codex session or API key setup
- outbound network access

Run a real benchmark with hosted Codex:

```bash
uv run metaharness run examples/python_fixture_benchmark --backend codex --hosted --budget 1 --run-name hosted-codex
```

Important:

- use `--hosted` if a project config defaults to local Ollama
- hosted Codex is the strongest current path for real benchmark runs in this repository

## Use Local Codex Over Ollama

Requirements:

- Ollama server reachable on `127.0.0.1:11434`
- a local model such as `gpt-oss:20b` or `gpt-oss:120b`

Probe the local path first:

```bash
uv run metaharness smoke codex examples/python_fixture_benchmark --probe-only --oss --local-provider ollama --model gpt-oss:20b
```

Run a real benchmark:

```bash
uv run metaharness run examples/python_fixture_benchmark --backend codex --oss --local-provider ollama --model gpt-oss:20b --proposal-timeout 240 --budget 1 --run-name ollama-20b
```

For the larger model:

```bash
uv run metaharness run examples/python_fixture_benchmark --backend codex --oss --local-provider ollama --model gpt-oss:120b --proposal-timeout 420 --budget 1 --run-name ollama-120b
```

## Create Your Own Project

Scaffold a coding-tool project:

```bash
uv run metaharness scaffold coding-tool ./my-coding-tool-optimizer
```

Faster local profile:

```bash
uv run metaharness scaffold coding-tool ./my-local-oss-smoke --profile local-oss-smoke
```

Medium local profile:

```bash
uv run metaharness scaffold coding-tool ./my-local-oss-medium --profile local-oss-medium
```

If you want a checked-in experiment workflow for your own project, add a small JSON spec and run it with:

```bash
uv run metaharness experiment --config ./my-experiment.json
```

## Build The Docs

Serve locally:

```bash
uv run mkdocs serve
```

Build the site:

```bash
uv run mkdocs build --strict
```
