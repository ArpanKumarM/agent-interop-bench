# Phase 7D — pre-analysis execution freeze (provenance record)

**Scientific analysis had not begun when these hashes were frozen.**

This is an immutable, reproducible pre-analysis snapshot of the entire
Phase 7 (`composed-live-canary-007a`, `v7a`) execution, recorded **before
any scientific computation**. No provider call, no trial re-run, no raw
mutation, no manuscript edit occurred in Phase 7D.

The freeze package itself lives at `reports/_phase7d_preanalysis_freeze/`
(read-only; `reports/` is gitignored, matching the Phase 6D convention).
This document is the committed provenance record.

## Source / execution identity

| item | value |
|---|---|
| `EXECUTION_SOURCE_SHA` (frozen executable source) | `2a892c0b9a8a636055cc0c4229aebfd788738b60` |
| metadata commit (FINAL fingerprints artifact) | `2201dda204021629548946f1f913fad026af4c28` |
| operational branch / HEAD at freeze | `phase-6b-impl` @ `fd333575c5a84b13185b456d37e86d2d646c4543` (`== origin/phase-6b-impl`) |
| experiment id / version | `composed-live-canary-007a` / `v7a` |
| panel order | `gpt-5.6-sol` → `gpt-5.6-terra` → `gpt-5.6-luna` → `claude-sonnet-5` |
| scheduling seed | `20260831` |
| study execution env | `A2AVALIDATOR_SOURCE_COMMIT=2a892c0b9a8a636055cc0c4229aebfd788738b60` |

Every one of the 480 study trials and every per-run
`execution_fingerprint.json` records
`source_commit_sha = 2a892c0b9a8a636055cc0c4229aebfd788738b60`.

## Raw `trials.jsonl` SHA-256 (four study runs)

| run | `trials.jsonl` SHA-256 | records |
|---|---|---|
| `phase-7a-confirmatory-v1-sol` | `5227c8b1deb5562e14698aca6ef3d4f6ff3b033c589b015d7fa587e2faa10346` | 120 |
| `phase-7a-confirmatory-v1-terra` | `874e364f7f85eca319634ba1d9351076965e9a51a90cae8792445a4969cab5a1` | 120 |
| `phase-7a-confirmatory-v1-luna` | `e1b6736b9fbcf3690388cb7669d4fc74b592c5ebcb9001196124292a7c5bfa29` | 120 |
| `phase-7a-confirmatory-v1-claude` | `68e0fc5a2b50b0738a29b9d9aebaa7f2c27fb13213a7d428097726b5511e3e37` | 120 |

480 scheduled = 480 attempted = 480 completed; 0 failed; 480 study
provider calls (exactly one decision per trial); 0 retries; 0 replacement
trials; 0 missing / 0 extra schedule positions. Live raw `trials.jsonl`
== the Phase 7D frozen copies byte-for-byte, and == the Phase 7C
integrity-package copies byte-for-byte.

## FINAL execution fingerprints (recorded == frozen artifact)

Artifact `benchmarks/composed/live_canary_phase7a_fingerprints.json`
(SHA-256 `27e9fa4fb6d05e80c5408f72a64b3c408951c571076e20417a171898d2b12623`,
`final_execution_fingerprint: true`, `source_commit_sha` `2a892c0b…`):

| model | `execution_fingerprint_sha256` | per-model `schedule_sha256` |
|---|---|---|
| gpt-5.6-sol | `5357ed45fb1bd98f15a1c7eae62cc266ea13a6138fe1367d66a8af8d15fb7e1d` | `2b0d6c27dadb16098b0aafd01831b6dcaf98c861e7c373c2ddac296662a173cf` |
| gpt-5.6-terra | `ece089cd7d3b8f645ae27b551e3f7743d20fc72d40d62eb13f5c7623db7459b4` | `ab887ecf3161933c5e0251e1b34b0f24237f50ff91a4e27d5df8a8d29106cc66` |
| gpt-5.6-luna | `3fac8f5629ee5d29b5b9530ce7fdf0cedc790f33a211c04adde1c0a3640e0be6` | `61e1b10a3d2d2c05f830db2c014095fe89f10c7e7c3d4be247ffe0bd155203f0` |
| claude-sonnet-5 | `ec5d5e613b5672b43016877287ae18ec58213bafdce88c50e498a62918709ed9` | `826ba13ba9b6b659691eaf066f27004e0920675e352b71c9115dc3431bd193e4` |

Overall `study_schedule_sha256` = `76823fdbbd69a6b5a6a7b3219a5a85525f9f301ed59e6cf1cb188d807551fea5`.

Shared component hashes: `resolved_overlay_bundle_sha256`
`9661309635c2913c6436c5421f48388727f7f3bfe2f5fc62fbe6e60fc460d155`;
`host_policy_sha256`
`32e6ba77c56554de69705f85d547b3e3c48d9d2e2be35d07ed093570d893f2be`;
`tool_schema_sha256`
`efa354c3b7ba9bf5050d32f152ed29f583c7348063184dfb5a8989cf26304b85`;
`canonical_action_schema_sha256` (`relay_to_remote`, `stop`)
`96c91c0be27b33a30cd9a9f5699acbc19e3d15227111c6a34b17d8dc156e65b5`;
`uv_lock_sha256`
`6b0d8279010a57be250d134ca291403061b4a8f7937fd2c93563ef9f6243fb56`;
Python `3.12.2`.

