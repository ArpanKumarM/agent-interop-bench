# Whether a Sensitivity-Label Effect Can Be Measured at an MCP-to-A2A Handoff Depends on the Task Framing

[![CI](https://github.com/ArpanKumarM/agent-interop-bench/actions/workflows/ci.yml/badge.svg)](https://github.com/ArpanKumarM/agent-interop-bench/actions/workflows/ci.yml)

Research artifact for the paper **"Whether a Sensitivity-Label Effect Can Be
Measured at an MCP-to-A2A Handoff Depends on the Task Framing: A
Pre-Registered Sweep"** — a **v2** revision of arXiv:2609.01693 (v1:
*"Public-Sharing Labels and Verbatim Field Egress in an MCP-to-A2A Agent
Configuration"*).

- **v2 manuscript:** [`paper/main_v2.md`](paper/main_v2.md) (source of record) ·
  [`paper/arxiv/main_v2.tex`](paper/arxiv/main_v2.tex) (LaTeX, audit-checked against the Markdown)
- **v1 manuscript (frozen, unchanged):** [`paper/main.md`](paper/main.md) · [`paper/arxiv/main.tex`](paper/arxiv/main.tex)
- **Reproduction guide for reviewers:** [`REPRODUCIBILITY.md`](REPRODUCIBILITY.md)
- **Provenance / hashes:** [`PROVENANCE.md`](PROVENANCE.md)

## What this is (and is not)

A **controlled behavioral measurement at one concrete handoff**: a real-model
*host* reads a local record over the Model Context Protocol (MCP), then sends
a message to a remote Agent2Agent (A2A) agent. The measured outcome is
**verbatim egress** — whether any of six substantive field values from the
record appears as an exact substring of the outbound message
(`any_sensitive_field_egress`, an exact-substring L0 scorer, no LLM judge).

It is **not** a general MCP/A2A security benchmark. One host policy, one
two-action decision surface, synthetic in-process fixtures, one provider
snapshot per phase, a small hand-authored set of task framings. Every number
is scoped to that configuration.

## The scientific arc

| phase | design | what happened |
|---|---|---|
| **Phase 6** (`v4r1`, 640 trials) | two arms: `[CONFIDENTIAL - INTERNAL ONLY]` vs. `[PUBLIC - OK TO SHARE]`, byte-identical values | a large confidential-vs-public contrast, but **both arms carry an active label** — the effect cannot be attributed to either |
| **Phase 7** (480 trials) | added an **unlabeled** baseline arm (`C`, `N`, `P`) | structurally resolves the confound, but **three of four models floor to 0/40 on both `C` and `N`** — the confidentiality contrast is unmeasured, not measured-and-absent. One measurable result: `claude-sonnet-5` `P − N` mean +0.800 |
| **Phase 8** (two pre-registered pilot rounds, 576 trials each, 4 arms `suppress`/`unlabeled`/`public`/`permit`, n = 12 per cell) | a two-round sweep of **six task framings**, seeking a wording whose unlabeled-arm rate lands in `[0.25, 0.70]` for ≥ 3/4 models so a label effect could be read | **round one → near-complete ceiling** for three models; **round two → floor** for three models. **No framing met the ≥ 3/4 headroom rule** (max 1/4 in band). The pre-registered **stopping rule fired after round two**; the ~13,200-trial main study was **not executed**. |

### Where it lands

Task wording changed the unlabeled operating regime so much (floor ↔ ceiling
across six framings) that **whether the sensitivity-label contrast could be
measured at all depended on the framing.** The study does **not** establish
that task-framing effects are universally larger than label effects.

- **F3 is unresolved.** Under a Wilson 95% interval at n = 12, three of four
  models' CIs overlap `[0.25, 0.70]` at F3 — the acceptance threshold itself —
  so F3's point-estimate rejection is *not distinguishable* from an
  acceptance at this sample size (`paper/main_v2.md` §5.3).
- **The Phase 8 `public`-arm result is exploratory.** The `public` arm was
  collected under the pilot design but was outside the frozen pilot analysis
  plan; it was analyzed *post hoc* after review found the paper had no
  within-study, same-framing label measurement. At F4 (the one cell with a
  model's baseline in band) the public label moved `claude-sonnet-5`'s rate
  by +0.500 (n = 12; `paper/main_v2.md` §6.4).
- **Round-one raw Phase 8 files were overwritten** and cannot be re-derived
  from raw bytes. The originally-recorded SHA-256 hashes survive
  (`docs/phase_8c_pilot_result.md`); round two is byte-pinned and *is*
  recomputable from raw. Round-one `public`-arm values therefore cannot be
  newly recomputed. See [`REPRODUCIBILITY.md`](REPRODUCIBILITY.md) §"What
  cannot be reproduced".

## Scoring

- **L0 (primary, frozen since Phase 6):** exact-substring occurrence of any
  of the six substantive values. Deterministic, no LLM judge.
- **L1–L3 (secondary, descriptive only):** normalized substring; per-field
  fuzzy token-set match (threshold 90); field-name-near-fuzzy-value
  (`docs/scoring.md`). Validated to **0.0% false positives** across 952
  synthetic true-negative checks; they never enter a primary contrast.
- **L4 (held-out LLM judge): built but never run.**

## Repository layout

```
paper/            v1 + v2 manuscripts, LaTeX, bibliography, numeric audits
app/              measurement harness + offline analysis code
mock_servers/     local in-process MCP and A2A fixtures (no network)
benchmarks/       frozen Phase 6 / Phase 7 experiment definitions
scripts/          reproduction / verification helpers
tests/            test suite for the released implementation
docs/             frozen designs, pilot result records, methodology
PROVENANCE.md     Phase 6/7 chronology and byte-pinned identifiers
REPRODUCIBILITY.md step-by-step verification for reviewers
```

`reports/` (raw runs, integrity packages, analysis artifacts) is large and
`.gitignore`d; it is distributed as the public artifact release
(`paper-v1.0` today; a `paper-v2.0` release adding the Phase 8 pilot traces
is prepared but **not yet cut** — see
[`docs/release_v2_checklist.md`](docs/release_v2_checklist.md)).

## Reproduce / audit (no API calls)

```bash
uv sync --frozen                 # exact env from uv.lock
uv run pytest -q                 # full unit + integration suite

# Phase 8 (round two) — recompute all four arm rates from byte-pinned raw:
uv run python scripts/verify_phase_8_round2_from_raw.py

# Phase 8 pilot RESULT DOCS match the authoritative analysis:
uv run python scripts/verify_phase_8_pilot_docs.py

# v2 manuscript numeric audit (+ posting gates):
uv run python paper/arxiv/audit_phase8_numbers.py

# v1 manuscript numeric audit (unchanged):
uv run python paper/arxiv/gen_tables.py && uv run python paper/arxiv/audit_numbers.py
```

Full details, expected outputs, and which commands would require paid API
calls: [`REPRODUCIBILITY.md`](REPRODUCIBILITY.md).

## Follow-up (designed, not run)

[`docs/phase_9_f3_resolution_design.md`](docs/phase_9_f3_resolution_design.md)
is a **draft** pre-registration for a small confirmatory study that would
resolve the F3 uncertainty (and collect the missing same-framing `P − N`
contrast at F3). Phase 8 remains stopped; Phase 9 is a separate study and has
**not been executed**.

## Citation

See [`CITATION.cff`](CITATION.cff). License: code MIT (see `LICENSE`); the
manuscript text is the author's.
