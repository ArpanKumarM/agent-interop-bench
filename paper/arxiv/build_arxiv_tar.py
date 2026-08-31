r"""Build the deterministic arXiv source archive.

Byte-reproducible: members sorted by name, ``mtime=0``, mode ``0444``,
``uid=gid=0``, empty owner/group names, gzip ``mtime=0``. Run after
``gen_tables.py`` and a full ``pdflatex``/``bibtex`` cycle so ``main.bbl`` and
``generated/*`` are current.

Run:  uv run python paper/arxiv/build_arxiv_tar.py
"""

from __future__ import annotations

import gzip
import io
import tarfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE.parent / "agent-interop-bench-arxiv-v2.tar.gz"

# Compile inputs plus the offline table generator and its fact digest, so the
# archive is both directly compilable and self-documenting.
MEMBERS = [
    "main.tex",
    "references.bib",
    "main.bbl",
    "gen_tables.py",
    "generated/facts.json",
    "generated/rq1_model.tex",
    "generated/rq1_pairs.tex",
    "generated/rq1_diag.tex",
    "generated/rq2_model.tex",
    "generated/rq2_diag.tex",
    "generated/exec_integrity.tex",
    "generated/pinned_ids.tex",
    "generated/rq1_pair_scatter.dat",
    "generated/rq1_pair_means.dat",
]


def main() -> None:
    raw = io.BytesIO()
    with tarfile.open(fileobj=raw, mode="w", format=tarfile.USTAR_FORMAT) as tar:
        for name in sorted(MEMBERS):
            data = (HERE / name).read_bytes()
            info = tarfile.TarInfo(name)
            info.size = len(data)
            info.mtime = 0
            info.mode = 0o444
            info.uid = info.gid = 0
            info.uname = info.gname = ""
            info.type = tarfile.REGTYPE
            tar.addfile(info, io.BytesIO(data))
    with open(OUT, "wb") as fh, gzip.GzipFile(fileobj=fh, mode="wb", mtime=0) as gz:
        gz.write(raw.getvalue())
    print(f"wrote {OUT.relative_to(HERE.parents[1])} ({OUT.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
