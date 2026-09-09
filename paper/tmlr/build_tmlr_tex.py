r"""Derive the anonymized TMLR submission source from the public
manuscript, deterministically.

Input : paper/arxiv/main_v2.tex, paper/arxiv/references_v2.bib
Output: paper/tmlr/main_tmlr.tex        (official tmlr.sty, anonymous author)
        paper/tmlr/references_tmlr.bib  (identity-bearing self-cite removed)
        paper/tmlr/TRANSFORM_LOG.txt    (every substitution, for the
                                         public-vs-anonymous scientific diff)

The scientific text -- every sentence, number, table, CI, limitation, and
the central claim -- is carried through byte-for-byte. Only these change:
  1. preamble: article+geometry+custom title/author  ->  \usepackage{tmlr}
     (anonymous author block rendered by the class), no arXiv-revision note;
  2. the "Public artifact" paragraph (identifying repo + release URLs)
     -> a neutral "Reproducibility artifacts ... anonymized supplementary
     material" paragraph;
  3. git commit SHAs in Appendix B -> "[commit; see supplementary
     material]" (content SHA-256 hashes are kept -- they verify the data
     and do not index to an account);
  4. \bibliographystyle{plainnat} -> {tmlr}; the self-citation bib entry
     is dropped from references_tmlr.bib.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC_TEX = ROOT / "paper" / "arxiv" / "main_v2.tex"
SRC_BIB = ROOT / "paper" / "arxiv" / "references_v2.bib"
OUT_TEX = ROOT / "paper" / "tmlr" / "main_tmlr.tex"
OUT_BIB = ROOT / "paper" / "tmlr" / "references_tmlr.bib"
LOG = ROOT / "paper" / "tmlr" / "TRANSFORM_LOG.txt"

TITLE = (
    "Measuring Sensitivity-Label Effects at an MCP-to-A2A Handoff: \\\\ "
    "Baseline Saturation and Directional Headroom"
)

# Required TMLR first-page disclosure of generative-AI use. Anonymous;
# reflects the actual workflow (AI used for code, manuscript drafting, and
# procedure critique -- not merely copyediting).
LLM_DISCLOSURE = (
    "Generative AI tools (ChatGPT and Claude) were used during development "
    "for code drafting and debugging, for drafting and editing the "
    "manuscript text, and for critique of the experimental, statistical, "
    "and reproducibility procedures. The authors reviewed and approved the "
    "resulting design decisions, verified the executed experiments and "
    "analyses against deterministic audits, and take responsibility for the "
    "manuscript and its claims."
)

PREAMBLE = r"""\documentclass[10pt]{article}
% Anonymized TMLR submission. Derived from the public manuscript by
% paper/tmlr/build_tmlr_tex.py -- scientific content is identical; see
% paper/tmlr/TRANSFORM_LOG.txt for the exact anonymization substitutions.
\usepackage{tmlr}          % no [accepted]/[preprint] => double-blind anonymous
\usepackage{amsmath}
\usepackage{amssymb}
\usepackage{array}
\usepackage{booktabs}
\usepackage{microtype}
\usepackage{float}
\usepackage{hyperref}
\usepackage{url}

