# Python Fixture Benchmark

This is the first real benchmark target for `metaharness`.

It is still small, but it is not a placeholder scaffold:

- `baseline/fixture_repo/` is a real Python package
- `scripts/bootstrap.sh` must create a real virtualenv
- `scripts/test.sh` must run a real `unittest` suite
- `scripts/validate.sh` must enforce concrete coding-agent instruction requirements

Run it with the fake backend:

```bash
uv run metaharness run examples/python_fixture_benchmark --backend fake --budget 1 --run-name fake-smoke
```

Run it with hosted Codex:

```bash
uv run metaharness run examples/python_fixture_benchmark --backend codex --hosted --budget 1 --run-name codex-hosted
```

Run it with local Codex over Ollama:

```bash
uv run metaharness run examples/python_fixture_benchmark --backend codex --oss --local-provider ollama --model gpt-oss:20b --proposal-timeout 180 --budget 1 --run-name codex-local
```
