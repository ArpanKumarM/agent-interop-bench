# Public-Sharing Labels and Verbatim Field Egress in an MCP-to-A2A Agent Configuration

[![CI](https://github.com/ArpanKumarM/agent-interop-bench/actions/workflows/ci.yml/badge.svg)](https://github.com/ArpanKumarM/agent-interop-bench/actions/workflows/ci.yml)

Research artifact for the paper **"Public-Sharing Labels and Verbatim Field
Egress in an MCP-to-A2A Agent Configuration: A Controlled Multi-Model
Study."** Manuscript source: [`paper/arxiv/main.tex`](paper/arxiv/main.tex)
(reference copy: [`paper/main.md`](paper/main.md)).

## What the study measures

One narrow behavior at a concrete **Model Context Protocol (MCP) → Agent2Agent
(A2A)** handoff: a real-model *host* reads a local record over MCP and then
sends a message to a remote A2A agent. We ask how an explicit sensitivity
label on that record changes the **verbatim egress** of the record's
substantive field values into the outbound message, relative to the same
record with no label.

**Three-arm matched design (frozen before execution).** For each of 10
record scenarios the record is presented in three forms whose six
substantive field values are byte-identical, differing only in the opening
header line:

| arm | opening line |
|---|---|
| **C** — confidential | `[CONFIDENTIAL - INTERNAL ONLY]` |
| **N** — unlabeled | *(no sensitivity header)* |
| **P** — public | `[PUBLIC - OK TO SHARE]` |

Four models (three OpenAI GPT-5.6 tiers, Claude Sonnet 5) × 3 arms × 4
repeats = **480 trials**. The scenario is the unit of generalization; the
four repeats are repeated observations. Outcome:
`any_sensitive_field_egress` — exact-substring occurrence of any of six
substantive values in the outbound message (no LLM judge). We report the 10
scenario-level values of `C − N`, `P − N`, `C − P`, their mean and median,
and sign counts — **no p-values, intervals, or cross-model pooling.**

## Headline result

- **`C − N` (confidential vs. unlabeled) is inconclusive and floor-limited
  in every model.** For three models both arms sit at zero; for
  `claude-sonnet-5` the small negative difference sits over a low unlabeled
  baseline (5/40). The design does not distinguish a genuine null from a
  floor, so it **does not show that confidential labels lack a protective
  effect**.
- **`P − N` (public vs. unlabeled) is a descriptive, strongly
  model-dependent association** with higher verbatim egress:
  `claude-sonnet-5` strong and consistent (mean +0.800, all 10 scenarios;
  mostly an association with *whether Claude relays at all*),
  `gpt-5.6-luna` moderate/floor-limited (+0.250), `gpt-5.6-sol`
  small/floor-limited (+0.125, median 0), `gpt-5.6-terra` a complete floor.
- This is an association in **one configuration**, not a causal or general
  effect.

An earlier frozen **two-arm** study (`v4r1`, confidential vs. public only)
reproduces its `C − P` direction descriptively for the three non-floor
models; it is not pooled with the three-arm study.

## Repository layout

```
paper/                 manuscript source, machine-generated tables, numeric audit
app/                    the measurement harness and the offline analysis code
mock_servers/           local in-process MCP and A2A fixtures (no network)
benchmarks/             frozen Phase 6 and Phase 7 experiment definitions
policies/               the fixed host policy
scripts/                reproduction / verification helpers
tests/                  test suite for the released implementation
docs/                   methodology and reproduction notes
PROVENANCE.md           frozen chronology and every byte-pinned identifier
```

The raw execution package, integrity manifests, and analysis artifacts
(`reports/…`) are large and `.gitignore`d; they are distributed as the
public artifact release (see below).

## Reproduce the analysis offline (no provider calls)

```bash
uv sync --frozen

# 1. get the frozen artifacts: download the paper-v1.0 release and extract
#    it so that reports/ sits at the repository root.

# 2. re-run the frozen, pre-specified analysis against the frozen raw copies
uv run python -m app.cli.phase_7e_neutral
#    -> rewrites reports/phase_7e_analysis/ ; must reproduce it byte-for-byte

# 3. regenerate every manuscript number and audit it against the frozen data
uv run python paper/arxiv/gen_tables.py
uv run python paper/arxiv/audit_numbers.py
```

## Verify the raw data

```bash
# raw trials.jsonl hashes must match PROVENANCE.md
for r in sol terra luna claude; do
  shasum -a 256 reports/_phase7d_preanalysis_freeze/raw_runs/phase-7a-confirmatory-v1-$r/trials.jsonl
done

# frozen manifests must match PROVENANCE.md
shasum -a 256 \
  reports/_phase7d_preanalysis_freeze/MANIFEST.sha256 \
  reports/phase_7e_analysis/MANIFEST.sha256 \
  reports/phase_6e_v4r1/MANIFEST.sha256 \
  reports/_phase6d_v4r1_integrity/MANIFEST.sha256

# rebuild + byte-compare the Phase 7D deterministic freeze archives
uv run python scripts/phase_7d_build_freeze.py --check
```

## Rebuild the PDF

```bash
uv run python paper/arxiv/gen_tables.py
bash paper/arxiv/build_pdf.sh            # deterministic; sets SOURCE_DATE_EPOCH
uv run python paper/arxiv/audit_numbers.py
```

A minimal arXiv source archive is built by
`uv run python paper/arxiv/build_arxiv_submission.py`; proposed submission
metadata is in [`paper/arxiv/ARXIV_METADATA.txt`](paper/arxiv/ARXIV_METADATA.txt).

## Public artifact release

The frozen raw execution package, integrity/pre-analysis manifests, Phase 7
analysis artifacts, and the necessary Phase 6 comparison artifacts are
released here:

<https://github.com/ArpanKumarM/agent-interop-bench/releases/tag/paper-v1.0>

All hashes are pinned in [`PROVENANCE.md`](PROVENANCE.md).

## Scope and limits

Local in-process synthetic MCP and A2A fixtures; one host policy; one
`{relay_to_remote, stop}` decision surface; one provider snapshot; provider
configurations not numerically equated across families. The exact-substring
detector measures verbatim value leakage only. Results are specific to this
configuration — not a causal claim, a provider ranking, or a general safety
verdict. See the paper's Limitations section and
[`PROVENANCE.md`](PROVENANCE.md).

## Provenance discipline

Manuscript and analysis preparation made **zero provider calls** and
changed no raw observation, stimulus, schedule, model, parameter, outcome
definition, or analysis plan. Every manuscript number is machine-generated
from the frozen artifacts and re-verified by `paper/arxiv/audit_numbers.py`.

## Citation

See [`CITATION.cff`](CITATION.cff).

## License

Code is released under the MIT License (see [`LICENSE`](LICENSE)). The
manuscript text is the author's; a recommended arXiv license is noted in
`paper/arxiv/ARXIV_METADATA.txt`.
