# Python CLI Benchmark

This is the second real benchmark target for `metaharness`.

It is built around a real Python CLI fixture package and a real deterministic acceptance flow:

- `baseline/fixture_repo/` contains a real Python package with unit tests
- `scripts/bootstrap.sh` must create a real virtualenv
- `scripts/test.sh` must run the fixture unit tests and a CLI smoke command
- `scripts/validate.sh` must enforce concrete coding-agent instruction requirements

Run it with the fake backend:

```bash
uv run metaharness run examples/python_cli_benchmark --backend fake --budget 1 --run-name fake-smoke
```

Run it with hosted Codex:

```bash
uv run metaharness run examples/python_cli_benchmark --backend codex --hosted --budget 1 --run-name codex-hosted
```

Run it with local Codex over Ollama:

```bash
uv run metaharness run examples/python_cli_benchmark --backend codex --oss --local-provider ollama --model gpt-oss:20b --proposal-timeout 240 --budget 1 --run-name codex-local
```
