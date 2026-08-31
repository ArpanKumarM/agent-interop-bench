# arXiv submission package — MCP--A2A cross-protocol composition study (v4r1)

Self-contained arXiv-ready LaTeX source. Renders `paper/main.md` as a
conventional single-column research paper. **Manuscript preparation made
zero provider calls and changed no raw observation, stimulus, schedule,
model, parameter, outcome definition, or analysis plan.** The prior Phase 4B
pilot is historical evidence only; the frozen **v4r1 Phase 6 study** is the
confirmatory empirical core, and this manuscript is rebuilt entirely from
it.

## Title

> Cross-Protocol Information Flow and Action Containment in MCP--A2A Agent
> Composition: A Controlled Multi-Model Study

## Section structure

1. Abstract
2. Introduction
3. Background and System Model
4. Related Work
5. Experimental Method
6. Results (6.1 RQ1 information flow, 6.2 RQ2 behavioral influence,
   6.3 RQ3 containment invariant)
7. Discussion
8. Threats to Validity and Limitations
9. Reproducibility (execution/integrity table, execution-deviation
   paragraph, pinned-identifier table)
10. Conclusion

Appendix A --- RQ1 pair-level table. Appendix B --- RQ2 pair-level table.

Compiled length: **13 pages** including references and both appendices
(`pdflatex` + `bibtex`, TeX Live 2026): 0 undefined citations, 0 undefined
references, 0 overfull `\hbox`, 4 benign underfull `\hbox`, 0 missing
glyphs, 0 fatal warnings.

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
| `references.bib` | bibliography database (18 cited entries) | yes |
| `main.bbl` | pre-generated bibliography (natbib / `plainnat`) | yes |
| `README_SUBMISSION.md` | this file | no (not a compile input) |

Packages: `geometry`, `amsmath`, `amssymb`, `graphicx`, `array`, `booktabs`,
`multirow`, `xcolor`, `microtype`, `url`, `caption`, `pgfplots`
(`compat=1.18`, `groupplots`), `natbib`, `hyperref`, `lmodern`. No custom
fonts, no shell-escape, no network access, no absolute paths.

## Compilation

```
pdflatex main
bibtex   main
pdflatex main
pdflatex main
```

`main.bbl` is bundled. Compiled PDF: `../arxiv_preview.pdf`.

## Deterministic source archive

`../agent-interop-bench-arxiv-v2.tar.gz` contains exactly `main.tex`,
`references.bib`, `main.bbl`, built deterministically (sorted members,
`mtime=0`, mode `0444`, `uid=gid=0`, gzip `mtime=0`).

## Scope note

The only non-local component in every trial is real provider model
inference (three OpenAI GPT-5.6 models via the Responses API and Claude
Sonnet 5 via the Anthropic Messages API); the real model host is the system
under test. All MCP and A2A infrastructure is local deterministic protocol
fixtures; no production, external, or third-party MCP server or A2A agent was
contacted. Results are conditional on 40 fixed overlays (10 matched pairs
per experiment), one host policy, one 12-tool model-visible surface, four
model identifiers, and one point in time. No p-values, no significance
tests, no general model-safety verdict, no provider ranking, no
semantic-leakage claim, and no priority claim on cross-protocol composition
risk or MCP+A2A pivoting --- prior articulation by AgentRFC, an IETF
Internet-Draft, and a formal composition analysis is acknowledged in the
Related Work section.

## Recommended arXiv category

Left for the submitter. Subject matter is agent/LLM security evaluation;
`cs.CR` with a `cs.AI` cross-list is a plausible choice (non-binding).