Provider-interface hashes (`provider_config_sha256`): sol
`d8df1b6cdf58d035ef9157253dd41f184a8ac1e89942509196e6148058400ea9`; terra
`8e6c3d7f664b7404f967dacb24be37cf77d29d47bafff8373eb45c188aec7d28`; luna
`db708cd0d840f1053f53e6d92fbf23adede67912e53d51350d15bfdacc8e620b`; claude
`fc7f38d046ef7c7e1c65c0148c7d2eb283a44eb485fae7509a5c16b07ae69c60`.

## Pre-registered Phase 7 analysis document

| item | value |
|---|---|
| path | `docs/phase_7a_neutral_baseline_design.md` (analysis rule in §6) |
| on-disk SHA-256 | `87fec92f4b71a80e10a9f6fd5dd06fade13bec11d72d41725d34a660b1e7f68d` |
| git blob (sha1) | `1b2b5ca2eebb18cec003158f486d318d0c3f688a` |
| last-modified commit | `67545a03980d5cb84f65d55a4d3b5d5048b9f584` (7B.1 — operational-checkout prose only; the §6 analysis rule was frozen at 7B, `EXECUTION_SOURCE_SHA` `2a892c0`, and is unchanged since) |

Execution governance: `docs/phase_7b_execution_governance.md`, on-disk
SHA-256 `0a598ef821aa60ad56d97be104674d79b0c578dbd9002d321d46fa5e5d10ecc4`,
blob `a6358e33a187c2f1fca0968049e47e7fc7b808dc`.

## Integrity packages / archives

| artifact | SHA-256 |
|---|---|
| Phase 7C integrity `MANIFEST.sha256` (self-hash) | `a43d623066170849d719c884085d658bbe550ea7342439d7a923a267970e0ee3` |
| Phase 7D `MANIFEST.sha256` (self-hash, 51 lines) | `dad290f5b5ac460bf2d46c74facc05da7197f946ca5a0a2ed2d165c48ad1dd22` |
| `phase7d_raw_runs.tar.gz` | `d83e0db8154db368b1848d81c4edf04a875195221f329eadd342627cb819cea6` |
| `phase7d_execution_integrity.tar.gz` | `56d8b1232f1f9efc5187bc92ad46785f33d4ecf4796ed5243e22df15d1425028` |
| `phase7d_preanalysis_freeze.tar.gz` | `86005add89c618db6d739267f451ffbebf1927e955465a669f790cbf93872e11` |

Archives are deterministic (sorted members, `mtime=0`, mode `0o444`,
`uid=gid=0`, empty owner/group, USTAR, gzip `mtime=0`, no embedded
filename). Rebuild + verify with
`uv run python scripts/phase_7d_build_freeze.py --check` — all three
reproduce byte-for-byte; the Phase 7D `MANIFEST.sha256` verifies 51/51.

## Non-study smoke exclusion

Four infrastructure smoke calls (one per model) were made **before** study
position 1, under `reports/smoke/phase_7c/` (SHA-256
`47b3866c6f86002e29588aaffb07a075314791419437ba1e8851e7f1d452c89d`) —
outside every study run directory. `is_study_data = false`,
`counts_toward_study = false`, `excluded_from_study_dataset = true`. Smoke
surface `{call_tool, stop}` deliberately differs from the Phase 7A study
surface `{relay_to_remote, stop}`. These four calls are **not** part of the
480-trial dataset.

## Outcome-exposure disclosure (provenance, not a study exclusion)

Recorded in full at
`reports/_phase7d_preanalysis_freeze/OUTCOME_EXPOSURE_NOTE.md` /
`.json`, before scientific analysis begins:

- During the first Sol execution (`phase-7a-confirmatory-v1-sol`), the
  runner's default end-of-run summary output was **incidentally surfaced
  through stdout** (the `run` command prints `summary.json` on completion;
  a `tail` of that stdout showed a fragment of it).
- The surfaced information consisted **only** of the runner's existing
  pooled treatment/control counts and the pooled sign summary for Sol.
- **No** neutral-arm quantity was computed or inspected.
- **No** `C − N`, `P − N`, or `C − P` contrast was computed.
- **No** pair-level Phase 7 effect was computed.
- **No** cross-model comparison was computed.
- **No** scientific conclusion or treatment-direction inference was drawn.
- The Phase 7 analysis plan had **already been frozen** before execution.
- **No** stimulus, outcome definition, schedule, statistical rule, or
  analysis rule was altered after this exposure.
- Runs Terra / Luna / Claude were executed under the same already-frozen
  source and design, with stdout redirected to files not read for
  scientific content.
- This exposure is documented **before** scientific analysis begins. It is
  not minimized or hidden.

## Phase 6 integrity (unchanged)

- `reports/_phase6d_v4r1_integrity/MANIFEST.sha256` = `8310a1f9c1c1464ad1786b832deac328b8d21bf209919f1d57ba66cc1a542695`
- `reports/phase_6e_v4r1/MANIFEST.sha256` = `db34e1bad9d770dcdf38e1d887550c2eab999ffa404c79cea936be429e540593`

## Statement

**Scientific analysis had not begun when these hashes were frozen.** The
raw Phase 7 dataset is complete, execution-integrity-clean, and pinned to
`EXECUTION_SOURCE_SHA` `2a892c0b9a8a636055cc0c4229aebfd788738b60`.
