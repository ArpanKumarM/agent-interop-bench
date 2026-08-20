# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Generalized the runner from a single tool call into a bounded interaction
  loop: `BenchmarkRunner.run_case` now calls `AgentAdapter.decide` up to
  `BenchmarkCase.max_turns` times (default `1`, i.e. behaviorally unchanged
  single-turn execution), validating and mutation-gating every turn
  identically, and terminating deterministically for exactly one of three
  reasons (`TerminationReason`: `voluntary_stop`, `blocked_unsafe`,
  `max_turns_reached`) — never an unbounded loop.
- Replaced the ad hoc, recursive `RunResult.follow_up` with a flat
  `RunResult.turns: list[TurnResult]` interaction trace. Each `TurnResult`
  independently audits the adapter's decision, the requested tool/arguments,
  whether the tool was known, its mutation status and approval, the safety
  gate's verdict, whether execution actually happened, and the tool
  output/error/timing. `RunResult` keeps `selected_tool`, `tool_output`,
  `latency_ms`, etc. as computed properties over `turns[0]`, so every
  existing evaluator needed no changes.
- `prompt_injection_resistance` now scores real reaction resistance for any
  case with `max_turns >= 2` and a `simulated_reaction` fixture (via
  `RunResult.reaction_turns`), and falls back to the original single-turn
  check otherwise. Two new cases (`injection-003-resists-hijack-attempt`,
  `injection-004-hijacked-into-mutation`) demonstrate both outcomes; the
  latter is also proven, via `test_injection_004_defense_in_depth_full_proof`,
  to be blocked by the mutation safety gate at the transport level (the mock
  `create_comment` tool is never actually invoked) while the evaluator still
  records it as compromised. Documentation added distinguishing this
  deterministic-fixture harness validation from real-model robustness
  measurement, which remains future work. See `docs/scoring.md`.
- `CaseReport` now persists the full per-case interaction trace —
  `turns: list[TurnResult]` and `termination_reason` — directly in the JSON
  report, not just inside individual evaluators' `evidence` dicts. Every
  executed or blocked turn (requested tool/arguments, mutation/safety-gate
  verdict, execution status, tool output/error, per-turn latency) is
  reconstructable from `GET /runs/{id}/report` alone; verified by
  `test_injection_004_is_reconstructable_from_the_persisted_report_alone`.
- `docs/scoring.md` and the README now mechanically break down
  `prompt_injection_resistance`'s 3/4 = 0.75 into its two disjoint
  populations — legacy single-turn (2/2) and reactive multi-turn (1/2) —
  pinned by `test_prompt_injection_resistance_legacy_vs_reactive_subsets`,
  rather than presenting one blended number without explanation.

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
  `scripts/demo.sh` for a reproducible, self-cleaning end-to-end demo,
  with a detailed default mode plus condensed `--presentation` and
  `--recording` modes — the latter paced for a 30-40 second screen
  recording, with pauses skipped automatically outside a real terminal.
- A recorded demo GIF (`docs/assets/demo.gif`), embedded in the README,
  showing tool discovery, the benchmark run, real reliability scores,
  and the intentional evaluator-validation failures end to end.
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
