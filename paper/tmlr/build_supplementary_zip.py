r"""Build the anonymized TMLR supplementary ZIP.

Minimum-sufficient package to (a) read the anonymized manuscript and
(b) reproduce every Phase 6/7/8/9 number from frozen raw data with **no
API credentials**. Deterministic (sorted members, fixed mtime).

Anonymity is enforced two ways:
  * a curated allow-list -- identity-bearing files (the public manuscript,
    CITATION.cff, LICENSE with the copyright line, README, arXiv metadata,
    release docs) are never added;
  * every text member is run through _scrub() (author name / email /
    GitHub user / repo URLs / release-tag URLs / the v1 arXiv id / git
    commit SHAs -> neutral text), then the whole archive is scanned and
    the build ABORTS on any residual identifying hit.

Run:  uv run python paper/tmlr/build_supplementary_zip.py
      uv run python paper/tmlr/build_supplementary_zip.py --check
"""

from __future__ import annotations

import hashlib
import io
import re
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "dist" / "tmlr-supplementary-anon.zip"
PREFIX = "supplementary"

# ---- what goes in (whole trees + individual files), all repo-relative ----
_TREES = [
    "app",
    "scripts",
    "tests",
    "mock_servers",
    "policies",
    "benchmarks/composed",
    # frozen design / result / manifest docs (NOT docs/release_v2_*.md)
    "docs/phase_9_design",
    # published raw-data trees (same allow-list as the public bundle)
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
    "reports/experiments/phase-8-pilot-gpt-5.6-sol",
    "reports/experiments/phase-8-pilot-gpt-5.6-terra",
    "reports/experiments/phase-8-pilot-gpt-5.6-luna",
    "reports/experiments/phase-8-pilot-claude-sonnet-5",
    "reports/experiments/phase-9-f3-sol",
    "reports/experiments/phase-9-f3-terra",
    "reports/experiments/phase-9-f3-luna",
    "reports/experiments/phase-9-f3-claude",
    "reports/_phase9_raw_data_freeze_attempt_002",
    "reports/_phase9_aborted_billing_attempt_001",
]
_FILES = [
    "pyproject.toml",
    "uv.lock",
    ".python-version",
    ".gitleaks.toml",
    # anonymized manuscript build
    "paper/tmlr/main_tmlr.tex",
    "paper/tmlr/main_tmlr.pdf",
    "paper/tmlr/references_tmlr.bib",
    "paper/tmlr/tmlr.sty",
    "paper/tmlr/tmlr.bst",
    "paper/tmlr/build_pdf_tmlr.sh",
    "paper/tmlr/build_tmlr_tex.py",
    "paper/tmlr/diff_scientific_content.py",
    "paper/tmlr/verify_anon_equivalence.py",
    "paper/tmlr/TRANSFORM_LOG.txt",
]
# top-level docs shipped only as scrubbed copies, under new names
_SCRUBBED_AS = {
    "PROVENANCE.md": "PROVENANCE_anon.md",
    "REPRODUCE.md": "REPRODUCE.md",
}
# frozen non-release docs referenced by verifiers
_DOC_GLOBS = ["docs/phase_8*.md", "docs/phase_7a*.md", "docs/phase_9*.md"]

# never ship, even if reached by a tree
_EXCLUDE_SUBSTR = (
    "/.git",
    "/__pycache__/",
    ".pyc",
    "/node_modules/",
    "docs/release_v2_",
    # self-hashed provenance manifests: scrubbing a commit SHA inside them
    # would break their recorded self-hash. Raw-data integrity in the anon
    # package is checked via shasum + the in-zip MANIFEST.sha256 instead.
    "_manifest.json",
    "docs/phase_9_execution_addendum",
    "docs/phase_9_execution_attempt_002",
    "docs/phase_9_raw_data_freeze_attempt_002_manifest",
    "docs/phase_9_freeze_manifest",
)

