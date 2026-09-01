"""Phase 7D -- rebuild the deterministic pre-analysis freeze archives.

Rebuilds, byte-for-byte, the three archives under
``reports/_phase7d_preanalysis_freeze/archives/`` from the package
directory contents, and verifies each SHA-256 against a recorded value.

This is a REBUILD / VERIFY helper only. It reads the already-frozen
package files; it makes NO provider call, executes NO trial, and modifies
NO source, stimulus, schedule, provider-config, analysis, or fingerprint
file. Determinism comes entirely from the archive parameters below
(sorted members, ``mtime=0``, mode ``0o444``, ``uid=gid=0``, empty
owner/group, USTAR, gzip ``mtime=0`` and NO embedded filename), never from
touching any source file.

Run:  uv run python scripts/phase_7d_build_freeze.py            # rebuild + verify
      uv run python scripts/phase_7d_build_freeze.py --check    # verify only
"""

from __future__ import annotations

import contextlib
import gzip
import hashlib
import io
import sys
import tarfile
from pathlib import Path

PKG = Path("reports/_phase7d_preanalysis_freeze")
ARC = PKG / "archives"
TOP_MANIFEST = (PKG / "MANIFEST.sha256").resolve()

# Recorded final archive SHA-256 (Phase 7D). --check compares against these.
EXPECTED = {
    "phase7d_raw_runs.tar.gz": "d83e0db8154db368b1848d81c4edf04a875195221f329eadd342627cb819cea6",
    "phase7d_execution_integrity.tar.gz": (
        "56d8b1232f1f9efc5187bc92ad46785f33d4ecf4796ed5243e22df15d1425028"
    ),
    "phase7d_preanalysis_freeze.tar.gz": (
        "86005add89c618db6d739267f451ffbebf1927e955465a669f790cbf93872e11"
    ),
}


def _sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _det_archive_bytes(members: list[tuple[Path, str]]) -> bytes:
    """Fully path-independent deterministic ``.tar.gz`` bytes."""
    members = sorted(members, key=lambda t: t[1])
    raw = io.BytesIO()
    with tarfile.open(fileobj=raw, mode="w", format=tarfile.USTAR_FORMAT) as tar:
        for path, name in members:
            data = path.read_bytes()
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


def _members_raw_runs() -> list[tuple[Path, str]]:
    base = PKG / "raw_runs"
    return [
        (p, f"phase7d_raw_runs/{p.relative_to(base).as_posix()}")
        for p in base.rglob("*")
        if p.is_file()
    ]


def _members_execution_integrity() -> list[tuple[Path, str]]:
    base = PKG / "execution_integrity_7c"
    return [
        (p, f"phase7d_execution_integrity/{p.relative_to(base).as_posix()}")
        for p in base.rglob("*")
        if p.is_file()
    ]


def _members_whole_package() -> list[tuple[Path, str]]:
    out: list[tuple[Path, str]] = []
    for p in PKG.rglob("*"):
        if not p.is_file():
            continue
        rel = p.relative_to(PKG)
        if rel.parts[0] == "archives" or p.resolve() == TOP_MANIFEST:
            continue
        out.append((p, f"phase7d_preanalysis_freeze/{rel.as_posix()}"))
    return out


ARCHIVES = {
    "phase7d_raw_runs.tar.gz": _members_raw_runs,
    "phase7d_execution_integrity.tar.gz": _members_execution_integrity,
    "phase7d_preanalysis_freeze.tar.gz": _members_whole_package,
}


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    check_only = "--check" in args
    if not PKG.is_dir():
        print(f"missing package dir: {PKG}", file=sys.stderr)
        return 2

    ok = True
    for name, members_fn in ARCHIVES.items():
        rebuilt = _det_archive_bytes(members_fn())
        rebuilt_sha = hashlib.sha256(rebuilt).hexdigest()
        target = ARC / name
        if not check_only:
            with contextlib.suppress(FileNotFoundError):
                target.chmod(0o644)
            target.write_bytes(rebuilt)
            target.chmod(0o444)
        on_disk_sha = _sha256(target) if target.exists() else "<absent>"
        expected = EXPECTED[name]
        row_ok = rebuilt_sha == expected == on_disk_sha
        ok &= row_ok
        print(
            f"{'OK  ' if row_ok else 'FAIL'} {name:38s} rebuilt={rebuilt_sha} "
            f"on_disk={on_disk_sha} expected={expected}"
        )
    print("ALL ARCHIVES REPRODUCE BYTE-FOR-BYTE:" if ok else "MISMATCH:", ok)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
