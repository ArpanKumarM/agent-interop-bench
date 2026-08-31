# arXiv submission package — MCP--A2A cross-protocol composition study (v4r1)

Self-contained arXiv-ready LaTeX source. Mirrors `paper/main.md` as a
conventional single-column research paper. **Manuscript preparation made
zero provider calls and changed no raw observation, stimulus, schedule,
model, parameter, primary outcome definition, or analysis plan.** Every
numeric table body and the RQ1 pair-effect figure are **machine-generated**
from the frozen analysis artifacts by `gen_tables.py` (into `generated/`)
and audited by `audit_numbers.py`; they are not hand-transcribed. The prior
Phase 4B pilot is historical evidence only; the frozen **v4r1 Phase 6
study** is the confirmatory empirical core, and this manuscript is rebuilt
entirely from it.

## Title

> Cross-Protocol Information Flow in MCP--A2A Agent Composition: A Controlled
> Multi-Model Study

## Section structure

1. Abstract
2. Introduction
3. Background and System Model
4. Related Work
5. Experimental Method
6. Results (5.1 RQ1 — a confidential-versus-public labeling contrast;
   5.2 RQ2 — a complete floor; 5.3 Verified enforcement property, reported
   as a harness invariant, **not** a research question)
7. Discussion
8. Threats to Validity and Limitations
9. Reproducibility (machine-generated execution/integrity table,
   execution-deviation paragraph, machine-generated pinned-identifier table)
10. Conclusion

Appendix A --- RQ1 pair-level table (machine-generated). Appendix B --- RQ2
pair-level table.

Compiled length: **13 pages** including references and both appendices
(`pdflatex` + `bibtex`, TeX Live 2026): 0 undefined citations, 0 undefined
references, 0 overfull `\hbox`, 2 benign underfull `\hbox`, 0 missing
glyphs, 0 fatal warnings. The date is a literal (`\date{August 2026}`, no
`\today`); with `SOURCE_DATE_EPOCH=0` the PDF is byte-reproducible
(SHA-256 `e41e1f6bafa4732e813145ef53b25d022335e04ffd54192ecabf0cccef8d80ca`).

## Provenance

| item | value |
|---|---|
| Execution source commit | `23bf90bf379654f0afc2fadaa5a16ade30ae3439` |
| Analysis source commit (Phase 6E.2) | `60024fcf24624fab90ac9d6a3be7c73be17acbc9` |
| Frozen raw-integrity package manifest SHA-256 | `8310a1f9c1c1464ad1786b832deac328b8d21bf209919f1d57ba66cc1a542695` |
| Final analysis-artifact manifest SHA-256 | `db34e1bad9d770dcdf38e1d887550c2eab999ffa404c79cea936be429e540593` |
| Resolved dependency lock SHA-256 | `6b0d8279010a57be250d134ca291403061b4a8f7937fd2c93563ef9f6243fb56` |
| Environment | Python 3.12.2; `mcp==2.0.0`, `openai==3.3.1`, `anthropic==1.2.0` |

All figures are LaTeX (pgfplots) renderings of the exact frozen numbers in
`reports/phase_6e_v4r1/`; no raster or vector image files are bundled.

## Files

| file | role | in source archive? |
|---|---|---|
| `main.tex` | the manuscript (LaTeX) | yes |
| `references.bib` | bibliography database (18 cited entries; all web-verified against primary sources, see `paper/citation_audit.md`; proper nouns brace-protected for `plainnat`) | yes |
| `main.bbl` | pre-generated bibliography (natbib / `plainnat`) | yes |
| `generated/*.tex` | machine-generated numeric table bodies, `\input`-ed by `main.tex` (7 files) | yes |
| `generated/*.dat` | machine-generated pgfplots data for the RQ1 pair-effect figure (2 files) | yes |
| `generated/facts.json` | machine-extracted fact digest used by the numeric audit | yes (provenance) |
| `gen_tables.py` | offline generator for `generated/*` from the frozen Phase 6E.2 artifacts (no provider calls) | yes (provenance) |
| `audit_numbers.py` | offline numeric audit: manuscript numbers vs. frozen artifacts | no (not a compile input) |
| `build_arxiv_tar.py` | deterministic archive builder | no (not a compile input) |
| `README_SUBMISSION.md` | this file | no (not a compile input) |

Packages: `geometry`, `amsmath`, `amssymb`, `graphicx`, `array`, `booktabs`,
`xcolor`, `microtype`, `url`, `caption`, `pgfplots` (`compat=1.18`),
`natbib`, `hyperref`, `lmodern`. No custom fonts, no shell-escape, no
network access, no absolute paths.

Regeneration: `uv run python paper/arxiv/gen_tables.py` rewrites
`generated/*`; `uv run python paper/arxiv/audit_numbers.py` re-verifies every
manuscript number against `reports/phase_6e_v4r1/`;
`uv run python paper/arxiv/build_arxiv_tar.py` rebuilds the archive.

## Compilation

```
pdflatex main
bibtex   main
pdflatex main
pdflatex main
```

`main.bbl` and `generated/*` are bundled. Compiled PDF: `../arxiv_preview.pdf`.

## Deterministic source archive

`../agent-interop-bench-arxiv-v2.tar.gz` contains `main.tex`,
`references.bib`, `main.bbl`, `gen_tables.py`, and `generated/`
(`facts.json`, 7 `.tex` fragments, 2 `.dat` files), built deterministically
by `build_arxiv_tar.py` (sorted members, `mtime=0`, mode `0444`,
`uid=gid=0`, empty owner/group, gzip `mtime=0`). It extracts and compiles
with the four-command sequence above using only the bundled `main.bbl`.

## Scope note

The only non-local component in every trial is real provider model
inference (three OpenAI GPT-5.6 models via the Responses API and Claude
Sonnet 5 via the Anthropic Messages API); the real model host is the system
under test. All MCP and A2A infrastructure is local deterministic protocol
fixtures; no production, external, or third-party MCP server or A2A agent was
contacted. Results are conditional on 40 fixed overlays (10 matched pairs
per experiment), one host policy, one 12-tool model-visible surface, four
model identifiers, and one point in time. RQ1 is a symmetric
confidential-versus-public **labeling contrast**, not a causal claim that
confidential marking protects data; RQ2 is a **complete floor** (zero
state-changing tool requests) and establishes no resistance to cross-agent
influence; §5.3 is a deterministic-gate-plus-audit **enforcement property**,
not a model safety rate. No p-values, no significance tests, no general
model-safety verdict, no provider ranking, no semantic-leakage claim, and no
priority claim on cross-protocol composition risk or MCP+A2A pivoting ---
prior articulation by AgentRFC, an IETF Internet-Draft, and a formal
composition analysis is acknowledged in the Related Work section.

## Recommended arXiv category

Left for the submitter. Subject matter is agent/LLM security evaluation;
`cs.CR` with a `cs.AI` cross-list is a plausible choice (non-binding).