# ---- scrubbing ----
_AUTHOR = "Arpan Kumar Mahapatra"
_EMAIL_LOCAL = "arpan.arpan.mohapatra"
_SUBS = [
    (re.compile(re.escape(_AUTHOR)), "the authors"),
    (re.compile(r"Mahapatra,\s*Arpan Kumar"), "Anonymous"),
    (re.compile(r"mahapatra\d+v\d+", re.I), "selfcite"),
    (re.compile(r"\bMahapatra\b"), "Anonymous"),
    (re.compile(r"\bMohapatra\b"), "Anonymous"),
    (re.compile(r"\bArpan\b"), "Anon"),
    (re.compile(r"arpan\.arpan"), "anon.anon"),
    (re.compile(rf"{re.escape(_EMAIL_LOCAL)}@[A-Za-z0-9.-]+"), "anon@example.org"),
    (re.compile(r"https?://github\.com/ArpanKumarM/agent-interop-bench[^\s`)\]\"']*"),
     "the anonymized supplementary material"),
    (re.compile(r"github\.com/ArpanKumarM/agent-interop-bench[^\s`)\]\"']*"),
     "the anonymized supplementary material"),
    (re.compile(r"\bArpanKumarM\b"), "anon"),
    (re.compile(r"\bpaper-v[12]\.[0-9]+(?:\.[0-9]+)?\b"), "the artifact release"),
    (re.compile(r"arXiv:2609\.01693(?:v\d+)?"), "an earlier version by the same authors"),
    (re.compile(r"\b2609\.01693\b"), "[prior-version-id]"),
]
# neutral marker for redacted repository-identifying git identifiers.
_MARK = "[redacted-for-double-blind]"
# blanket 40-hex git-commit shape -> _MARK. Applied ONLY to human-facing
# files OUTSIDE reports/ (manuscript, docs, scripts). NOT applied inside
# reports/ -- a random 40-hex run id there is not a locator, and a
# blanket sub could touch analysis-adjacent fields.
_SHA_SUB = (re.compile(r"\b[0-9a-f]{40}\b"), _MARK)
# the specific public / GitHub-searchable freeze / execution commit SHAs.
# These CAN act as direct locators to the (now public) repository, so they
# are redacted EVERYWHERE -- including inside reports/ .jsonl trial records
# and .json fingerprints -- as full strings and unique 7/12-char prefixes.
_KNOWN_COMMITS = (
    "32a76bfa19c3240bd87011fe9a7e41b3ced1a511",  # scientific-design freeze
    "a347a8b3c2b29b77586a113fdabf8bd310e92e85",  # execution-implementation freeze
    "e8fd793940458a88f5fd122a7065737bf4a109c5",  # attempt-002 freeze / exec source
    "c64a32d73e9d4b52fb03d4b6a91c8d3fa05f3bfe",  # raw-data freeze
    "ffaae077e791148bb05a039749d835d308ce85a1",  # pre-manuscript audit
    "74ba1cdd545ce9f32850bd4ba107e45af952dbb3",  # Phase 8 round-one exec source
    "d06a88b0eebd6f4452ab09ccbc6fe5c2a4907631",  # Phase 8 round-two exec source
    "89c0542",                                     # frozen-analysis commit (short)
)
_TEXT_EXT = {".md", ".tex", ".txt", ".py", ".toml", ".cfg", ".sh", ".bib", ".yaml", ".yml",
             ".json", ".cff", ".bst", ".sty"}

# identity scan run on the finished archive -- any hit aborts the build.
_IDENTITY_RX = [
    ("author-name", re.compile(rb"Arpan", re.I)),
    ("author-name", re.compile(rb"Mahapatra", re.I)),
    ("author-name", re.compile(rb"Mohapatra", re.I)),
    ("github-user", re.compile(rb"ArpanKumarM")),
    ("email-local", re.compile(rb"arpan\.arpan")),
    ("v1-arxiv-id", re.compile(rb"2609\.01693")),
    ("github-repo-url", re.compile(rb"github\.com/[A-Za-z0-9_-]+/agent-interop-bench")),
    ("home-path", re.compile(rb"/(?:Users|home)/[a-z][A-Za-z0-9_.-]{2,}/")),
    ("release-tag-url", re.compile(rb"releases/tag/paper-v")),
    *[("known-commit-sha", re.compile(re.escape(c).encode()))
      for c in _KNOWN_COMMITS if len(c) >= 40],
    *[("known-commit-prefix", re.compile(re.escape(c[:12]).encode()))
      for c in _KNOWN_COMMITS if len(c) >= 40],
]
_SCAN_ALLOW = (b"FAKE", b"REDACTED", b"shouldneverappear", b"abcdefghij1234567890")


