# metaharness

`metaharness` is an open source Python library for optimizing executable harnesses around agentic coding systems.

It is built for two audiences:

- developers building agentic coding systems who want to improve harness code, workflow scripts, routing logic, or evaluation flows
- practitioners using coding-agent tools who want to improve `AGENTS.md`, `GEMINI.md`, setup scripts, validation scripts, and acceptance tests

The core idea is simple:

1. start from a baseline harness
2. let a coding agent propose changes
3. validate and evaluate the result
4. keep the best candidate
5. store all artifacts on disk

This makes the optimization process inspectable, reproducible, and usable in real engineering workflows.

## Why This Project Exists

Most real failures in agent workflows are not just model failures.
They come from the harness around the model:

- weak repository instructions
- missing setup steps
- brittle validation scripts
- poor context handoff between iterations
- acceptance tests that do not match the real task

`metaharness` turns those harness artifacts into an optimization target.

## What You Can Optimize

`metaharness` is useful when the thing under optimization is executable and file-based, such as:

- `AGENTS.md`
- `GEMINI.md`
- bootstrap scripts
- validation scripts
- test scripts
- routing or workflow glue code
- benchmark harness logic

## What You Get

- a minimal optimization engine
- a filesystem-backed run store
- a provider-neutral proposer backend interface
- a real `CodexExecBackend`
- a deterministic `FakeBackend`
- a coding-tool integration for instruction files and script-based harnesses
- benchmark targets and experiment reports
- CLI commands for `scaffold`, `run`, `smoke`, `inspect`, `summarize`, and `compare`

## Current Status

This repository now includes:

- two real coding-tool benchmark targets
- a smaller deterministic ticket-router example
- hosted Codex runs on the real benchmarks
- local Codex over Ollama runs with `gpt-oss:20b` and `gpt-oss:120b`
- reporting that highlights actual harness edits instead of transient `.venv` churn

As of April 1, 2026:

- hosted Codex solved both real benchmarks in one proposal iteration
- local `gpt-oss:120b` solved `python_fixture_benchmark`
- local `gpt-oss:20b` timed out on both real benchmark runs at the configured `240s`

Detailed experiment records are in:

- [BENCHMARK_RESULTS.md](BENCHMARK_RESULTS.md)
- [docs/experiments.md](docs/experiments.md)

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

Alternative editable install:

```bash
pip install -e .
```

## Quick Start

Run the fake backend on a real benchmark:

```bash
uv run metaharness run examples/python_fixture_benchmark --backend fake --budget 1 --run-name quickstart
```

Inspect the result:

```bash
uv run metaharness inspect examples/python_fixture_benchmark/runs/quickstart
```

Summarize all runs for that benchmark:

```bash
uv run metaharness summarize examples/python_fixture_benchmark
```

## Use Hosted Codex

Requirements:

- `codex` CLI installed
- authenticated Codex session or API key
- network access

Run a real benchmark:

```bash
uv run metaharness run examples/python_fixture_benchmark --backend codex --hosted --budget 1 --run-name hosted-codex
```

Important:

- use `--hosted` when a benchmark config defaults to local Ollama
- there is no product blocker in `metaharness` for hosted Codex now

## Use Local Codex Over Ollama

Probe the local setup:

```bash
uv run metaharness smoke codex examples/python_fixture_benchmark --probe-only --oss --local-provider ollama --model gpt-oss:20b
```

Run with `gpt-oss:20b`:

```bash
uv run metaharness run examples/python_fixture_benchmark --backend codex --oss --local-provider ollama --model gpt-oss:20b --proposal-timeout 240 --budget 1 --run-name ollama-20b
```

Run with `gpt-oss:120b`:

```bash
uv run metaharness run examples/python_fixture_benchmark --backend codex --oss --local-provider ollama --model gpt-oss:120b --proposal-timeout 420 --budget 1 --run-name ollama-120b
```

## Benchmarks And Examples

### Real Benchmarks

- [examples/python_fixture_benchmark](examples/python_fixture_benchmark)
- [examples/python_cli_benchmark](examples/python_cli_benchmark)

These are small, real, and executable.
They use:

- real fixture repositories
- real shell scripts
- deterministic task scoring
- instruction-file checks
- stored run artifacts

### Deterministic Example

- [examples/ticket_router](examples/ticket_router)

Run it:

```bash
uv run python examples/ticket_router/run.py --backend fake --budget 1
```

## Create Your Own Project

Scaffold a coding-tool project:

```bash
uv run metaharness scaffold coding-tool ./my-coding-tool-optimizer
```

Useful scaffold profiles:

- `standard`
- `local-oss-smoke`
- `local-oss-medium`

Run the scaffold with the fake backend:

```bash
uv run metaharness run ./my-coding-tool-optimizer --backend fake --budget 1
```

## CLI Commands

Create a scaffold:

```bash
uv run metaharness scaffold coding-tool ./my-project
```

Run a project:

```bash
uv run metaharness run ./my-project --backend fake --budget 1
```

Probe Codex:

```bash
uv run metaharness smoke codex ./my-project --probe-only
```

Inspect one run:

```bash
uv run metaharness inspect ./my-project/runs/example
```

Summarize project runs:

```bash
uv run metaharness summarize ./examples/python_fixture_benchmark
```

Compare specific runs:

```bash
uv run metaharness compare \
  ./examples/python_fixture_benchmark/runs/hosted-codex-20260401 \
  ./examples/python_fixture_benchmark/runs/ollama-20b-20260401 \
  ./examples/python_fixture_benchmark/runs/ollama-120b-20260401
```

## Why Filesystem First Matters

`metaharness` stores every important artifact on disk:

- prompts
- candidate workspaces
- validation output
- evaluation output
- proposal metadata
- workspace diffs
- per-candidate manifests

That makes the optimization history reviewable and reusable.

## Documentation

Project docs:

- [docs/index.md](docs/index.md)
- [docs/getting-started.md](docs/getting-started.md)
- [docs/architecture.md](docs/architecture.md)
- [docs/providers.md](docs/providers.md)
- [docs/benchmarks.md](docs/benchmarks.md)
- [docs/cli-reference.md](docs/cli-reference.md)
- [docs/experiments.md](docs/experiments.md)

Docs site commands:

```bash
uv sync --group dev
uv run mkdocs serve
uv run mkdocs build --strict
```

## Development Checks

Compile:

```bash
uv run python -m py_compile $(find src tests examples -name '*.py' | sort)
```

Unit tests:

```bash
uv run python -m unittest discover -s tests -v
```

Fake benchmark smoke runs:

```bash
uv run metaharness run examples/python_fixture_benchmark --backend fake --budget 1 --run-name ci-fixture-local
uv run metaharness run examples/python_cli_benchmark --backend fake --budget 1 --run-name ci-cli-local
uv run python examples/ticket_router/run.py --backend fake --budget 1
```

## License

MIT. See [LICENSE](LICENSE).
