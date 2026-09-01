r"""Build the deterministic public reproducibility artifact bundle for the
paper release (tag ``paper-v1.0``).

The bundle is the *minimum sufficient* set of frozen artifacts to verify
the raw-data hashes, re-run the frozen offline analysis, and regenerate
every manuscript number -- nothing else from ``reports/``. It is NOT the
GitHub repository and it is NOT the arXiv source archive.

Byte-reproducible: members sorted by name, ``mtime=0``, mode ``0444``,
``uid=gid=0``, empty owner/group, gzip ``mtime=0`` with no embedded
filename. An in-bundle ``MANIFEST.sha256`` lists every member.

Run:  uv run python scripts/build_paper_release.py
      uv run python scripts/build_paper_release.py --check
"""

from __future__ import annotations

import gzip
import hashlib
import io
import sys
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "dist" / "agent-interop-bench-paper-v1.0-artifacts.tar.gz"
BUNDLE_PREFIX = "agent-interop-bench-paper-v1.0-artifacts"

# Directory trees copied whole (frozen, self-consistent, manifest-covered).
_TREES = [
    "reports/_phase7d_preanalysis_freeze",  # Phase 7 frozen raw + pre-analysis integrity
    "reports/phase_7e_analysis",  # Phase 7 analysis artifacts
    "reports/phase_7e1_interpretation",  # Phase 7E.1 interpretive clarification
    "reports/phase_6e_v4r1",  # Phase 6 analysis (comparison / RQ2 / enforcement)
    "reports/_phase6d_v4r1_integrity",  # Phase 6 raw-integrity package
    "reports/experiments/phase-7a-confirmatory-v1-sol",
    "reports/experiments/phase-7a-confirmatory-v1-terra",
    "reports/experiments/phase-7a-confirmatory-v1-luna",
    "reports/experiments/phase-7a-confirmatory-v1-claude",
    "reports/experiments/phase-6b-confirmatory-v4r1-sol",
    "reports/experiments/phase-6b-confirmatory-v4r1-terra",
    "reports/experiments/phase-6b-confirmatory-v4r1-luna",
    "reports/experiments/phase-6b-confirmatory-v4r1-claude",
]
# Single files copied to the bundle root for standalone context.
_FILES = ["PROVENANCE.md"]

_ARTIFACTS_README = """\
# Public reproducibility artifacts -- paper-v1.0

Frozen artifacts for "Public-Sharing Labels and Verbatim Field Egress in an
MCP-to-A2A Agent Configuration: A Controlled Multi-Model Study."

Extract this archive at the repository root so that `reports/` sits next to
`app/`, `paper/`, etc. Then, from the repository:

    uv sync --frozen

    # 1. verify the frozen raw-data hashes against PROVENANCE.md
    for r in sol terra luna claude; do
      shasum -a 256 \\
        reports/_phase7d_preanalysis_freeze/raw_runs/phase-7a-confirmatory-v1-$r/trials.jsonl
    done
    shasum -a 256 \\
      reports/_phase7d_preanalysis_freeze/MANIFEST.sha256 \\
      reports/phase_7e_analysis/MANIFEST.sha256 \\
      reports/phase_6e_v4r1/MANIFEST.sha256 \\
      reports/_phase6d_v4r1_integrity/MANIFEST.sha256

    # 2. re-run the frozen, pre-specified analysis offline (no provider calls);
    #    it must reproduce reports/phase_7e_analysis/ byte-for-byte
    uv run python -m app.cli.phase_7e_neutral

    # 3. regenerate every manuscript number and audit it
    uv run python paper/arxiv/gen_tables.py
    uv run python paper/arxiv/audit_numbers.py

    # 4. rebuild + byte-compare the Phase 7D deterministic freeze archives
    uv run python scripts/phase_7d_build_freeze.py --check

`MANIFEST.sha256` in this archive lists the SHA-256 of every bundled file.
All frozen identifiers are in `PROVENANCE.md`.
"""


def _tree_files(rel: str) -> list[Path]:
    base = ROOT / rel
    if not base.is_dir():
        raise SystemExit(f"missing tree: {rel}")
    return sorted(p for p in base.rglob("*") if p.is_file())


def _collect() -> list[tuple[Path | None, str, bytes | None]]:
    """(source path or None, arcname, inline-bytes or None)."""
    members: list[tuple[Path | None, str, bytes | None]] = []
    for rel in _TREES:
        for p in _tree_files(rel):
            members.append((p, f"{BUNDLE_PREFIX}/{p.relative_to(ROOT).as_posix()}", None))
    for rel in _FILES:
        p = ROOT / rel
        if not p.is_file():
            raise SystemExit(f"missing file: {rel}")
        members.append((p, f"{BUNDLE_PREFIX}/{rel}", None))
    members.append((None, f"{BUNDLE_PREFIX}/ARTIFACTS_README.md", _ARTIFACTS_README.encode()))
    # MANIFEST over every other member
    lines = []
    for src, arc, blob in sorted(members, key=lambda t: t[1]):
        data = blob if blob is not None else src.read_bytes()  # type: ignore[union-attr]
        rel_in_bundle = arc[len(BUNDLE_PREFIX) + 1 :]
        lines.append(f"{hashlib.sha256(data).hexdigest()}  {rel_in_bundle}")
    manifest = ("\n".join(lines) + "\n").encode()
    members.append((None, f"{BUNDLE_PREFIX}/MANIFEST.sha256", manifest))
    return members


def _archive_bytes(members: list[tuple[Path | None, str, bytes | None]]) -> bytes:
    raw = io.BytesIO()
    with tarfile.open(fileobj=raw, mode="w", format=tarfile.USTAR_FORMAT) as tar:
        for src, arc, blob in sorted(members, key=lambda t: t[1]):
            data = blob if blob is not None else src.read_bytes()  # type: ignore[union-attr]
            info = tarfile.TarInfo(arc)
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
    members = _collect()
    blob = _archive_bytes(members)
    sha = hashlib.sha256(blob).hexdigest()
    n_files = sum(1 for _s, _a, _b in members)
    if "--check" in args:
        if not OUT.is_file():
            print(f"MISSING {OUT}", file=sys.stderr)
            return 1
        on_disk = hashlib.sha256(OUT.read_bytes()).hexdigest()
        ok = on_disk == sha
        print(f"{'OK  ' if ok else 'FAIL'} {OUT.name}  rebuilt={sha}  on_disk={on_disk}")
        return 0 if ok else 1
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_bytes(blob)
    print(f"wrote {OUT.relative_to(ROOT)} ({len(blob)} bytes, {n_files} files)")
    print(f"sha256 {sha}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
