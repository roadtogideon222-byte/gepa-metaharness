# Ticket Router Example

This example gives `metaharness` a small deterministic harness to optimize.

The candidate workspace contains a Python ticket router. The evaluator scores it
against a fixed labeled dataset of support tickets.

## Run With Fake Backend

```bash
uv run python examples/ticket_router/run.py --backend fake --budget 1
```

## Run With Codex

Requires a working `codex` installation and authentication.

```bash
uv run python examples/ticket_router/run.py --backend codex --budget 2
```

Run artifacts are written under `examples/ticket_router/runs/`.
