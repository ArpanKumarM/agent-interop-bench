r"""Build the minimal arXiv upload archive: ONLY the files arXiv needs to
compile ``main.tex``, nothing else.

Traced dependencies of ``main.tex``:
  * main.tex, references.bib, main.bbl
  * the 10 generated/*.tex fragments \input by main.tex
  * the 4 generated/*.dat pgfplots data files loaded by \addplot table{...}
No custom .sty/.cls (all packages are standard TeX Live), no figures
(the only figure is drawn inline with pgfplots), no PDF, no scripts.

Byte-reproducible: members sorted by name, ``mtime=0``, mode ``0444``,
``uid=gid=0``, empty owner/group names, gzip ``mtime=0`` with no embedded
filename.

Run:  uv run python paper/arxiv/build_arxiv_submission.py
      uv run python paper/arxiv/build_arxiv_submission.py --check
"""

from __future__ import annotations

import gzip
import hashlib
import io
import re
import sys
import tarfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "arxiv-submission.tar.gz"

_ALWAYS = ["main.tex", "references.bib", "main.bbl"]


def _members() -> list[str]:
    tex = (HERE / "main.tex").read_text()
    inputs = sorted(set(re.findall(r"\\input\{(generated/[^}]+)\}", tex)))
    data = sorted(set(re.findall(r"table \{(generated/[^}]+)\}", tex)))
    members = _ALWAYS + inputs + data
    missing = [m for m in members if not (HERE / m).is_file()]
    if missing:
        raise SystemExit(f"missing compile inputs: {missing}")
    # sanity: main.tex must not pull in figures or custom styles
    if "\\includegraphics" in tex:
        raise SystemExit("main.tex uses \\includegraphics; add the image to the archive")
    return sorted(members)


def _archive_bytes(members: list[str]) -> bytes:
    raw = io.BytesIO()
    with tarfile.open(fileobj=raw, mode="w", format=tarfile.USTAR_FORMAT) as tar:
        for name in sorted(members):
            data = (HERE / name).read_bytes()
            info = tarfile.TarInfo(name)
            info.size = len(data)
            info.mtime = 0
            info.mode = 0o444
            info.uid = info.gid = 0
            info.uname = info.gname = ""
            info.type = tarfile.REGTYPE
            tar.addfile(info, io.BytesIO(data))
    out = io.BytesIO()
    with gzip.GzipFile(filename="", fileobj=out, mode="wb", mtime=0) as gz:
        gz.write(raw.getvalue())
    return out.getvalue()


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    members = _members()
    blob = _archive_bytes(members)
    sha = hashlib.sha256(blob).hexdigest()
    if "--check" in args:
        if not OUT.is_file():
            print(f"MISSING {OUT}", file=sys.stderr)
            return 1
        on_disk = hashlib.sha256(OUT.read_bytes()).hexdigest()
        ok = on_disk == sha
        print(f"{'OK  ' if ok else 'FAIL'} {OUT.name}  rebuilt={sha}  on_disk={on_disk}")
        return 0 if ok else 1
    OUT.write_bytes(blob)
    print(f"wrote {OUT.relative_to(HERE.parents[1])} ({len(blob)} bytes)  sha256 {sha}")
    print("contents (" + str(len(members)) + " files):")
    for m in members:
        print(f"  {m}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
