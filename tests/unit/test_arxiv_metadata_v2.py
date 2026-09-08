"""Same checks as test_arxiv_metadata.py, for the v2 metadata file
(paper/arxiv/ARXIV_METADATA_v2.txt): the delimited abstract block must be
pure ASCII and within arXiv's 1920-character hard limit, the title must be
ASCII and match the current manuscript, and the withdrawn "dominates"
framing must not have crept back in.
"""

from __future__ import annotations

import re
from pathlib import Path

META = Path(__file__).resolve().parents[2] / "paper" / "arxiv" / "ARXIV_METADATA_v2.txt"
_ARXIV_HARD_LIMIT = 1920


def _abstract() -> str:
    text = META.read_text()
    m = re.search(r"hard limit 1920 characters\)\n-+\n(.*?)\n-+\nEND ABSTRACT", text, re.S)
    assert m, "ARXIV_METADATA_v2.txt: could not locate the delimited abstract block"
    return re.sub(r"\s*\n\s*", " ", m.group(1)).strip()


def _title() -> str:
    m = re.search(r"\nTitle:\n(.+?)\n\n", META.read_text(), re.S)
    assert m, "ARXIV_METADATA_v2.txt: could not locate the Title block"
    return re.sub(r"\s*\n\s*", " ", m.group(1)).strip()


def test_v2_metadata_file_exists():
    assert META.is_file(), f"missing {META}"


def test_v2_abstract_ascii_and_within_limit():
    ab = _abstract()
    assert ab.isascii(), "v2 metadata abstract contains non-ASCII characters"
    assert len(ab) <= _ARXIV_HARD_LIMIT, (
        f"v2 metadata abstract is {len(ab)} chars, over the {_ARXIV_HARD_LIMIT} hard limit"
    )


def test_v2_abstract_is_substantive_and_current():
    ab = _abstract()
    assert len(ab) >= 800, f"v2 metadata abstract is only {len(ab)} chars"
    assert "MCP-to-A2A" in ab
    assert "stopping rule" in ab
    assert "F3" in ab and "exploratory" in ab
    # the withdrawn framing must not be back
    low = ab.lower()
    assert "task framing dominates" not in low
    assert "framing dominated them here" not in low


def test_v2_title_ascii_and_current():
    title = _title()
    assert title.isascii(), "v2 metadata title contains non-ASCII characters"
    assert title.startswith("Whether a Sensitivity-Label Effect Can Be Measured at an MCP-to-A2A")
    assert "Dominates" not in title
