<div class="hero">
  <p class="hero-kicker">Filesystem first harness optimization</p>
  <h1>metaharness</h1>
  <p>
    <code>metaharness</code> is an open source Python library for optimizing executable harnesses around agentic coding systems.
    It treats the harness itself as the thing under optimization.
    That includes instruction files, bootstrap scripts, validation scripts, test flows, routing logic, and other executable support code.
  </p>
  <div class="hero-actions">
    <a class="md-button md-button--primary" href="getting-started/">Get Started</a>
    <a class="md-button" href="experiments/">View Experiments</a>
  </div>
</div>

<div class="stat-grid">
  <div class="stat-card">
    <strong>2 real benchmarks</strong>
    Small but real coding-tool targets built around executable scripts and fixture repos.
  </div>
  <div class="stat-card">
    <strong>Hosted and local providers</strong>
    Hosted Codex and local Codex over Ollama have both been exercised in real runs.
  </div>
  <div class="stat-card">
    <strong>Filesystem run artifacts</strong>
    Every run stores prompts, results, diffs, evaluation output, and candidate manifests on disk.
  </div>
</div>

## What This Project Is

`metaharness` is a framework for improving the code and files around an agentic system by running an outer optimization loop:

1. start from a baseline harness
2. ask a coding agent to improve it
3. validate and evaluate the result
4. keep the best candidate
5. repeat within a fixed budget

The important point is that the optimized object is executable and inspectable.
It is not limited to prompt strings.

## Who This Is For

`metaharness` is for two groups:

- developers building agentic coding systems who want to optimize harness code, workflow scripts, retrieval wrappers, or evaluation contracts
- practitioners using coding-agent tools who want to tune `AGENTS.md`, `GEMINI.md`, bootstrap flows, safety instructions, and acceptance tests

## Why Use It

Most agent workflows fail because of the harness around the model, not just the model call.
Typical failure points include:

- weak repository instructions
- missing setup scripts
- broken validation flows
- poor context handoff between iterations
- acceptance tests that are too vague or too brittle

`metaharness` helps by turning those artifacts into a repeatable optimization target with stored evidence.

## What You Get

- a minimal optimization engine
- a filesystem-backed run store
- a provider-neutral proposer backend interface
- a real `CodexExecBackend`
- a `FakeBackend` for deterministic tests and smoke runs
- a coding-tool integration for optimizing instruction files and scripts
- benchmark targets and experiment tracking
- CLI commands for `run`, `smoke`, `inspect`, `summarize`, and `compare`

## Current Benchmarks

- `examples/python_fixture_benchmark`
- `examples/python_cli_benchmark`
- `examples/ticket_router`

The two Python benchmarks are the main OSS examples today.
They use real shell scripts and real fixture repositories, not placeholder text-only checks.

## Experiment Snapshot

As of April 1, 2026:

- hosted Codex solved both real benchmarks in one proposal iteration
- local `gpt-oss:120b` over Ollama solved `python_fixture_benchmark`
- local `gpt-oss:20b` timed out on both real benchmark runs at the configured `240s`

See [Experiments](experiments.md) for the full tables and notes.

## Next Steps

- [Getting Started](getting-started.md)
- [Architecture](architecture.md)
- [Providers](providers.md)
- [Benchmarks](benchmarks.md)
- [CLI Reference](cli-reference.md)
