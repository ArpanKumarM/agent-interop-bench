r"""Build the deterministic public reproducibility release for ``paper-v2.0``.

Contents:
  * the full tracked source tree at HEAD (``git archive HEAD``) -- app/,
    scripts/, tests/, paper/, docs/, benchmarks/, mock_servers/,
    pyproject.toml, uv.lock, PROVENANCE.md, REPRODUCE.md, ... -- which
    contains NO ``reports/`` (that tree is git-ignored) and NO ``.env``;
  * the git-ignored *published* raw-data trees, added explicitly by an
    allow-list (never ``reports/`` wholesale): Phase 6/7 confirmatory
    runs + analysis, Phase 8 round-two pilot, Phase 9 F3 resolution run
    dirs + raw-data freeze archive + the aborted attempt-001 archive.

Deterministic: members sorted by path, ``mtime=0``, mode ``0444`` (dirs
``0555``), ``uid=gid=0``, empty owner/group, gzip with ``mtime=0`` and no
embedded filename. Two manifests are written into the bundle root:
``MANIFEST.sha256`` (sha256<TAB>path) and ``RELEASE_MANIFEST.tsv``
(path<TAB>sha256<TAB>size_bytes).

Run:  uv run python scripts/build_paper_v2_release.py
      uv run python scripts/build_paper_v2_release.py --check
"""

from __future__ import annotations

import gzip
import hashlib
import io
import re
import subprocess
import sys
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PREFIX = "agent-interop-bench-paper-v2.0"
OUT = ROOT / "dist" / f"{PREFIX}.tar.gz"

# git-ignored published raw-data trees, added from disk by allow-list.
_PUBLISHED_REPORT_TREES = [
    # Phase 6 / 7 (same set as the paper-v1.0 artifact bundle)
    "reports/_phase6d_v4r1_integrity",
    "reports/phase_6e_v4r1",
    "reports/_phase7d_preanalysis_freeze",
    "reports/phase_7e_analysis",
    "reports/phase_7e1_interpretation",
    "reports/experiments/phase-6b-confirmatory-v4r1-sol",
    "reports/experiments/phase-6b-confirmatory-v4r1-terra",
    "reports/experiments/phase-6b-confirmatory-v4r1-luna",
    "reports/experiments/phase-6b-confirmatory-v4r1-claude",
    "reports/experiments/phase-7a-confirmatory-v1-sol",
    "reports/experiments/phase-7a-confirmatory-v1-terra",
    "reports/experiments/phase-7a-confirmatory-v1-luna",
    "reports/experiments/phase-7a-confirmatory-v1-claude",
    # Phase 8 round-two pilot (byte-pinned raw for verify_phase_8_round2_from_raw.py)
    "reports/experiments/phase-8-pilot-gpt-5.6-sol",
    "reports/experiments/phase-8-pilot-gpt-5.6-terra",
    "reports/experiments/phase-8-pilot-gpt-5.6-luna",
    "reports/experiments/phase-8-pilot-claude-sonnet-5",
    # Phase 9 F3 resolution study
    "reports/experiments/phase-9-f3-sol",
    "reports/experiments/phase-9-f3-terra",
    "reports/experiments/phase-9-f3-luna",
    "reports/experiments/phase-9-f3-claude",
    "reports/_phase9_raw_data_freeze_attempt_002",
    "reports/_phase9_aborted_billing_attempt_001",
]


# Secret / path patterns that must NOT appear in any shipped file, as
# anchored regexes over the raw bytes. Each pattern is written to match a
# *real* credential shape, not a placeholder or a regex-in-documentation.
_FORBIDDEN = (
    ("openai-proj-key", re.compile(rb"sk-proj-[A-Za-z0-9_-]{20,}")),
    ("openai-key", re.compile(rb"sk-[A-Za-z0-9]{32,}")),
    ("anthropic-key", re.compile(rb"sk-ant-api\d{2}-[A-Za-z0-9_-]{20,}")),
    ("aws-access-key", re.compile(rb"AKIA[0-9A-Z]{16}")),
    ("slack-bot-token", re.compile(rb"xoxb-[0-9]{10,}-[0-9]{10,}-[A-Za-z0-9]{20,}")),
    ("openssh-private-key", re.compile(rb"-----BEGIN OPENSSH PRIVATE KEY-----")),
    ("rsa-private-key", re.compile(rb"-----BEGIN RSA PRIVATE KEY-----")),
    ("pkcs8-private-key", re.compile(rb"-----BEGIN PRIVATE KEY-----")),
    ("home-path", re.compile(rb"/(?:Users|home)/[a-z][A-Za-z0-9_.-]{2,}/")),
)
# Obvious non-secrets that would otherwise match the broad key shapes:
# fabricated test fixtures and prose/regex fragments in documentation.
_ALLOW_SUBSTR = (
    b"FAKE",
    b"REDACTED",
    b"shouldneverappear",
    b"abcdefghij1234567890",
    b"masked",
    b"asterisk",
    b"[0-9A-Z]{16}",  # the grep pattern printed in docs/release_v2_checklist.md
    b"[A-Za-z0-9]",
)