\newcommand{\code}[1]{\texttt{\detokenize{#1}}}

% unmarked first-page footnote (no in-text symbol, no footnote number)
\newcommand{\blfootnote}[1]{%
  \begingroup
    \renewcommand\thefootnote{}\footnote{#1}%
    \addtocounter{footnote}{-1}%
  \endgroup
}

\title{__TITLE__}

% Authors must not appear in the submitted version (tmlr renders an
% anonymous block while the [accepted]/[preprint] options are absent).
\author{\name Anonymous authors \\ \addr Paper under double-blind review}

\begin{document}
\maketitle
\blfootnote{__LLM_DISCLOSURE__}
""".replace("__TITLE__", TITLE).replace("__LLM_DISCLOSURE__", LLM_DISCLOSURE)

ANON_ARTIFACT_PARA = r"""\paragraph{Reproducibility artifacts.}
The code, the frozen harness, all byte-pinned raw traces, the Phase~9
frozen analysis output, and an offline reproduction guide
(\code{REPRODUCE.md}) are provided as anonymized supplementary material;
the normal reproduction path needs no API credentials. The freeze
commits, content hashes, and per-model raw \code{trials.jsonl} SHA-256s
are in Appendix~\ref{app:pinned}. Phase~8 round-one raw traces were
overwritten before the \code{public} arm was analyzed
(\S\ref{subsec:publicarm}) and are unrecoverable; Phase~9 collected a
fresh \code{public} arm at F3 over 64 new scenarios."""

COMMIT_SHAS = [
    "32a76bfa19c3240bd87011fe9a7e41b3ced1a511",
    "a347a8b3c2b29b77586a113fdabf8bd310e92e85",
    "e8fd793940458a88f5fd122a7065737bf4a109c5",
    "c64a32d73e9d4b52fb03d4b6a91c8d3fa05f3bfe",
    "ffaae077e791148bb05a039749d835d308ce85a1",
    "74ba1cdd545ce9f32850bd4ba107e45af952dbb3",
    "d06a88b0eebd6f4452ab09ccbc6fe5c2a4907631",
    "89c0542",
]


def main() -> int:
    tex = SRC_TEX.read_text()
    log: list[str] = []

    # --- 1. slice body: \begin{abstract} .. up to the final bibliography ---
    m0 = tex.index(r"\begin{abstract}")
    m1 = tex.index(r"\bibliographystyle{plainnat}")
    body = tex[m0:m1].rstrip()
    log.append(f"[slice] kept chars {m0}..{m1} of {SRC_TEX.name} "
               r"(\begin{abstract} .. before \bibliographystyle)")

    # --- 2. Public artifact -> anonymized paragraph ---
    pa = body.index(r"\paragraph{Public artifact.}")
    pa_end = body.index("\n\n", pa)
    old = body[pa:pa_end]
    body = body[:pa] + ANON_ARTIFACT_PARA + body[pa_end:]
    log.append("[sub] Public-artifact paragraph replaced:")
    log.append("  - removed: " + " ".join(old.split()))
    log.append("  + added:   " + " ".join(ANON_ARTIFACT_PARA.split()))

    # --- 3. git commit SHAs -> neutral label ---
    for sha in COMMIT_SHAS:
        tok = "\\code{" + sha + "}"
        n = body.count(tok)
        if n:
            body = body.replace(tok, r"\emph{[commit; see supplementary material]}")
            log.append(f"[sub] commit SHA {sha[:12]}... relabelled ({n}x)")

    # --- 3b. compression: move the two secondary Phase 7 tables
    #        (secondary-diagnostics + cross-phase comparison) and their
    #        short paragraphs out of the body into the Phase 7 appendix.
    #        No sentence is deleted or reworded; only relocated. ---
    b0 = body.index(r"\paragraph{Secondary diagnostics.}")
    xph = body.index(r"\label{tab:xphase}", b0)
    b1 = body.index(r"\end{table}", xph) + len(r"\end{table}")
    moved = body[b0:b1].strip()
    body = (body[:b0].rstrip() + "\n\n" + body[b1:].lstrip()).replace("\n\n\n", "\n\n")
    anchor = body.index(r"\section{Phase 7 scenario-level contrast tables}")
    body = (
        body[:anchor]
        + "\\section{Phase 7 secondary and cross-phase tables}\n\n"
        + moved
        + "\n\n"
        + body[anchor:]
    )
    log.append(
        "[move] section 5.2 'Secondary diagnostics' + 'Cross-phase reproducibility "
        "check' paragraphs and tables tab:p7diag / tab:xphase relocated verbatim "
        "to a new appendix section 'Phase 7 secondary and cross-phase tables' "
        "(main-body compression; no text changed)"
    )

    # belt: no identifying URL / name / arXiv id survives in the body
    for bad in ("ArpanKumarM", "Mahapatra", "arpan.arpan", "arXiv:2609.01693",
                "github.com/ArpanKumarM"):
        if bad in body:
            raise SystemExit(f"anonymization FAILED: {bad!r} still in TMLR body")
    # any bare 40-hex still present?
    leftover = sorted(set(re.findall(r"\\code\{([0-9a-f]{40})\}", body)))
    if leftover:
        raise SystemExit(f"anonymization FAILED: commit-shaped hashes remain: {leftover}")

    # --- 3c. TMLR section order: references must precede the appendix.
    #        The public manuscript places \appendix before the bibliography;
    #        for the TMLR submission we split the sliced body at \appendix and
    #        emit  main body -> \bibliography -> \appendix ... .  Only the
    #        position of the bibliography block changes; no appendix content
    #        is moved, reworded, or renumbered (\appendix still immediately
    #        precedes Appendix A, so lettering A..E is unchanged). ---
    ap = body.index("\\appendix")
    if body.count("\\appendix") != 1:
        raise SystemExit("expected exactly one \\appendix in the sliced body")
    main_body = body[:ap].rstrip()
    appendix = body[ap:].strip()
    appendix = re.sub(r"\s*\\clearpage\s*$", "\n", appendix)
    log.append(
        "[order] TMLR format: bibliography emitted between the main body and "
        "\\appendix (public source keeps \\appendix before the bibliography); "
        "appendix content, labels, and A--D lettering unchanged"
    )

    # --- 4. assemble: main body -> references -> appendix -> end ---
    out = (
        PREAMBLE
        + "\n"
        + main_body
        + "\n\n"
        + "\\bibliographystyle{tmlr}\n\\bibliography{references_tmlr}\n\n"
        + appendix
        + "\n\n\\end{document}\n"
    )
    OUT_TEX.write_text(out)

    # --- references: drop the identity-bearing self-citation entry ---
    bib = SRC_BIB.read_text()
    entries = re.split(r"(?=^@)", bib, flags=re.MULTILINE)
    kept, dropped = [], []
    for e in entries:
        key = re.match(r"@\w+\{([^,]+),", e.strip())
        if key and key.group(1).strip() == "mahapatra2026v1":
            dropped.append(key.group(1).strip())
            continue
        kept.append(e)
    OUT_BIB.write_text("".join(kept))
    log.append(f"[bib] dropped {dropped or 'nothing'} from references_tmlr.bib "
               "(no \\cite to it in the anonymized body)")

    LOG.write_text("\n".join(log) + "\n")
    print(f"wrote {OUT_TEX.relative_to(ROOT)}  ({len(out):,} bytes)")
    print(f"wrote {OUT_BIB.relative_to(ROOT)}")
    print(f"wrote {LOG.relative_to(ROOT)}  ({len(log)} lines)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
