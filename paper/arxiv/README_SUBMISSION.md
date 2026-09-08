# arXiv submission notes (v2)

Self-contained arXiv-ready LaTeX source for **"Whether a Sensitivity-Label
Effect Can Be Measured at an MCP-to-A2A Handoff Depends on the Task
Framing: A Pre-Registered Sweep"** — submitted as **v2** of
arXiv:2609.01693 (v1: *"Public-Sharing Labels and Verbatim Field Egress in
an MCP-to-A2A Agent Configuration: A Controlled Multi-Model Study"*).
Proposed metadata: [`ARXIV_METADATA_v2.txt`](ARXIV_METADATA_v2.txt).

## What the paper is

A **controlled behavioral measurement at one concrete handoff** — an
MCP-result → A2A-message boundary — **not** a general MCP/A2A security
benchmark. A real-model host reads a local record over MCP, then sends a
message to a remote A2A agent; the outcome is verbatim occurrence of any
of six substantive record values in the outbound message
(`any_sensitive_field_egress`, an exact-substring L0 scorer, no LLM
judge).

## Scientific arc (Phase 6 → 7 → 8)

- **Phase 6** (two arms: `CONFIDENTIAL` vs. `PUBLIC - OK TO SHARE`, 640
  trials): a large confidential-vs-public contrast, but both arms carry
  an active label so it is unattributable.
- **Phase 7** (adds an unlabeled baseline, 480 trials): three of four
  models floor to 0/40 on both the confidential and unlabeled arms — the
  confidentiality contrast is *unmeasured*, not measured-and-absent.
- **Phase 8** (two pre-registered pilot rounds, 576 trials each, four
  arms, n = 12 per cell): a six-framing sweep seeking a wording whose
  unlabeled-arm rate lands in `[0.25, 0.70]` for ≥ 3/4 models. **No
  framing met the rule.** The pre-registered stopping rule fired after
  round two.

**Everything Phase 8 reports is pilot-scale.** The ~**13,184**-trial main
study (S8-A…D) was **not executed**. At n = 12, framing **F3 remains
unresolved** under a Wilson-interval analysis (three of four models' 95%
CIs overlap the acceptance band). The Phase 8 **public-arm** contrast
(§6.4 of the manuscript) was collected outside the frozen pilot analysis
plan and is reported as **exploratory** — one model, three framings.
**Phase 8 round-one raw trial bytes were overwritten and are
unrecoverable**; the recorded hashes survive, round two is byte-pinned
and recomputable from raw. See `../../PROVENANCE.md` §5,
`../../REPRODUCIBILITY.md` §7.

## Build (v2)

```
bash paper/arxiv/build_pdf_v2.sh                  # deterministic PDF (SOURCE_DATE_EPOCH)
uv run python paper/arxiv/audit_phase8_numbers.py # numeric audit + posting gates
uv run python paper/arxiv/audit_numbers.py        # v1 numeric audit (unchanged, still passes)
```

`main_v2.tex`'s tables are written directly (booktabs), not `\input`-ed
from generated fragments; `audit_phase8_numbers.py` parses the `.tex` and
asserts every table and quoted figure matches the frozen source and the
Markdown (`../main_v2.md`).

Compiled PDF: **15 pages**, TeX Live, `pdflatex` + `bibtex`; 0 undefined
citations, 0 undefined references, 0 overfull `\hbox`. The date is a
literal `\date{...}` (no `\today`); with `SOURCE_DATE_EPOCH=1451606400`
the PDF is byte-reproducible. **Before submission:** set the real
submission date in `\date{}` and remove the `% TODO` comment, and
substitute the `paper-v2.0` release URL into §9 (both clear posting gates
in `audit_phase8_numbers.py`).

## Minimal upload archive (v2)

For arXiv, `main_v2.tex` needs only:

| file | why |
|---|---|
| `main_v2.tex` | the manuscript |
| `references_v2.bib` | bibliography database for `\bibliography{references_v2}` |
| `main_v2.bbl` | pre-generated bibliography (arXiv compiles from `.bbl`) |

Packages, all standard TeX Live, no bundled `.sty`/`.cls`: `fontenc`,
`inputenc`, `lmodern`, `geometry`, `amsmath`, `amssymb`, `array`,
`booktabs`, `microtype`, `url`, `caption`, `float`, `natbib`, `hyperref`.
No figures, no `\includegraphics`, no `pgfplots`, no shell-escape, no
network access, no absolute paths.

Clean-extraction compile:

```
pdflatex main_v2
bibtex   main_v2
pdflatex main_v2
pdflatex main_v2
```

## v1 archive (historical)

The v1 submission (`main.tex`, `gen_tables.py`-generated fragments,
`arxiv-submission.tar.gz`, `ARXIV_METADATA.txt`, `build_pdf.sh`) is
unchanged and still builds. v1 is 12 pages, `\date{August 2026}`. v2 does
not use the `gen_tables.py` fragment pipeline.