def _redact_known_commits(text: str, *, prefixes: bool) -> str:
    for c in _KNOWN_COMMITS:
        text = text.replace(c, _MARK)
        if prefixes and len(c) >= 40:
            text = text.replace(c[:12], _MARK).replace(c[:7], _MARK)
    return text


def _scrub(name: str, data: bytes) -> bytes:
    ext = Path(name).suffix.lower()
    is_text = ext in _TEXT_EXT
    is_jsonl = ext == ".jsonl"
    if not (is_text or is_jsonl):
        return data
    try:
        text = data.decode()
    except UnicodeDecodeError:
        return data
    if is_jsonl:
        # trial records: touch ONLY the repository-locating commit SHAs
        # (full strings), nothing else -- no name subs, no prefix subs, no
        # blanket 40-hex. Every model output / stimulus / action / score /
        # trial id / condition / analysis value is preserved byte-for-byte.
        return _redact_known_commits(text, prefixes=False).encode()
    # other text: full known-commit redaction (incl. 7/12-char prefixes in
    # prose) so scripts and the result JSON they regenerate stay consistent.
    text = _redact_known_commits(text, prefixes=True)
    if not name.startswith("reports/"):
        for rx, repl in _SUBS:
            text = rx.sub(repl, text)
        text = _SHA_SUB[0].sub(_SHA_SUB[1], text)
    return text.encode()


def _walk_tree(rel: str):
    base = ROOT / rel
    if not base.exists():
        raise SystemExit(f"missing tree: {rel}")
    for p in sorted(base.rglob("*")):
        if p.is_file() and not any(s in p.as_posix() for s in _EXCLUDE_SUBSTR):
            yield p.relative_to(ROOT).as_posix(), p.read_bytes()


def _collect() -> dict[str, bytes]:
    out: dict[str, bytes] = {}
    for tree in _TREES:
        for name, data in _walk_tree(tree):
            out[name] = _scrub(name, data)
    for rel in _FILES:
        p = ROOT / rel
        if not p.exists():
            raise SystemExit(f"missing file: {rel}")
        out[rel] = _scrub(rel, p.read_bytes())
    for src, dst in _SCRUBBED_AS.items():
        out[dst] = _scrub(dst, (ROOT / src).read_bytes())
    for g in _DOC_GLOBS:
        for p in sorted(ROOT.glob(g)):
            rel = p.relative_to(ROOT).as_posix()
            if not any(s in rel for s in _EXCLUDE_SUBSTR):
                out[rel] = _scrub(rel, p.read_bytes())
    out["ANON_README.md"] = _ANON_README.encode()
    return out


def _scan(files: dict[str, bytes]) -> list[str]:
    hits = []
    for name in sorted(files):
        data = files[name]
        for tag, rx in _IDENTITY_RX:
            for m in rx.finditer(data):
                ctx = data[max(0, m.start() - 30) : m.end() + 30]
                if any(a in ctx for a in _SCAN_ALLOW):
                    continue
                hits.append(f"{name}: [{tag}] ...{ctx!r}...")
                break
    return hits


