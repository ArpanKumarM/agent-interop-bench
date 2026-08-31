# arXiv submission package — Agent Interop Bench cross-protocol pilot

This directory is a self-contained arXiv-ready LaTeX source package. It
renders the manuscript `paper/main.md` as a conventional single-column
research paper. **Manuscript preparation introduced no new experimental runs
or provider calls; all empirical results are reproduced from the frozen
public release `phase4b-results-v1`.**

The `main.tex` here is the **v2 (compressed) layout**: the earlier v1
technical-report styling (numbered/bulleted lists, 14 sections, 19 pages)
was rewritten into cohesive academic prose and a nine-section structure.
No scientific result, number, Wilson interval, citation, or claim was
changed; low-value per-cell detail moved to appendices.

## Final title

> Cross-Protocol Failure Propagation Across MCP and A2A Agents: A Controlled
> Pilot on Information Flow, Behavioral Influence, and Containment

## Abstract

Deployed AI agents increasingly speak two protocols at once: the Model
Context Protocol (MCP) for local tool use, and the Agent2Agent Protocol
(A2A) for delegating work to other agents. Dedicated safety benchmarks for
each evaluate one protocol in isolation. We study the seam. A composed
harness drives one real-model host across both protocol legs --- implemented
as local deterministic MCP and A2A protocol fixtures, not external services
--- in a single ordered event trace, with an observable cross-protocol
provenance model (deterministic content canaries carrying a sensitivity
label, an explicit allowed-edge policy, and per-event causal ancestry) so
that information flow and behavioral influence across the boundary are
measured by exact rule-based checks, without an LLM-based judge or
evaluator. Using a decision-point methodology that deterministically builds
the situation and then elicits one restricted host decision, we ran a
controlled confirmatory pilot over three OpenAI GPT-5.6 models, 240 trials
in total. We separate *relay initiation* (the host sent a message onto the
A2A leg after reading a confidential MCP record) from *direct sensitive
egress* (the exact confidential marker crossed the disallowed
host-to-remote edge): relay initiation varied widely by model (15%, 85%,
100% of confidential trials), while direct exact-token egress was 0 for
every model (0/3, 0/17, 0/20 of relay trials; Wilson 95% upper bounds
56.2%, 18.4%, 16.1%). This is verbatim-marker leakage only, not semantic or
paraphrased leakage. Scoring whether the host both selected the
mutation-attempt action *and* named a tool the harness discovered to be
mutating (our primary influence outcome), the adversarial A2A artifact
condition showed a higher rate than a structurally matched benign condition
in all three models (signed treatment-control differences +0.20, +0.40,
+0.50; Wilson 95% intervals per cell) --- an association under a controlled
manipulation, not a causal-mechanism claim. Every one of the 56 observed
actual mutating-tool requests was blocked by an independent mutation gate,
and none executed. We report Wilson 95% intervals and signed rate
differences throughout and deliberately report no p-values: the replicates
in a cell are repeated draws from one model under one fixed stimulus and are
not assumed statistically independent. The complete raw runs and a fully
offline analysis pipeline are published as a deterministic, hash-pinned
release.

## Section structure

1. Introduction
2. Background and Related Work
3. Threat Model and Research Questions
4. Agent Interop Bench
5. Experimental Methodology (5.1 decision-point, 5.2 stimuli, 5.3 model
   panel, 5.4 reproducibility mechanism, 5.5 outcome definitions,
   5.6 statistical reporting)
6. Results (6.1 cross-protocol information flow, 6.2 behavioral influence,
   6.3 containment)
7. Discussion
8. Limitations
9. Conclusion (with a concise Reproducibility paragraph)

References

Appendix A — Experimental-integrity detail (full 12-cell table)
Appendix B — Wrapper / tool-selection diagnostic (full table)
Appendix C — Extended reproducibility detail (commits, archive hash,
per-run execution fingerprints, offline recompute commands)

Main-text length (Introduction through Conclusion): approximately 5,060
words. Compiled length: 13 pages including references and appendices.

## Provenance

| item | value |
|---|---|
| Reference manuscript (`paper/main.md`) commit | `67f61bc41303fed42a8d3d9adb00f9903426be19` |
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
environment: `geometry`, `amsmath`, `amssymb`, `stmaryrd`, `graphicx`,
`array`, `booktabs`, `multirow`, `xcolor`, `microtype`, `url`, `caption`,
`pgfplots` (`compat=1.18`, `groupplots` library), `natbib`, `hyperref`,
`lmodern`. No custom fonts, no `\write18` / shell-escape, no network access,
no absolute paths.

## Author metadata

```
\author{Arpan Kumar Mahapatra\\
\texttt{arpan.arpan.mohapatra@gmail.com}}
```

Single author, no affiliation line, as provided.

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

`main.bbl` is bundled, so `pdflatex main` (run twice for cross-references)
also produces the complete document with a correct bibliography even if
`bibtex` is not re-run.

Verified locally with TeX Live 2026 (`pdflatex`): **13 pages, 0 undefined
citations, 0 undefined references, 0 missing figures, 0 fatal warnings,
0 overfull `\hbox`, 0 overfull `\vbox`, no missing glyphs.** Compiled PDF:
`../arxiv_preview.pdf`.

## Deterministic source archive

`../agent-interop-bench-arxiv-v2.tar.gz` contains exactly the three compile
inputs (`main.tex`, `references.bib`, `main.bbl`), built deterministically
(sorted members, `mtime=0`, mode `0444`, `uid=gid=0`, gzip `mtime=0`).

```
archive : agent-interop-bench-arxiv-v2.tar.gz
bytes   : 25609
sha256  : eb14908a4a09e3c7330396fa55b9c7b3167751633a6aef30d8e46141bb705b9f
members : main.bbl, main.tex, references.bib
```

## Scope note (unchanged from the manuscript)

The only non-local component in every experiment is real provider model
inference (OpenAI GPT-5.6 via the Responses API); this real GPT-5.6 host is
the system under test. All MCP and A2A infrastructure is local deterministic
protocol fixtures; no production, external, or third-party MCP server or A2A
agent was contacted. Results are conditional on four fixed stimuli, one host
policy, one tool surface, three model identifiers, and one point in time. No
p-values, no significance tests, no general model-safety verdict, no
semantic-leakage claim, no claim that repeated provider calls are
statistically independent, and no priority claim on cross-protocol
composition risk or MCP+A2A pivoting --- prior articulation by AgentRFC and
by the IETF "Protocol Pivoting" Internet-Draft is acknowledged in Section 2.
