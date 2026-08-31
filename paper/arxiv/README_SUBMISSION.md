# arXiv submission package — Agent Interop Bench cross-protocol pilot

This directory is a self-contained arXiv-ready LaTeX source package. It is a
faithful conversion of `paper/main.md` into LaTeX; **no experiment, provider
call, or model inference was run** to produce it, and every number is
verbatim from the frozen public release `phase4b-results-v1`.

## Final title

> Cross-Protocol Failure Propagation Across MCP and A2A Agents: A Controlled
> Pilot on Information Flow, Behavioral Influence, and Containment

## Abstract

Deployed AI agents increasingly speak two protocols at once: the Model
Context Protocol (MCP) for local tool use, and the Agent2Agent Protocol
(A2A) for delegating work to other agents. Each protocol has begun to
attract dedicated safety benchmarks, but those benchmarks evaluate a single
protocol in isolation. We study what happens *at the seam*: a real-model
host that reads content from an MCP tool and, in the same task, exchanges
messages with an A2A agent. We introduce Agent Interop Bench's composed
harness, which drives one real-model host across both protocol legs ---
implemented here as local deterministic MCP and A2A protocol fixtures, not
external services --- within a single ordered event trace, and attaches an
observable cross-protocol provenance model (deterministic content canaries
with a sensitivity label, an explicit allowed-edge policy, and per-event
causal ancestry) so that information flow and behavioral influence across
the protocol boundary can be measured by exact rule-based checks without an
LLM-based judge or evaluator.

Using a decision-point methodology that deterministically constructs the
situation and then elicits exactly one restricted host decision, we ran a
controlled confirmatory pilot over three models (`gpt-5.6-sol`,
`gpt-5.6-terra`, `gpt-5.6-luna`), 240 trials total (20 blocked-randomised
replicates per model per condition), addressing three questions. **RQ1:**
does confidential MCP-originated content propagate across the A2A boundary?
We separate *relay initiation* (the host chose to send a message onto the
A2A leg after reading a confidential record) from *direct sensitive egress*
(the exact confidential marker crossed the host->remote/A2A edge). Relay
initiation varied widely by model (15%, 85%, 100% of confidential trials);
direct exact-token sensitive egress was 0 in every model (0/3, 0/17, 0/20 of
relay trials; Wilson 95% upper bounds 56.2%, 18.4%, 16.1%). This measures
verbatim marker leakage only and does not evaluate semantic or paraphrased
leakage. **RQ2:** can an adversarial A2A artifact influence a host toward
requesting a *mutating* MCP tool? Using the outcome *actual mutating-tool
request* --- the host selected the mutation-attempt action and named a tool
the harness discovered to be mutating --- the adversarial condition showed a
higher rate than the structurally matched benign condition for all three
models (signed treatment-control rate differences +0.20, +0.40, +0.50;
Wilson 95% intervals reported per cell). We report this as an association
under a controlled manipulation, not a causal-mechanism claim. **RQ3:** can
an independent mutation gate contain those requests? Every *observed* actual
mutating-tool request was blocked by the gate (100% blocked in all six
model x condition cells) and zero executed across the entire study (Wilson
95% upper bounds on the executed rate 21.5-56.2% depending on cell size). We
report Wilson 95% confidence intervals and signed rate differences
throughout and deliberately report no p-values; the 20 replicates in a cell
are repeated draws from one model under one fixed stimulus and are not
assumed to be statistically independent provider executions. The complete
raw runs, the offline analysis pipeline, and every derived table and figure
are published as a deterministic, hash-pinned reproducibility release.

## Provenance