def _iter_disk_tree(rel: str):
    base = ROOT / rel
    if not base.exists():
        raise SystemExit(f"missing published tree: {rel}")
    for p in sorted(base.rglob("*")):
        if p.is_file():
            yield p.relative_to(ROOT).as_posix(), p.read_bytes()


# Tracked files kept OUT of the reproducibility bundle: release-page
# narrative whose content would otherwise make the bundle SHA-256
# self-referential.
_ARCHIVE_EXCLUDE = {"docs/release_v2_notes.md"}


def _iter_git_archive():
    raw = subprocess.run(
        ["git", "archive", "--format=tar", "HEAD"],
        cwd=ROOT,
        check=True,
        capture_output=True,
    ).stdout
    with tarfile.open(fileobj=io.BytesIO(raw)) as tf:
        for m in tf.getmembers():
            if m.isfile() and m.name not in _ARCHIVE_EXCLUDE:
                yield m.name, tf.extractfile(m).read()


# git-ignored built artifacts added from disk (deterministic builds).
_EXTRA_FILES = ["paper/arxiv/main_v2.pdf"]


def _collect() -> dict[str, bytes]:
    files: dict[str, bytes] = {}
    for name, data in _iter_git_archive():
        files[name] = data
    for tree in _PUBLISHED_REPORT_TREES:
        for name, data in _iter_disk_tree(tree):
            files[name] = data
    for rel in _EXTRA_FILES:
        p = ROOT / rel
        if not p.exists():
            raise SystemExit(f"missing built artifact: {rel} (run build_pdf_v2.sh first)")
        files[rel] = p.read_bytes()
    return files


# This scanner file defines the credential regexes as literal byte
# strings; it is the one file allowed to contain them.
_SCAN_SKIP = {"scripts/build_paper_v2_release.py"}


def _scan(files: dict[str, bytes]) -> list[str]:
    hits: list[str] = []
    for name in sorted(files):
        if name in _SCAN_SKIP:
            continue
        data = files[name]
        for tag, rx in _FORBIDDEN:
            for m in rx.finditer(data):
                ctx = data[max(0, m.start() - 40) : m.end() + 40]
                if any(a in ctx for a in _ALLOW_SUBSTR):
                    continue
                hits.append(f"{name}: [{tag}] ...{ctx!r}...")
                break
    return hits


def _build(files: dict[str, bytes]) -> bytes:
    manifest_lines = []
    tsv_lines = ["path\tsha256\tsize_bytes"]
    for name in sorted(files):
        h = hashlib.sha256(files[name]).hexdigest()
        manifest_lines.append(f"{h}  {PREFIX}/{name}")
        tsv_lines.append(f"{PREFIX}/{name}\t{h}\t{len(files[name])}")
    files_with_manifests = dict(files)
    files_with_manifests["MANIFEST.sha256"] = ("\n".join(manifest_lines) + "\n").encode()
    files_with_manifests["RELEASE_MANIFEST.tsv"] = ("\n".join(tsv_lines) + "\n").encode()

    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w", format=tarfile.GNU_FORMAT) as tf:
        for name in sorted(files_with_manifests):
            data = files_with_manifests[name]
            ti = tarfile.TarInfo(f"{PREFIX}/{name}")
            ti.size = len(data)
            ti.mtime = 0
            ti.mode = 0o444
            ti.uid = ti.gid = 0
            ti.uname = ti.gname = ""
            ti.type = tarfile.REGTYPE
            tf.addfile(ti, io.BytesIO(data))
    gz = io.BytesIO()
    with gzip.GzipFile(fileobj=gz, mode="wb", mtime=0, filename="") as g:
        g.write(buf.getvalue())
    return gz.getvalue()


def main(argv: list[str]) -> int:
    check = "--check" in argv
    files = _collect()
    hits = _scan(files)
    if hits:
        print(f"SECRET/PATH SCAN FAILED ({len(hits)} hit(s)):", file=sys.stderr)
        for h in hits[:40]:
            print("  " + h, file=sys.stderr)
        return 2
    blob = _build(files)
    digest = hashlib.sha256(blob).hexdigest()
    if check:
        if not OUT.exists():
            print(f"--check: {OUT} does not exist", file=sys.stderr)
            return 1
        on_disk = hashlib.sha256(OUT.read_bytes()).hexdigest()
        ok = on_disk == digest
        print(f"{'OK' if ok else 'FAIL'}  rebuilt={digest}  on_disk={on_disk}")
        return 0 if ok else 1
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_bytes(blob)
    total = sum(len(v) for v in files.values())
    print(f"wrote {OUT}")
    print(f"  members : {len(files)} files + 2 manifests")
    print(f"  raw size: {total:,} bytes")
    print(f"  gz size : {len(blob):,} bytes")
    print(f"  sha256  : {digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