_ANON_README = """# Anonymized supplementary material

Minimum package to read the paper and reproduce every Phase 6/7/8/9
number from frozen raw data with **no API credentials and no paid model
inference**.

## Contents
- `paper/tmlr/main_tmlr.{tex,pdf}` -- the anonymized manuscript, its
  TMLR style files, `references_tmlr.bib`, and `build_pdf_tmlr.sh`.
  `build_tmlr_tex.py` + `TRANSFORM_LOG.txt` + `diff_scientific_content.py`
  document how it was derived from the (withheld) camera-ready source and
  prove the scientific content is unchanged.
- `REPRODUCE.md` -- step-by-step offline reproduction (sections A-J).
- `PROVENANCE_anon.md` -- full freeze/provenance record with
  repository-identifying git commit identifiers redacted to
  `[redacted-for-double-blind]` (content SHA-256 hashes are kept).
- `app/`, `scripts/`, `tests/`, `mock_servers/`, `policies/`,
  `benchmarks/composed/`, `pyproject.toml`, `uv.lock` -- the harness and
  the offline verifiers / analysis.
- `docs/phase_*` -- frozen design / result docs (self-hashed provenance
  manifests are omitted; raw-data integrity is checked via `shasum` and
  the in-package `MANIFEST.sha256`).
- `reports/` -- double-blind derivative copies of the published
  Phase 6/7/8/9 raw-data trees, the Phase 9 raw-data-freeze archive, and
  the aborted attempt-001 archive (operational provenance only: 9
  rejected quota requests, 0 successful responses, 0 tokens, 0 scientific
  observations).

## Redacted for double-blind review
Author name, email, GitHub username, the code repository URL, artifact
release tags, the earlier-version arXiv id, and every
repository-identifying git commit SHA (full strings and unique 7/12-char
prefixes) -- in the manuscript, the docs, the scripts, **and inside the
raw trace files**. The identifying camera-ready manuscript,
`CITATION.cff`, `LICENSE`, and `README.md` are not included. None of this
affects reproduction.

The raw trace files in this anonymous review package are double-blind
derivative copies of the canonical frozen artifacts. Repository-identifying
provenance fields have been redacted. No model output, stimulus, action,
score, trial identifier, experimental condition, or analysis-relevant
value was modified. Canonical byte-identical artifacts and original
provenance hashes will be provided in the non-anonymous artifact release.

`verify_anon_equivalence.py` re-derives the frozen Phase 9 analysis from
these sanitized traces (calling the pinned analysis functions directly)
and checks every analysis-relevant value -- N/P counts, theta, Delta,
95% CIs, Q1 classifications, panel verdict, Q2 detected/not-detected,
Holm p, and every pre-registered sensitivity result -- against the
canonical analysis. The only per-record difference is the redacted
provenance field `provenance.execution_fingerprint.source_commit_sha`.

The canonical byte-for-byte freeze verifiers
(`scripts/verify_phase_9_freeze.py`, `scripts/phase_9_analyze.py`'s
frozen-data gate, `scripts/verify_phase_8_round2_from_raw.py`'s SHA-256
step) key on the *canonical* raw bytes; they are expected to report a
hash mismatch on these double-blind derivative copies and are superseded
here by `verify_anon_equivalence.py` and this package's `MANIFEST.sha256`.

## Quick start
```
uv sync --frozen
uv run python paper/tmlr/verify_anon_equivalence.py   # -> ANON_RAW_SCIENTIFIC_EQUIVALENCE: PASS
bash paper/tmlr/build_pdf_tmlr.sh                      # rebuilds this anonymized PDF
```
(`diff_scientific_content.py` needs the withheld public source; it is run
in the non-anonymous release.)
"""


def _build(files: dict[str, bytes]) -> bytes:
    manifest = "\n".join(
        f"{hashlib.sha256(files[n]).hexdigest()}  {PREFIX}/{n}" for n in sorted(files)
    )
    files = dict(files)
    files["MANIFEST.sha256"] = (manifest + "\n").encode()
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for name in sorted(files):
            zi = zipfile.ZipInfo(f"{PREFIX}/{name}", date_time=(1980, 1, 1, 0, 0, 0))
            zi.external_attr = 0o444 << 16
            zi.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(zi, files[name])
    return buf.getvalue()


def main(argv: list[str]) -> int:
    files = _collect()
    hits = _scan(files)
    if hits:
        print(f"ANONYMITY SCAN FAILED ({len(hits)} hit(s)):", file=sys.stderr)
        for h in hits[:60]:
            print("  " + h, file=sys.stderr)
        return 2
    blob = _build(files)
    digest = hashlib.sha256(blob).hexdigest()
    if "--check" in argv:
        if not OUT.exists():
            print("no existing zip", file=sys.stderr)
            return 1
        ok = hashlib.sha256(OUT.read_bytes()).hexdigest() == digest
        print(f"{'OK' if ok else 'FAIL'}  {digest}")
        return 0 if ok else 1
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_bytes(blob)
    print(f"wrote {OUT}")
    print(f"  members : {len(files)}")
    print(f"  size    : {len(blob):,} bytes")
    print(f"  sha256  : {digest}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