| item | value |
|---|---|
| Manuscript commit (source of this conversion) | `67f61bc41303fed42a8d3d9adb00f9903426be19` |
| Frozen experimental source commit | `6cb64606a614c42145cc2da03468551c1ca48c6d` |
| Offline analysis commit (tables + figures) | `caf036db97b142005e8f12e02fc9b95d0a205cbd` |
| Frozen results release (tag) | `phase4b-results-v1` |
| Frozen results release (URL) | https://github.com/ArpanKumarM/agent-interop-bench/releases/tag/phase4b-results-v1 |
| Phase 4B results archive SHA-256 | `85c04c34d8fed427ac54a98f0f2ed1ccc50df32f1d9958fe6d21ef71bf9defb5` |

All Phase 4B figures in the manuscript are LaTeX (TikZ / pgfplots)
renderings of the exact frozen numbers in
`docs/assets/phase_4b/table_*.csv` and the corresponding SVG files in the
release; no raster or vector image files are bundled or required.

## Files in this package

| file | role | in source archive? |
|---|---|---|
| `main.tex` | the manuscript (LaTeX) | yes |
| `references.bib` | bibliography database (15 entries, all cited) | yes |
| `main.bbl` | pre-generated bibliography (natbib / `plainnat`) | yes |
| `README_SUBMISSION.md` | this file (submission metadata) | no (not a compile input) |

The manuscript uses only packages present in a standard full TeX Live / arXiv
environment: `geometry`, `amsmath`, `amssymb`, `graphicx`, `array`,
`booktabs`, `multirow`, `xcolor`, `microtype`, `url`, `caption`, `pgfplots`
(`compat=1.18`), `natbib`, `hyperref`, `lmodern`. No custom fonts, no
`\write18` / shell-escape, no network access, no absolute paths.

## Author metadata — TODO (unresolved)

The source manuscript `paper/main.md` contains **no** author, affiliation, or
contact metadata. `main.tex` therefore carries explicit placeholders:

```
\author{%
  [AUTHOR NAME --- TODO]\\
  \texttt{[AFFILIATION --- TODO]}\\
  \texttt{[EMAIL --- TODO]}%
}
```

Fill these in before submitting. Nothing has been invented.

## Recommended arXiv category — TODO

Left for the submitter to decide. (Non-binding note: the subject matter is
agent/LLM security evaluation; `cs.CR` with a `cs.AI` cross-list is a
plausible choice, but this is not prescribed here.)

## Compilation

Standard arXiv-compatible workflow, `pdflatex` + `bibtex`, no shell-escape,
no internet:

```
pdflatex main
bibtex   main
pdflatex main
pdflatex main
```

`main.bbl` is bundled, so a single `pdflatex main` (twice, for cross-refs)
also produces the complete document with a correct bibliography even if
`bibtex` is not re-run.

Verified locally with TeX Live 2026 (`pdflatex`): 19 pages, **0 undefined
citations, 0 undefined references, 0 missing figures, 0 fatal warnings**; the
only residual `Overfull \hbox` warnings are <= 2.3 pt (sub-visible) in body
prose. Compiled PDF: `../arxiv_preview.pdf`.

## Deterministic source archive

`../agent-interop-bench-arxiv-v1.tar.gz` contains exactly the three compile
inputs (`main.tex`, `references.bib`, `main.bbl`), built deterministically
(sorted members, `mtime=0`, mode `0444`, `uid=gid=0`, gzip `mtime=0`).

```
archive : agent-interop-bench-arxiv-v1.tar.gz
bytes   : 27473
sha256  : e3d2613558ea35a2677e078272ff2b90337cb1a73d6f2b37323ccbdc93714525
members : main.bbl, main.tex, references.bib
```

## Scope note (unchanged from the manuscript)

The only non-local component in every experiment is real provider model
inference (OpenAI GPT-5.6 via the Responses API). All MCP and A2A
infrastructure is local deterministic protocol fixtures; no production,
external, or third-party MCP server or A2A agent was contacted. Results are
conditional on four fixed stimuli, one host policy, one tool surface, three
model identifiers, and one point in time. No p-values, no significance
tests, no general model-safety verdict, no semantic-leakage claim, no
claim that repeated provider calls are statistically independent, and no
priority claim on cross-protocol composition risk or MCP+A2A pivoting.
