# `paper-v2.0` — public reproducibility release

Frozen artifacts for the v2 manuscript, *"Whether a Sensitivity-Label
Effect Can Be Measured at an MCP-to-A2A Handoff Depends on the Task
Framing: A Pre-Registered Sweep"* (arXiv:2609.01693 v2).

Supersedes and includes everything in `paper-v1.0`.

## Archive

- file: `agent-interop-bench-paper-v2.0.tar.gz`
- built by: `scripts/build_paper_v2_release.py` (deterministic;
  `uv run python scripts/build_paper_v2_release.py --check` re-derives the
  archive SHA-256 from the source tree + published raw trees + built PDF).
- The archive SHA-256, byte size, member count, and the exact release
  commit are listed in the **Verification** section of this GitHub
  release page (added when the asset is uploaded).

`MANIFEST.sha256` (in the archive root) lists every member as
`<sha256>  agent-interop-bench-paper-v2.0/<path>`; verify with
`shasum -a 256 -c agent-interop-bench-paper-v2.0/MANIFEST.sha256` from the
archive's parent directory. `RELEASE_MANIFEST.tsv` gives
`path <tab> sha256 <tab> size_bytes` for the same set.

## What's inside

- **Full tracked source** at the release commit (`app/`, `scripts/`,
  `tests/`, `paper/`, `docs/`, `benchmarks/`, `mock_servers/`,
  `pyproject.toml`, `uv.lock`, `PROVENANCE.md`, `REPRODUCE.md`,
  `REPRODUCIBILITY.md`). Contains **no** `reports/` tree (git-ignored) and
  **no** `.env`.
- **Phase 6 / Phase 7** confirmatory raw runs + pre-analysis freezes +
  analysis artifacts (same set as `paper-v1.0`).
- **Phase 8** round-two pilot: the four `phase-8-pilot-<model>/` run dirs
  (byte-pinned raw that `scripts/verify_phase_8_round2_from_raw.py`
  recomputes).
- **Phase 9 F3 resolution study**: the four
  `reports/experiments/phase-9-f3-<model>/` run dirs (`trials.jsonl`,
  `attempts.jsonl`, `summary.json`, `execution_fingerprint.json`,
  `schedule.json`, `plan.json`, `phase_9_frozen_trial_map.json`);
  `reports/_phase9_raw_data_freeze_attempt_002/` (byte-identical archive +
  its `MANIFEST.sha256`, self-hash
  `6e86a4cf00ab99636de84d86428fae3d7b708ff2498ec62fe19e43f7852e760f`);
  the frozen analysis output
  `docs/phase_9_design/phase_9_results_attempt_002.{json,md}`; the
  hash-pinned analysis implementation and all Phase 9 freeze / verifier
  scripts.
- **Built PDF** `paper/arxiv/main_v2.pdf` (19 pages, SHA-256
  `6a8f86428accace37e317a0aeed372c4bcbdf718199797c9ec53949bee6554ef`;
  deterministic from `paper/arxiv/build_pdf_v2.sh`).

### Phase 9 frozen raw `trials.jsonl` SHA-256

| model | SHA-256 |
|---|---|
| `gpt-5.6-sol`     | `7d5cd35ba3102fc3bfc2501d74bb9ec758cd220395f44e79980a20370ffe02fc` |
| `gpt-5.6-terra`   | `fc658ac3ccf3f79054ee3c38e54543932dce0c076fa9012fd4e0539c7e54d1e6` |
| `gpt-5.6-luna`    | `0d45e5bd1b3419bf52481e3c2d968cc92a2f0b1b432f5129937f34fdfc3e1ce0` |
| `claude-sonnet-5` | `f09c30cbc0c1e7688e672341bec70767deb0e6885999d85e12074b7b57e06313` |

Phase 9 freeze chain: scientific `32a76bfa19c3240bd87011fe9a7e41b3ced1a511`
· execution-implementation addendum `a347a8b3c2b29b77586a113fdabf8bd310e92e85`
· attempt-002 `e8fd793940458a88f5fd122a7065737bf4a109c5`
· raw-data `c64a32d73e9d4b52fb03d4b6a91c8d3fa05f3bfe`
· analysis `89c0542`
· pre-manuscript documentation audit `ffaae077e791148bb05a039749d835d308ce85a1`.

## Aborted attempt (operational provenance, NOT scientific data)

`reports/_phase9_aborted_billing_attempt_001/` records an authorized run
that halted itself after **9** provider calls (all `gpt-5.6-sol`), every
one returning HTTP 429 `insufficient_quota`. It produced **0** successful
model responses, **0** generated tokens, **$0.00** billed cost, and
**0** scientific observations, and was excluded before any analysis under
the frozen §12 completion rule. It is not an outcome-based re-run — no
model output was ever observed. Attempt 002 is the run analysed in the
paper. Do not count these files as Phase 9 data.

## Reproduce with zero API credentials

See `REPRODUCE.md` in the archive. The normal path — verify the frozen
raw hashes → run the offline verifiers → re-run the deterministic frozen
analysis → re-run the paper numeric audits → rebuild the PDF — requires
**no** OpenAI or Anthropic keys and **no** paid inference.

## What cannot be reproduced

**Phase 8 round-one (F1–F3) raw traces were overwritten** by the
round-two run before the `public` arm was identified as worth analyzing.
The originally-recorded round-one SHA-256s survive in
`docs/phase_8c_pilot_result.md` but there are no bytes to check them
against. The round-one `public` arm cannot be recovered; the within-study
`P − N` contrast in §6.4 therefore exists only for F4–F6, for one model.
Phase 9 collected a fresh `public` arm at F3 over 64 new scenarios, so
the framing that mattered no longer depends on the lost data. Disclosed
in the paper (§6.4, §8, §9), `REPRODUCIBILITY.md` §7, and
`docs/release_v2_checklist.md` §3.
