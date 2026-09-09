r"""Programmatic public-vs-anonymous scientific-content equality check.

Compares paper/arxiv/main_v2.tex (public) with paper/tmlr/main_tmlr.tex
(anonymized TMLR submission) and asserts that the scientific content is
identical. Reports any substantive difference.

"Scientific content" here = the ordered multiset of every numeric token,
every table data row, every section / subsection / paragraph heading, and
the abstract text -- after removing exactly the parts that anonymization
and TMLR formatting are *allowed* to change:

  * the whole preamble (documentclass / packages / title / author);
  * the "DRAFT v2 / revision of arXiv" front-matter note (public only);
  * the "Public artifact" paragraph vs the "Reproducibility artifacts"
    paragraph (each dropped from its side);
  * git commit SHAs (kept as content in public, relabelled in anon);
  * the bibliography style line.

The two secondary Phase 7 tables are relocated (body -> appendix) in the
anon version but not edited, so headings are compared as a *set* and
numbers / rows as a *multiset*.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PUB = (ROOT / "paper" / "arxiv" / "main_v2.tex").read_text()
ANON = (ROOT / "paper" / "tmlr" / "main_tmlr.tex").read_text()

COMMIT_SHAS = {
    "32a76bfa19c3240bd87011fe9a7e41b3ced1a511",
    "a347a8b3c2b29b77586a113fdabf8bd310e92e85",
    "e8fd793940458a88f5fd122a7065737bf4a109c5",
    "c64a32d73e9d4b52fb03d4b6a91c8d3fa05f3bfe",
    "ffaae077e791148bb05a039749d835d308ce85a1",
    "74ba1cdd545ce9f32850bd4ba107e45af952dbb3",
    "d06a88b0eebd6f4452ab09ccbc6fe5c2a4907631",
    "89c0542",
}


def _body(tex: str) -> str:
    s = tex[tex.index(r"\begin{abstract}") :]
    s = s[: s.index(r"\bibliography{")]
    # drop the two artifact paragraphs (one per side) up to the blank line
    for para in (r"\paragraph{Public artifact.}", r"\paragraph{Reproducibility artifacts.}"):
        if para in s:
            i = s.index(para)
            j = s.index("\n\n", i)
            s = s[:i] + s[j:]
    # neutralise commit SHAs and their relabelled placeholder, then any
    # emptied \code{} / \emph{} shell left behind on either side
    for sha in COMMIT_SHAS:
        s = s.replace("\\code{" + sha + "}", "")
        s = s.replace(sha, "")
    s = s.replace(r"\emph{[commit; see supplementary material]}", "")
    s = s.replace(r"\code{}", "")
    return s


def _strip_headings(s: str) -> str:
    # heading text is compared separately by _headings(); the compression
    # pass legitimately adds one new appendix heading, so its words/digits
    # must not enter the numeric multiset.
    return re.sub(r"\\(?:section|subsection|paragraph)\{[^}]*\}", " ", s)


def _numbers(s: str) -> list[str]:
    s = _strip_headings(s)
    # 64-hex content hashes must survive identically; keep them, plus every
    # signed decimal / integer.
    hexes = re.findall(r"\b[0-9a-f]{64}\b", s)
    nums = re.findall(r"[+-]?\d+(?:\.\d+)?", re.sub(r"\b[0-9a-f]{64}\b", " ", s))
    return sorted(hexes) + sorted(nums, key=lambda x: (len(x), x))


def _headings(s: str) -> set[str]:
    return set(re.findall(r"\\(?:sub)?section\{([^}]*)\}", s)) | set(
        re.findall(r"\\paragraph\{([^}]*)\}", s)
    )


def _table_rows(s: str) -> list[str]:
    rows = []
    for blk in re.findall(r"\\begin\{tabular\}.*?\\end\{tabular\}", s, re.DOTALL):
        for line in blk.splitlines():
            if "&" in line and "\\\\" in line:
                rows.append(" ".join(line.replace("\\\\", "").split()))
    return sorted(rows)


def _abstract(s: str) -> str:
    a = s[s.index(r"\begin{abstract}") + len(r"\begin{abstract}") : s.index(r"\end{abstract}")]
    return " ".join(a.split())


def main() -> int:
    pb, ab = _body(PUB), _body(ANON)
    problems: list[str] = []

    pn, an = _numbers(pb), _numbers(ab)
    if pn != an:
        from collections import Counter

        cp, ca = Counter(pn), Counter(an)
        diff = {k: (cp[k], ca[k]) for k in set(cp) | set(ca) if cp[k] != ca[k]}
        problems.append(
            f"numeric/multiset differs: {len(pn)} vs {len(an)} tokens; "
            f"per-token (public,anon): {diff}"
        )

    ph, ah = _headings(pb), _headings(ab)
    extra_anon = ah - ph
    missing_anon = ph - ah
    allowed_new = {"Phase 7 secondary and cross-phase tables", "Reproducibility artifacts."}
    if (extra_anon - allowed_new) or missing_anon:
        problems.append(
            f"headings differ:\n    unexpected new in anon: {sorted(extra_anon - allowed_new)}\n"
            f"    missing from anon      : {sorted(missing_anon)}"
        )

    pr, ar = _table_rows(pb), _table_rows(ab)
    if pr != ar:
        problems.append(
            f"table data rows differ: {len(pr)} vs {len(ar)}\n"
            f"    only public: {sorted(set(pr) - set(ar))[:10]}\n"
            f"    only anon  : {sorted(set(ar) - set(pr))[:10]}"
        )

    if _abstract(pb) != _abstract(ab):
        problems.append("ABSTRACT TEXT DIFFERS")

    if problems:
        print("SCIENTIFIC-CONTENT DIFF: FAIL", file=sys.stderr)
        for p in problems:
            print("  - " + p, file=sys.stderr)
        return 1

    print("SCIENTIFIC-CONTENT DIFF: identical")
    print(f"  numeric/hash tokens compared : {len(pn)}")
    print(f"  section/paragraph headings   : {len(ph)} (anon adds only {sorted(allowed_new)})")
    print(f"  table data rows              : {len(pr)}")
    print("  abstract text                : byte-identical (whitespace-normalized)")
    print("  allowed differences          : preamble, front-matter arXiv note,")
    print("     Public-artifact vs Reproducibility-artifacts paragraph, commit-SHA")
    print("     relabelling, bib style, and relocation of tab:p7diag + tab:xphase.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
