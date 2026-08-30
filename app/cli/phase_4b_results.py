"""CLI: write the paper-ready Phase 4B analysis (Phase 4B.2).

    uv run python -m app.cli.phase_4b_results

Writes, all OFFLINE from the frozen v3 traces:
    docs/phase_4b_results.md
    docs/assets/phase_4b/table_*.csv          (5 tables)
    docs/assets/phase_4b/fig_*.svg            (3 figures)
    docs/assets/phase_4b/MANIFEST.json        (source SHA-256s + analysis commit)

Makes no provider call; never writes any summary.json.
"""

from __future__ import annotations

import json
import sys

from app.reporting.phase_4b_audit import Phase4BAuditError
from app.reporting.phase_4b_results import (
    ASSETS_DIR,
    DOCS_DIR,
    build_all,
    rows_to_csv,
)


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    try:
        built = build_all()
    except Phase4BAuditError as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return 1

    manifest = built["manifest"]
    commit = manifest["analysis_code_commit_sha"]
    provenance = (
        f"# Phase 4B results ({manifest['phase_4b_results_version']}); "
        f"analysis_commit={commit}; source_trials_sha256="
        + ",".join(
            f"{m}:{manifest['source_artifacts'][m]['trials_jsonl_sha256']}"
            for m in manifest["source_artifacts"]
        )
        + "; zero_new_provider_calls=true"
    )

    ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    written: list[str] = []

    md_path = DOCS_DIR / "phase_4b_results.md"
    if md_path.name == "summary.json":  # defensive
        print("refused: will not write summary.json", file=sys.stderr)
        return 1
    md_path.write_text(built["markdown"])
    written.append(str(md_path))

    for key, rows in built["tables"].items():
        p = ASSETS_DIR / f"{key}.csv"
        p.write_text(rows_to_csv(rows, provenance))
        written.append(str(p))

    for key, svg in built["figures"].items():
        p = ASSETS_DIR / f"{key}.svg"
        p.write_text(
            svg.replace(
                "</svg>",
                f"<!-- provenance: {provenance.replace('--', '-')} -->\n</svg>",
            )
        )
        written.append(str(p))

    manifest_path = ASSETS_DIR / "MANIFEST.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True))
    written.append(str(manifest_path))

    print(json.dumps({"wrote": written}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
