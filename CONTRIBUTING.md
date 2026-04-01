# Contributing

## Setup

`metaharness` is `uv`-first.

```bash
uv sync
```

To work on the docs site too:

```bash
uv sync --group dev
```

## Development Checks

Run the compile and unit-test checks:

```bash
uv run python -m py_compile $(find src tests examples -name '*.py' | sort)
uv run python -m unittest discover -s tests -v
```

Run the fake benchmark smoke checks:

```bash
uv run metaharness run examples/python_fixture_benchmark --backend fake --budget 1 --run-name contrib-fixture
uv run metaharness run examples/python_cli_benchmark --backend fake --budget 1 --run-name contrib-cli
uv run python examples/ticket_router/run.py --backend fake --budget 1
```

## Documentation

Run the docs site locally:

```bash
uv run mkdocs serve
```

Build the docs site:

```bash
uv run mkdocs build --strict
```

## Live Provider Runs

Hosted Codex:

```bash
uv run metaharness run examples/python_fixture_benchmark --backend codex --hosted --budget 1
```

Local Codex over Ollama:

```bash
uv run metaharness run examples/python_fixture_benchmark --backend codex --oss --local-provider ollama --model gpt-oss:20b --proposal-timeout 240 --budget 1
```

## Notes

- keep benchmark tasks deterministic
- prefer improving real benchmarks over adding more scaffolding
- do not commit transient run outputs under `examples/*/runs/`
