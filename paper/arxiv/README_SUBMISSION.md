# arXiv submission package — public-sharing labels at the MCP--A2A seam (Phase 7F)

Self-contained arXiv-ready LaTeX source. Mirrors `paper/main.md` as a
conventional single-column research paper, rebuilt around the frozen
**Phase 7 three-arm neutral-baseline study** (`composed-live-canary-007a` /
`v7a`). **Manuscript preparation made zero provider calls and changed no
raw observation, stimulus, schedule, model, parameter, primary-outcome
definition, or analysis plan.** Every numeric table body and every figure
datum is **machine-generated** by `gen_tables.py` (into `generated/`) from
the frozen Phase 7E analysis artifacts (`reports/phase_7e_analysis/`) and,
for the earlier two-arm study and the enforcement property, the frozen
Phase 6E.2 artifacts; they are not hand-transcribed and are audited by
`audit_numbers.py`. **Phase 6 and Phase 7 observations are never pooled.**

## Title

> Public-Sharing Labels and Verbatim Field Egress at the MCP--A2A Seam:
> A Controlled Multi-Model Study

## Section structure

1. Abstract
2. Introduction
3. Background and System Model (incl. *System enforcement: a verified
   property*)
4. Related Work
5. Experimental Method (decision-point execution; three-arm matched design;
   stimuli/host policy/panel; frozen outcome definition; statistical
   presentation — scenario is the generalization unit, `n = 10`)
6. Results (6.1 RQ1: the three pre-registered contrasts C-N, P-N, C-P;
   6.2 Claude C-N conservative floor-bounded reading; 6.3 secondary
   diagnostics; 6.4 the earlier two-arm study + descriptive C-P
   reproducibility; 6.5 secondary null experiment)
7. Discussion
8. Threats to Validity and Limitations
9. Reproducibility and Provenance (scientific chronology Phase 6 -> 7E.1;
   incidental-exposure disclosure; machine-generated execution/integrity
   table; machine-generated pinned-identifier table)
10. Conclusion

Appendix A --- Phase 7 scenario-level contrast tables (C-N, P-N, C-P).
Appendix B --- secondary null experiment pair-level table. Appendix C ---
system-enforcement property.

Compiled length: **15 pages** including references and all three appendices
(`pdflatex` + `bibtex`, TeX Live 2026): 0 undefined citations, 0 undefined
references, 0 overfull `\hbox`. The date is a literal
(`\date{August 2026}`, no `\today`). Build with `build_pdf.sh`, which sets
`SOURCE_DATE_EPOCH=1451606400` and `FORCE_SOURCE_DATE=1` so the PDF is
byte-reproducible (SHA-256
`a6ffb1a2812ef8b54ccf02e04f3722ef32210bad9f292a3fd8a28e53d43183b5`,
529020 bytes).

## Provenance

| item | value |
|---|---|
| Phase 7 execution source commit | `2a892c0b9a8a636055cc0c4229aebfd788738b60` |
| Phase 7 analysis implementation commit | `dc5d0767ce4bec946373bf720a37aae538ef258c` |
| Phase 7 pre-registered analysis-plan SHA-256 | `87fec92f4b71a80e10a9f6fd5dd06fade13bec11d72d41725d34a660b1e7f68d` |
| Phase 7D pre-analysis freeze manifest (self-hash) | `dad290f5b5ac460bf2d46c74facc05da7197f946ca5a0a2ed2d165c48ad1dd22` |
| Phase 7E analysis-artifact manifest (self-hash) | `dbeb7068f1fe318862ba706a788fcc7a46107168f162e0021a04437958603b19` |
| Phase 6 execution source commit | `23bf90bf379654f0afc2fadaa5a16ade30ae3439` |
| Phase 6 frozen raw-integrity manifest SHA-256 | `8310a1f9c1c1464ad1786b832deac328b8d21bf209919f1d57ba66cc1a542695` |
| Phase 6 analysis-artifact manifest SHA-256 | `db34e1bad9d770dcdf38e1d887550c2eab999ffa404c79cea936be429e540593` |
| Resolved dependency lock SHA-256 | `6b0d8279010a57be250d134ca291403061b4a8f7937fd2c93563ef9f6243fb56` |
| Environment | Python 3.12.2; `mcp==2.0.0`, `openai==3.3.1`, `anthropic==1.2.0` |

