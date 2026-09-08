"""Phase 9 (F3 resolution study) -- POST-FREEZE EXECUTION-IMPLEMENTATION
ADDENDUM manifest.

The scientific freeze is commit
``32a76bfa19c3240bd87011fe9a7e41b3ced1a511`` (manifest
``docs/phase_9_freeze_manifest.json``) and is NOT rewritten by this file.
This addendum pins every repository file that can affect what the live
Phase 9 run actually does -- the dedicated entrypoint, the frozen-schedule
loader, the at-most-once journal, the halt monitor, the plan/overlays, and
every generic runtime component reused unchanged (the decision-point
engine, both provider adapters, the ledger, the fingerprint machinery, the
config/env loader, the mock MCP tool, the L0 scorer, ...).

Component list = the actual import closure of ``app.cli.phase_9_execute``
plus the mock tool server, restricted to first-party files, plus the
two benchmark artifacts and the environment lock. No hand-maintained list.

Writes ``docs/phase_9_execution_addendum_manifest.json``. Deterministic /
byte-reproducible (``--check`` and a unit test enforce it). NO provider
call. NO trial executed.

Run:  uv run python scripts/phase_9_execution_addendum.py           # write + verify
      uv run python scripts/phase_9_execution_addendum.py --check   # verify only
"""

from __future__ import annotations

import hashlib
import importlib
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))

SCIENTIFIC_FREEZE_COMMIT = "32a76bfa19c3240bd87011fe9a7e41b3ced1a511"
# Pinned once; stable across rebuilds so the manifest stays byte-reproducible.
ADDENDUM_FREEZE_UTC = "2026-09-08T21:35:00Z"
EXECUTION_ADDENDUM_PRECURSOR_COMMIT = "32a76bf"

MANIFEST_PATH = _ROOT / "docs" / "phase_9_execution_addendum_manifest.json"
_SCIENTIFIC_MANIFEST = _ROOT / "docs" / "phase_9_freeze_manifest.json"

# Modules imported explicitly so the closure reaches the lazily-imported
# provider adapters and the outcome path.
_FORCE_IMPORT = (
    "app.cli.phase_9_execute",
    "app.cli.freeze_phase_9_artifacts",
    "app.runner.phase_9_schedule_loader",
    "app.runner.phase_9_execution_journal",
    "app.runner.phase_9_halt_monitor",
    "app.runner.real_host_adapter",
    "app.runner.anthropic_host_adapter",
    "app.runner.host_decision_client",
    "app.runner.openai_adapter",
    "app.runner.anthropic_adapter",
    "app.reporting.pilot_outcomes",
    "app.reporting.rq1_field_egress",
    "mock_servers.composed_tool_mock",
)

# Non-Python result-affecting artifacts + environment lock.
_EXTRA_PATHS = (
    "benchmarks/composed/live_canary_plan_phase9.json",
    "benchmarks/composed/live_overlays_phase9.yaml",
    "docs/phase_9_design/phase_9_execution_schedule.json",
    "docs/phase_9_design/phase_9_execution_params.json",
    "docs/phase_9_design/phase_9_analysis_config.json",
    "scripts/verify_phase_9_execution_ready.py",
    "scripts/phase_9_execution_addendum.py",
    "pyproject.toml",
    "uv.lock",
)

_FIRST_PARTY_ROOTS = ("app", "mock_servers", "scripts")


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canon(obj: object) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def _closure_paths() -> set[str]:
    for name in _FORCE_IMPORT:
        importlib.import_module(name)
    out: set[str] = set()
    for mod in list(sys.modules.values()):
        f = getattr(mod, "__file__", None)
        if not f:
            continue
        p = Path(f).resolve()
        if not p.is_file() or p.suffix != ".py":
            continue
        try:
            rel = p.relative_to(_ROOT)
        except ValueError:
            continue
        if rel.parts and rel.parts[0] in _FIRST_PARTY_ROOTS:
            out.add(rel.as_posix())
    for extra in _EXTRA_PATHS:
        if (_ROOT / extra).is_file():
            out.add(extra)
    return out


