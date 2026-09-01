"""The proposed arXiv metadata abstract must be pure ASCII and within
arXiv's hard 1920-character limit (arXiv rejects longer abstracts).

The exact abstract text is the block between the dashed
``hard limit 1920 characters)`` header line and the dashed
``END ABSTRACT`` line in ``paper/arxiv/ARXIV_METADATA.txt``. arXiv reflows
the abstract as a single block, so the check normalises internal newlines
to single spaces before measuring.
"""

from __future__ import annotations

import re
from pathlib import Path

META = Path(__file__).resolve().parents[2] / "paper" / "arxiv" / "ARXIV_METADATA.txt"
_ARXIV_HARD_LIMIT = 1920


def _abstract() -> str:
    text = META.read_text()
    m = re.search(
        r"hard limit 1920 characters\)\n-+\n(.*?)\n-+\nEND ABSTRACT",
        text,
        re.S,
    )
    assert m, "ARXIV_METADATA.txt: could not locate the delimited abstract block"
    return re.sub(r"\s*\n\s*", " ", m.group(1)).strip()


def test_arxiv_metadata_file_exists():
    assert META.is_file(), f"missing {META}"


def test_arxiv_abstract_is_pure_ascii():
    ab = _abstract()
    assert ab.isascii(), "arXiv metadata abstract contains non-ASCII characters"


def test_arxiv_abstract_within_hard_limit():
    ab = _abstract()
    assert len(ab) <= _ARXIV_HARD_LIMIT, (
        f"arXiv metadata abstract is {len(ab)} characters, over the "
        f"{_ARXIV_HARD_LIMIT}-character hard limit"
    )


def test_arxiv_abstract_is_substantive():
    ab = _abstract()
    # a real abstract, not a stub; and it must carry the headline framing
    assert len(ab) >= 800, f"arXiv metadata abstract is only {len(ab)} characters"
    assert "MCP-to-A2A" in ab
    assert "480 trials" in ab
    assert "does not show that confidential labels lack a protective effect" in ab


def test_arxiv_title_is_ascii_safe():
    text = META.read_text()
    m = re.search(r"\nTitle:\n(.+?)\n\n", text, re.S)
    assert m, "ARXIV_METADATA.txt: could not locate the Title block"
    title = re.sub(r"\s*\n\s*", " ", m.group(1)).strip()
    assert title.isascii(), "arXiv metadata title contains non-ASCII characters"
    assert title.startswith("Public-Sharing Labels and Verbatim Field Egress in an MCP-to-A2A")
