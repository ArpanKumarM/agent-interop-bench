# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed (breaking API change)

- **`POST /runs` is now asynchronous.** Previously it blocked until the full
  benchmark suite finished and returned `200` with a completed run summary.
  It now returns immediately with `202 Accepted`, a `Location: /runs/{run_id}`
  header, and a `{"run_id": ..., "status": "queued"}` body; the suite
  executes in the background. Poll `GET /runs/{run_id}` for lifecycle status
  (`queued` -> `running` -> `completed`/`failed`) and `GET /runs/{run_id}/report`
  once `status == "completed"`. `GET /runs/{run_id}/report` now returns `409`
  for `queued`/`running`/`failed` runs (with structured detail identifying
  which), not just for "not yet completed" as before; a `failed` run's
  report is never fabricated — its error is only discoverable via
  `GET /runs/{run_id}`. Existing `GET /runs/{run_id}` and unknown-run `404`
  behavior are unchanged. Nothing else in the API contract changed. There is
  no legacy synchronous endpoint kept alongside this — see the README's
  execution model section for the rationale.

### Added

- **Bounded background run execution** (`app/runner/run_manager.py`):
  `RunManager` owns run creation, lifecycle transitions, a bounded
  `asyncio.Queue` of pending work, and a small fixed pool of asyncio worker
  tasks (`RUN_WORKER_COUNT`, default 2) that call the unchanged
  `execute_suite` primitive. Workers start/stop with the FastAPI lifespan.
  Queue capacity (`RUN_QUEUE_MAXSIZE`, default 10) is bounded; submissions
  past that capacity get `429`, not silently unbounded queueing. A worker
  that hits an exception (in the suite itself, or in bookkeeping) logs it,
  marks the run `failed`, and keeps servicing subsequent queued runs — one
  failure never kills the worker loop.
- **New run lifecycle model** (`app/models/run.py`): `RunStatus` is now
  exactly `queued` / `running` / `completed` / `failed` (previously
  `pending`/`running`/`completed`/`failed`, where `pending` was dead code —
  never actually produced). `RunSummary` gained `started_at` and
  `failed_at` alongside `created_at`/`completed_at`, with documented,
  tested timestamp invariants per status. Transitions are enforced
  monotonic: a completed or failed run is never re-executed or regressed
  (`RunManager._execute`'s defensive `QUEUED`-only guard, backed by a
  regression test).
- 18 new tests across `tests/unit/test_run_manager.py` (lifecycle,
  timestamp invariants, bounded concurrency, queue-full behavior, failure
  isolation, terminal-state monotonicity — all synchronization-primitive-based,
  no sleep-heavy timing) and `tests/integration/test_api.py` /
  `tests/integration/test_scientific_equivalence.py` (202/429/409 contract,
  API responsiveness during execution, concurrent-run isolation, and a
  mechanical proof that the async path's output is byte-identical to direct
  `execute_suite` after stripping run IDs/timestamps/latency — Phase 2A's
  21-case, 3/4 prompt-injection, injection-004-blocked results are
  unchanged).
- **`POST /runs` now validates `suite_name`.** Only one suite is ever
  loaded; omitting `suite_name` or passing exactly the loaded suite's name
  queues a run as before, but any other value is now rejected with `400`
  *before* anything is queued, rather than being silently ignored while a
  different suite quietly ran anyway.
- **`RUN_WORKER_COUNT`/`RUN_QUEUE_MAXSIZE` are validated at both layers**:
  `Settings.__post_init__` and `RunManager.__init__` both reject values
  `< 1` — a 0 in particular would otherwise be especially dangerous, since
  `asyncio.Queue(maxsize=0)` means *unbounded*, not zero, which would
  silently defeat the bounded-execution guarantee.
- **Documented, tested shutdown policy**: `RunManager.stop()` does not wait
  for in-flight or queued runs to finish — a worker mid-execution is
  cancelled immediately and its run is left stuck at whatever state it was
  last persisted in (never fabricated to a terminal state, never silently
  discarded), consistent with Phase 2B's in-memory-only storage having no
  durability contract to honor.
- Confirmed (and regression-tested) that `RunManager.submit()` is already
  atomic with respect to `RunQueueFullError`: `asyncio.Queue.put_nowait()`
  is attempted *before* the run record is ever written to the repository,
  so a rejected submission never receives a run ID, is never persisted, and
  cannot execute — no orphan `queued` record is left behind.

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