def build_manifest() -> dict:
    components = []
    for rel in sorted(_closure_paths()):
        raw = (_ROOT / rel).read_bytes()
        components.append({"path": rel, "sha256": _sha256(raw), "bytes": len(raw)})

    sci = json.loads(_SCIENTIFIC_MANIFEST.read_text())
    body = {
        "phase": 9,
        "kind": "POST-FREEZE EXECUTION-IMPLEMENTATION ADDENDUM",
        "scientific_freeze_unchanged": True,
        "scientific_freeze_commit": SCIENTIFIC_FREEZE_COMMIT,
        "scientific_freeze_manifest_sha256": sci["manifest_sha256"],
        "no_scientific_parameter_changed": True,
        "zero_live_calls_before_implementation": True,
        "addendum_freeze_utc": ADDENDUM_FREEZE_UTC,
        "execution_addendum_precursor_commit": EXECUTION_ADDENDUM_PRECURSOR_COMMIT,
        "live_entrypoint": "python -m app.cli.phase_9_execute run --model <MODEL_ID>",
        "per_model_commands": {
            "gpt-5.6-sol": "ENABLE_REAL_MODEL_COMPOSED_RUNS=true PHASE_9_EXECUTE=1 "
            "uv run python -m app.cli.phase_9_execute run --model gpt-5.6-sol",
            "gpt-5.6-terra": "ENABLE_REAL_MODEL_COMPOSED_RUNS=true PHASE_9_EXECUTE=1 "
            "uv run python -m app.cli.phase_9_execute run --model gpt-5.6-terra",
            "gpt-5.6-luna": "ENABLE_REAL_MODEL_COMPOSED_RUNS=true PHASE_9_EXECUTE=1 "
            "uv run python -m app.cli.phase_9_execute run --model gpt-5.6-luna",
            "claude-sonnet-5": "ENABLE_REAL_MODEL_COMPOSED_RUNS=true PHASE_9_EXECUTE=1 "
            "uv run python -m app.cli.phase_9_execute run --model claude-sonnet-5",
        },
        "verifier_command": (
            "uv run python scripts/verify_phase_9_execution_ready.py --model <MODEL_ID>"
        ),
        "real_output_dirs": {
            "gpt-5.6-sol": "reports/experiments/phase-9-f3-sol/",
            "gpt-5.6-terra": "reports/experiments/phase-9-f3-terra/",
            "gpt-5.6-luna": "reports/experiments/phase-9-f3-luna/",
            "claude-sonnet-5": "reports/experiments/phase-9-f3-claude/",
        },
        "integration_tested_with_fake_providers_only": True,
        "component_count": len(components),
        "components": components,
    }
    body["addendum_manifest_sha256"] = _sha256(_canon(body).encode())
    return body


def _pretty(obj: object) -> str:
    return json.dumps(obj, indent=2, sort_keys=True) + "\n"


def verify_addendum_manifest() -> list[str]:
    """[] == the on-disk addendum manifest is self-consistent and every
    pinned component still matches disk. Used by preflight + the readiness
    verifier. Zero network."""
    fails: list[str] = []
    if not MANIFEST_PATH.exists():
        return ["docs/phase_9_execution_addendum_manifest.json is missing"]
    on_disk = json.loads(MANIFEST_PATH.read_text())
    recorded = on_disk.get("addendum_manifest_sha256", "")
    body = {k: v for k, v in on_disk.items() if k != "addendum_manifest_sha256"}
    if _sha256(_canon(body).encode()) != recorded:
        fails.append("addendum manifest self-hash inconsistent with its body")

    rebuilt = build_manifest()
    if rebuilt["addendum_manifest_sha256"] != recorded:
        fails.append("a pinned execution-path component changed since the addendum was frozen")

    sci = json.loads(_SCIENTIFIC_MANIFEST.read_text())
    if on_disk.get("scientific_freeze_commit") != SCIENTIFIC_FREEZE_COMMIT:
        fails.append("addendum scientific_freeze_commit drift")
    if on_disk.get("scientific_freeze_manifest_sha256") != sci["manifest_sha256"]:
        fails.append(
            "addendum scientific_freeze_manifest_sha256 != docs/phase_9_freeze_manifest.json"
        )

    for row in on_disk.get("components", []):
        p = _ROOT / row["path"]
        if not p.exists():
            fails.append(f"pinned component missing: {row['path']}")
            continue
        raw = p.read_bytes()
        if _sha256(raw) != row["sha256"] or len(raw) != row["bytes"]:
            fails.append(f"pinned component drift: {row['path']}")
    return fails


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    check_only = "--check" in args
    text = _pretty(build_manifest())
    if check_only:
        on_disk = MANIFEST_PATH.read_text() if MANIFEST_PATH.exists() else "<absent>"
        ok = on_disk == text
        print(("OK   " if ok else "FAIL ") + str(MANIFEST_PATH.relative_to(_ROOT)))
        problems = verify_addendum_manifest()
        for p in problems:
            print(f"  - {p}")
        print("ADDENDUM MANIFEST VERIFIED" if ok and not problems else "ADDENDUM MANIFEST NOT OK")
        return 0 if ok and not problems else 1
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST_PATH.write_text(text)
    print(f"wrote {MANIFEST_PATH.relative_to(_ROOT)}  ({len(text.encode())} bytes)")
    return main(["--check"])


if __name__ == "__main__":
    raise SystemExit(main())
