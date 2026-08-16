# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-08-16

Initial public release: Phase 1, an MCP evaluation engine.

### Added

- MCP tool discovery and normalization into Pydantic models, over a stdio
  subprocess transport abstracted behind an `MCPTransport` interface.
- A local, fully offline mock MCP server (`mock_servers/github_mock.py`)
  exposing `search_issues`, `get_repository`, `create_comment`, and
  `calculate_sum`, with configurable failure injection (timeout, exception,
  malformed response, prompt injection). No real GitHub or network calls.
- 19 deterministic benchmark cases (`benchmarks/core_suite.yaml`) covering
  correct/incorrect tool selection, valid/missing/mistyped arguments,
  hallucinated tools, timeouts, tool exceptions, malformed responses,
  prompt injection, and unapproved/approved mutating actions.
- A deterministic `BenchmarkRunner` with a runner-enforced safety gate:
  mutating tools only execute when a benchmark case explicitly grants
  `approved_mutation`, independent of what the agent itself decides.
- Eight deterministic, rule-based evaluators — no LLM judge — for tool
  selection accuracy, argument correctness, schema validity, task
  completion, error handling, timeout recovery, unsafe-action detection,
  and prompt-injection resistance. Full scoring definitions in
  [`docs/scoring.md`](docs/scoring.md).
- A pluggable `AgentAdapter` interface: a `DeterministicFakeAdapter` for
  fully offline, API-key-free CI and testing, and a documented
  `PlaceholderAdapter` stub marking the future real-model integration point.
- A JSON reliability report aggregating pass/fail counts, per-metric rates,
  average latency, and per-case evidence and failure reasons.
- A FastAPI service (`/health`, `/tools`, `/benchmarks`, `POST /runs`,
  `/runs/{id}`, `/runs/{id}/report`) with an in-memory run store behind a
  `RunRepository` interface, ready for a persistent backend later.
- Docker and Docker Compose for one-command startup, and
  `scripts/demo.sh` for a reproducible, self-cleaning end-to-end demo.
- GitHub Actions CI running lint (`ruff check`), format verification
  (`ruff format --check`), and the full test suite on every push and PR.
- 47 unit and integration tests; no network access or paid API required.

### Known limitations

- Single-step execution: the adapter decides which tool to call before
  seeing any tool output, so prompt-injection resistance is scored as
  "was the payload detected and did the pre-existing decision stay
  uncompromised," not true multi-turn resistance.
- In-memory run storage only; runs do not survive a process restart.
- `POST /runs` executes synchronously; there is no background job queue.
- No real LLM-backed adapter yet (Claude/OpenAI); `PlaceholderAdapter` is
  a documented stub for future work.
- A2A agent support is not implemented in this release; see the
  [Roadmap](README.md#roadmap).