All figures are LaTeX (pgfplots) renderings of the exact frozen numbers in
`reports/phase_7e_analysis/`; no raster or vector image files are bundled.

## Files

| file | role | in source archive? |
|---|---|---|
| `main.tex` | the manuscript (LaTeX) | yes |
| `references.bib` | bibliography database (18 cited entries; web-verified, see `paper/citation_audit.md`) | yes |
| `main.bbl` | pre-generated bibliography (natbib / `plainnat`) | yes |
| `generated/p7_*.tex` | machine-generated Phase 7 table bodies, `\input`-ed by `main.tex` | yes |
| `generated/p6p7_cp.tex`, `generated/rq2_*.tex`, `generated/exec_integrity.tex`, `generated/pinned_ids.tex` | machine-generated table bodies | yes |
| `generated/p7_*_scatter.dat`, `generated/p7_*_means.dat` | machine-generated pgfplots data for the Phase 7 scenario-contrast figure | yes |
| `generated/facts.json` | machine-extracted fact digest used by the numeric audit | yes (provenance) |
| `gen_tables.py` | offline generator for `generated/*` from the frozen Phase 7E + Phase 6E.2 artifacts (no provider calls) | yes (provenance) |
| `audit_numbers.py` | offline numeric audit: manuscript vs. both frozen studies | yes (provenance) |
| `build_pdf.sh` | deterministic PDF build wrapper | no |
| `build_arxiv_tar.py` | deterministic archive builder | no |
| `README_SUBMISSION.md` | this file | no |

Packages: `geometry`, `amsmath`, `amssymb`, `graphicx`, `array`,
`booktabs`, `xcolor`, `microtype`, `url`, `caption`, `pgfplots`
(`compat=1.18`), `natbib`, `hyperref`, `lmodern`. No custom fonts, no
shell-escape, no network access, no absolute paths.

Regeneration:
`uv run python paper/arxiv/gen_tables.py` rewrites `generated/*`;
`bash paper/arxiv/build_pdf.sh` builds `main.pdf` deterministically;
`uv run python paper/arxiv/audit_numbers.py` re-verifies every manuscript
number against `reports/phase_7e_analysis/` and `reports/phase_6e_v4r1/`;
`uv run python paper/arxiv/build_arxiv_tar.py` rebuilds the archive.

## Compilation

```
pdflatex main
bibtex   main
pdflatex main
pdflatex main
```

`main.bbl` and `generated/*` are bundled. Compiled PDF:
`../arxiv_preview.pdf`.

## Deterministic source archive

`../agent-interop-bench-arxiv-v2.tar.gz` (43022 bytes, SHA-256
`5761d84acc10b78402ca9a09bb0a1ed39a376b4208fb027bdb72dde1566dca69`) is
built deterministically by `build_arxiv_tar.py` (sorted members,
`mtime=0`, mode `0444`, `uid=gid=0`, empty owner/group, gzip `mtime=0`). It
extracts and compiles with the four-command sequence above using only the
bundled `main.bbl`.

## Scope note

The only non-local component in every trial is real provider model
inference (three OpenAI GPT-5.6 models via the Responses API and Claude
Sonnet 5 via the Anthropic Messages API); the real model host is the system
under test. All MCP and A2A infrastructure is local deterministic protocol
fixtures; no production, external, or third-party MCP server or A2A agent
was contacted. Results are conditional on 10 record scenarios, three arms
(confidential / unlabeled / public), one host policy, one
`{relay_to_remote, stop}` decision surface, four model identifiers, and one
point in time. The unlabeled baseline provides **no convincing evidence**
of a confidential-header suppression effect in any model; adding
`PUBLIC - OK TO SHARE` is associated (descriptively, not causally) with
higher verbatim egress relative to the unlabeled baseline for three models.
The secondary null experiment is a **complete floor** and establishes no
resistance to cross-agent influence. The system-enforcement result is a
deterministic-gate-plus-audit **verified property**, not a model-safety
rate. No p-values, no significance tests, no bootstrap or intervals for the
Phase 7 primary, no cross-model pooling, no pooling of the two studies, no
general model-safety verdict, no provider ranking, no semantic-leakage
claim, and no priority claim on cross-protocol composition risk.

## Recommended arXiv category

Left for the submitter. `cs.CR` with a `cs.AI` cross-list is a plausible
choice (non-binding).
