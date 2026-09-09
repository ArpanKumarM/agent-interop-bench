# `paper-v2.4` — TMLR section-order patch of `paper-v2.3`

Formatting only, and only in the **anonymous TMLR derivation**.
`paper-v2.4` does **not** change any experiment, raw trial, frozen
analysis, numerical result, pre-registered rule, table, label, citation,
or scientific sentence. The public manuscript (`paper/arxiv/main_v2.*`)
is unchanged. Canonical raw data and every frozen scientific output are
byte-identical to `paper-v2.0`–`paper-v2.3`.

## What changed

Current TMLR author guidance places the appendix **after** the
references. The anonymous submission built by
`paper/tmlr/build_tmlr_tex.py` previously emitted

  main body → `\appendix` (A–D) → `\bibliography`

Now it emits the TMLR order

  main body → `\bibliography` → `\appendix` (A–D)

Only the position of the two-line bibliography block moves. `\appendix`
still immediately precedes Appendix A, so the A–D lettering, every
`\label`, every `\ref`/`\cite`, and all appendix content are unchanged.
The public `main_v2.tex` keeps its existing appendix-before-references
layout (valid for arXiv); the reorder is applied only in the TMLR
derivation step.

Files touched (all under `paper/tmlr/`):
- `build_tmlr_tex.py` — split the sliced body at `\appendix`; emit
  bibliography between the main body and the appendix.
- `main_tmlr.tex`, `TRANSFORM_LOG.txt` — regenerated.
- `diff_scientific_content.py` — the public-vs-anonymous equality checker
  sliced the anon body at `\bibliography{`; it now excises the bib block
  wherever it occurs and compares up to `\end{document}`, so the anon
  appendix is included on both sides. Result: `SCIENTIFIC-CONTENT DIFF:
  identical` (1548 numeric/hash tokens, 146 table rows, 55 headings,
  abstract byte-identical).

## Verification summary

- anonymous TMLR PDF: 19 pages, deterministic (passes 4 and 5 byte-identical
  to pass 3); zero undefined `\ref`/`\cite`; all 16 refs and 20 cites
  resolve.
- `ANON_RAW_SCIENTIFIC_EQUIVALENCE: PASS`.
- anonymity scan on the rebuilt supplementary ZIP: zero identifying hits,
  zero known-commit SHAs, PDF `/Author` and `/Title` empty,
  `source_commit_sha == [redacted-for-double-blind]`, `MANIFEST.sha256`
  551/551 OK.
- numeric audits (`audit_numbers`, `audit_phase8_numbers`,
  `audit_phase9_numbers`): pass.

## Archive

- file: `agent-interop-bench-paper-v2.4.tar.gz`
- built by `scripts/build_paper_v2_release.py` (`--check` re-derives the
  archive SHA-256).
- SHA-256, byte size, member count, and the exact release commit are in
  the **Verification** section of this release page.
