# Provenance

This file is the single, durable record of the frozen chronology and all
byte-pinned identifiers behind the paper. Sections 1–4 are the frozen
record for **v1** (`paper/arxiv/main.tex` / `paper/main.md`) and are not
edited. **Section 5 is a v2 addendum** covering Phase 8 and the current
manuscript (`paper/main_v2.md` / `paper/arxiv/main_v2.tex`).

Scope (v1): the paper reports the **Phase 7** three-arm neutral-baseline
study (`composed-live-canary-007a` / `v7a`) as the primary study, and the
**Phase 6** two-arm confirmatory study (`v4r1`) as a descriptive
comparison and as the source of the secondary null experiment and the
harness enforcement property. **Phase 6 and Phase 7 observations are never
pooled.** v2 keeps every v1 number and adds Phase 8 (§5 below).

The `reports/` directory (raw runs, integrity packages, analysis
artifacts) is `.gitignore`d and is distributed as a public artifact
release, not committed. Every hash below is verifiable against that
release.

---

## 1. Chronology

| step | what happened |
|---|---|
| **Phase 6 (`v4r1`)** | Frozen two-arm confirmatory study: a `CONFIDENTIAL - INTERNAL ONLY` record vs. a matched `PUBLIC - OK TO SHARE` record with byte-identical substantive values; 10 pairs x 4 repeats x 4 models. A first execution (source `046e8035b8f47e54c38167ad0c440f2b75306409`) was aborted by a runner bug **before any outcome was inspected**; one class of invalid tool selection was changed from an uncaught crash to a recorded `provider_protocol_error`, a new source `23bf90bf379654f0afc2fadaa5a16ade30ae3439` was frozen, and the whole study was rerun from the first trial. The primary-outcome definitions and the statistical plan did not change; the per-model and overall schedule hashes are byte-identical to the aborted version. The aborted observations are preserved on disk, permanently excluded, and never merged. |
| **Methodological gap identified** | A confidential-vs-public-only contrast cannot attribute the observed difference to either active label. |
| **Phase 7A / 7B** | The three-arm extension (adding an unlabeled baseline) was designed and **frozen before execution**: analysis plan `docs/phase_7a_neutral_baseline_design.md` (SHA-256 `87fec92f4b71a80e10a9f6fd5dd06fade13bec11d72d41725d34a660b1e7f68d`); execution governance `docs/phase_7b_execution_governance.md`; executable source `2a892c0b9a8a636055cc0c4229aebfd788738b60`; per-model FINAL execution fingerprints frozen. |
| **Phase 7C** | 480/480 trials executed: 480 provider calls `ok`, `retries = 0`, no replacement trials, every trial pinned to `2a892c0b…` with its per-model FINAL execution fingerprint, all schedule positions exact. |
| **Phase 7D** | The complete raw dataset was frozen **before any scientific computation**, with SHA-256 manifests and deterministic archives. |
| **Phase 7E** | The pre-registered analysis (`docs/phase_7a_neutral_baseline_design.md` section 6) was implemented (`app/reporting/phase_7e_neutral.py`, `app/cli/phase_7e_neutral.py`) and run **once** against the Phase 7D frozen raw copies. Raw `trials.jsonl` bytes are identical before and after. |
| **Phase 7E.1** | Interpretive clarification only: the analysis implementation had supplied `pooled N <= 0.05` as an operational classifier for the frozen design's unquantified phrase "neutral baseline at or near zero"; that threshold was not part of the frozen plan, so Phase 7E.1 adopts the more conservative threshold-free reading (Claude's `C - N` is treated as low-baseline / floor-limited). **No numeric result changed.** |

### Incidental-exposure disclosure

During the first Phase 7 run (`gpt-5.6-sol`) the runner's default
end-of-run summary was briefly surfaced through stdout, showing a fragment
of the runner's existing pooled treatment/control counts and a sign
summary **for `gpt-5.6-sol` only**. No unlabeled-arm quantity and no
`C - N` / `P - N` / `C - P` contrast, pair effect, cross-model comparison,
or scientific conclusion was computed or inspected before analysis. The
analysis plan was already frozen; nothing was altered afterward. This is a
provenance disclosure, not a study exclusion, and it did not change the
analysis.

---

## 2. Pinned identifiers

### Phase 7 (primary study)

| item | value |
|---|---|
| execution source commit | `2a892c0b9a8a636055cc0c4229aebfd788738b60` |
| analysis implementation commit | `dc5d0767ce4bec946373bf720a37aae538ef258c` |
| interpretation freeze commit (Phase 7E.1) | `b53ddc6` |
| pre-execution-frozen analysis-plan SHA-256 (`docs/phase_7a_neutral_baseline_design.md`) | `87fec92f4b71a80e10a9f6fd5dd06fade13bec11d72d41725d34a660b1e7f68d` |
| Phase 7D pre-analysis freeze manifest (self-hash) | `dad290f5b5ac460bf2d46c74facc05da7197f946ca5a0a2ed2d165c48ad1dd22` |
| Phase 7E analysis-artifact manifest (self-hash) | `dbeb7068f1fe318862ba706a788fcc7a46107168f162e0021a04437958603b19` |
| Phase 7E.1 interpretation-package manifest (self-hash) | `f63d30c525926ef0d4ae54ccdfbeb425143d7e2e420280881ced637876d4b6d2` |
| overall study-schedule hash | `76823fdbbd69a6b5a6a7b3219a5a85525f9f301ed59e6cf1cb188d807551fea5` |

Raw `trials.jsonl` SHA-256 (Phase 7D frozen copies; byte-identical before
and after Phase 7E analysis):

| run | SHA-256 |
|---|---|
| `phase-7a-confirmatory-v1-sol` | `5227c8b1deb5562e14698aca6ef3d4f6ff3b033c589b015d7fa587e2faa10346` |
| `phase-7a-confirmatory-v1-terra` | `874e364f7f85eca319634ba1d9351076965e9a51a90cae8792445a4969cab5a1` |
| `phase-7a-confirmatory-v1-luna` | `e1b6736b9fbcf3690388cb7669d4fc74b592c5ebcb9001196124292a7c5bfa29` |
| `phase-7a-confirmatory-v1-claude` | `68e0fc5a2b50b0738a29b9d9aebaa7f2c27fb13213a7d428097726b5511e3e37` |

Per-model FINAL execution fingerprint (`execution_fingerprint_sha256`):

| model | fingerprint |
|---|---|
| gpt-5.6-sol | `5357ed45fb1bd98f15a1c7eae62cc266ea13a6138fe1367d66a8af8d15fb7e1d` |
| gpt-5.6-terra | `ece089cd7d3b8f645ae27b551e3f7743d20fc72d40d62eb13f5c7623db7459b4` |
| gpt-5.6-luna | `3fac8f5629ee5d29b5b9530ce7fdf0cedc790f33a211c04adde1c0a3640e0be6` |
| claude-sonnet-5 | `ec5d5e613b5672b43016877287ae18ec58213bafdce88c50e498a62918709ed9` |

### Phase 6 (`v4r1`; comparison + secondary null + enforcement property)

| item | value |
|---|---|
| execution source commit | `23bf90bf379654f0afc2fadaa5a16ade30ae3439` |
| aborted first-execution source commit (excluded) | `046e8035b8f47e54c38167ad0c440f2b75306409` |
| analysis source commit (Phase 6E.2) | `60024fcf24624fab90ac9d6a3be7c73be17acbc9` |
| frozen raw-integrity manifest (self-hash) | `8310a1f9c1c1464ad1786b832deac328b8d21bf209919f1d57ba66cc1a542695` |
| analysis-artifact manifest (self-hash) | `db34e1bad9d770dcdf38e1d887550c2eab999ffa404c79cea936be429e540593` |
| overall study-schedule hash | `092b638ea9dd345e7507f7f859adc9af331e8785675f6ea52ec25ee0ac21f0e0` |

Per-model execution fingerprint:

| model | fingerprint |
|---|---|
| gpt-5.6-sol | `c92f11c4c7399092aca078545a44962eb1432f0643e147b968bdd549b3cf133d` |
| gpt-5.6-terra | `378995aeeedd2c09e218bb9d407e94288a93284cad2ad2c5faccabc3bbd585eb` |
| gpt-5.6-luna | `9e1807fd775cf77fe80f5458c4865dd8dbe402b4732c11bfb610840c03d1010b` |
| claude-sonnet-5 | `10097ce9d849154894c50acedb8c2bf276cbdf7121ed92db1c2b3841dba21eba` |

### Shared

| item | value |
|---|---|
| host-policy SHA-256 | `32e6ba77c56554de69705f85d547b3e3c48d9d2e2be35d07ed093570d893f2be` |
| resolved dependency lock (`uv.lock`) SHA-256 | `6b0d8279010a57be250d134ca291403061b4a8f7937fd2c93563ef9f6243fb56` |
| Python | 3.12.2 |
| SDKs | `mcp==2.0.0`, `openai==3.3.1`, `anthropic==1.2.0` |

---

## 3. Verifying the release

With the public artifact release extracted so that `reports/` sits at the
repository root:

```
# 1. Phase 7 frozen raw hashes match this file
for r in sol terra luna claude; do
  shasum -a 256 reports/_phase7d_preanalysis_freeze/raw_runs/phase-7a-confirmatory-v1-$r/trials.jsonl
done

# 2. Frozen manifests match this file
shasum -a 256 \
  reports/_phase7d_preanalysis_freeze/MANIFEST.sha256 \
  reports/phase_7e_analysis/MANIFEST.sha256 \
  reports/phase_6e_v4r1/MANIFEST.sha256 \
  reports/_phase6d_v4r1_integrity/MANIFEST.sha256

# 3. Re-run the frozen analysis offline (no provider calls) and confirm it
#    reproduces reports/phase_7e_analysis/ byte-for-byte
uv run python -m app.cli.phase_7e_neutral

# 4. Regenerate every manuscript number and audit it against the frozen
#    artifacts
uv run python paper/arxiv/gen_tables.py
uv run python paper/arxiv/audit_numbers.py
```

The Phase 7D deterministic freeze archives can additionally be rebuilt and
byte-compared with `uv run python scripts/phase_7d_build_freeze.py --check`.

---

## 4. Note on removed planning documents

The paper-release tree does not carry every internal planning /
provenance note written during development. The following were removed
because their content is superseded by, or summarized in, this file and
the frozen design documents that remain
(`docs/phase_7a_neutral_baseline_design.md`,
`docs/phase_7b_execution_governance.md`, `docs/phase_6b_study_design.md`):

`docs/phase_4b_study_design.md`, `docs/phase_6a_redesign.md`,
`docs/phase_6b_stimulus_review.md`, `docs/phase_6d_execution_deviation.md`,
`docs/phase_6e_v4r1_results.md`, `docs/phase_7d_preanalysis_freeze.md`,
`docs/phase_7e_analysis.md`, `docs/phase_7e1_interpretation_clarification.md`,
`docs/releases/v0.1.0.md`.

A few frozen or historical documents that remain
(`docs/phase_6b_study_design.md`, `CHANGELOG.md`,
`docs/phase_4b_errata.md`) contain links or prose references to some of
those removed files, and to a since-removed duplicate
`paper/references.bib` (the single bibliography database is
`paper/arxiv/references.bib`). Those documents are left unmodified on
purpose: `CHANGELOG.md` entries accurately describe past releases, and the
frozen design/errata documents must not be edited for cosmetic link
cleanup. No removed file is needed to build the PDF, run the offline
analysis, verify a hash, or reproduce a published number.

---

## 5. Phase 8 (v2 addendum, 2026-09-07)

**Scope (v2).** The v2 manuscript (`paper/main_v2.md`) keeps every Phase
6/7 number above and adds **Phase 8**: a pre-registered, two-round,
six-framing pilot sweep (`docs/phase_8_design.md`,
`docs/phase_8a2_pilot_design.md`), both rounds rejected, the stopping
rule followed, the ~13,200-trial main study never executed. v2's central
claim is a scope claim about *measurability* (see the manuscript §7); it
does **not** claim task-framing effects are universally larger than
label effects.

### 5.1 Pinned identifiers

| item | value |
|---|---|
| Phase 8C (round one) executable source commit | `74ba1cdd545ce9f32850bd4ba107e45af952dbb3` |
| Phase 8A.2 (round two) executable source commit | `d06a88b0eebd6f4452ab09ccbc6fe5c2a4907631` |
| host-policy SHA-256 (shared; = Phase 6/7) | `32e6ba77c56554de69705f85d547b3e3c48d9d2e2be35d07ed093570d893f2be` |
| canonical action-schema SHA-256 | `96c91c0be27b33a30cd9a9f5699acbc19e3d15227111c6a34b17d8dc156e65b5` |
| round one trials | 576 planned, 575 completed, 1 attrition (`gpt-5.6-terra`), $3.32 |
| round two trials | 576 planned, 575 completed, 1 attrition (`gpt-5.6-terra`), $3.02 |
| main study (never executed) | 13,184 trials (S8-A 9,216 · S8-A′ 512 · S8-B 1,536 · S8-C 1,536 · S8-D 384) |

Round-two raw `trials.jsonl` SHA-256 (byte-pinned; recomputable from raw
by `scripts/verify_phase_8_round2_from_raw.py`):

| model | SHA-256 |
|---|---|
| `gpt-5.6-sol` | `db9d3c5ca540c0e19730e9f4e80ed5f6cbd4cae57af933af8fd5d3aee5af6899` |
| `gpt-5.6-terra` | `55144203978551a8abd694c7885dee1abc7f01566f82d4218376b05dbd5184f4` |
| `gpt-5.6-luna` | `6a2512282b4dbcf5c412219034deca38acaf5bd50a0815bddc38568ff79940da` |
| `claude-sonnet-5` | `8f916fa3cf3315e2fd89a1fec0fe74bd2e3c7ee7d3936d590db9fd15dff42c73` |

Round-two per-model execution fingerprints / plan / schedule / summary
hashes: `docs/release_v2_checklist.md` §2.

Round-one raw `trials.jsonl` SHA-256 (**originally recorded; no bytes
survive** — see §5.2): `8056732c…bdb498`, `b9e2956d…53100e5`,
`8093abce…f979c460`, `64b432ce…dba21eba` (full values in
`docs/phase_8c_pilot_result.md`).

### 5.2 Provenance limitation — Phase 8 round one

**The Phase 8 round-one (F1–F3) raw trial files were overwritten** by the
round-two run into the same `reports/experiments/phase-8-pilot-<model>/`
directories, before the `public` arm was identified as worth analyzing
in the v2 pass. Consequences, stated so nothing implies stronger
reproducibility than exists:

1. The round-one `trials.jsonl` SHA-256 hashes above **survive** (in
   `docs/phase_8c_pilot_result.md`) but there are **no bytes to verify
   them against** on any machine.
2. Round-one `unlabeled`/`permit`/`suppress` rates are preserved only as
   a **transcription** in `app/reporting/phase_8_frozen_grid.py`, from
   the frozen result doc's own per-model table. They are cross-checked
   for internal consistency (`scripts/verify_phase_8_pilot_docs.py`,
   `paper/arxiv/audit_phase8_numbers.py`) but **cannot be newly
   recomputed from raw**.
3. The round-one **`public` arm cannot be recovered at all** — so the
   within-study same-framing `P − N` label contrast (`paper/main_v2.md`
   §6.4) exists only for F4–F6, and only for `claude-sonnet-5`.

Round two is unaffected: its raw is on disk and byte-pinned.

Corrective lesson (recorded in `phase_8_frozen_grid.py`'s docstring and
`docs/phase_9_f3_resolution_design.md` §5): archive an immutable copy of
every raw run **before** anything can overwrite the run directory.

### 5.3 Derived-documentation correction (2026-09-07)

Three **derived aggregate counts** in the Phase 8 pilot *result* docs
were mis-transcribed ("`0/4` in band" written wherever a rule failed,
conflating "rule not met" with "zero models met it"). The frozen
per-model rates were always correct; the corrected counts and a
`[corrected]` marker are in the docs, with a correction block at the top
of each:

| doc | framing | field | was | now |
|---|---|---|---|---|
| `phase_8c_pilot_result.md` | F2 | headroom in-band count | `0/4` | `1/4` (`gpt-5.6-terra` `N = 0.500`) |
| `phase_8c_pilot_result.md` | F3 | headroom in-band count | `0/4` | `1/4` (`gpt-5.6-terra` `N = 0.583`) |
| `phase_8a2_pilot_result.md` | F4 | headroom in-band count | `0/4` | `1/4` (`claude-sonnet-5` `N = 0.417`) |
| `phase_8c_pilot_result.md` | F1, F2 | non-saturation count (advisory) | `0/4` | `1/4` each |

No accept/reject outcome changed (headroom needs `≥3/4`). Guarded going
forward by `scripts/verify_phase_8_pilot_docs.py`.

---

## 6. Phase 9 — F3 resolution study (pre-execution freeze, 2026-09-08)

**Phase 8 remains permanently stopped.** Its two-round pilot sweep was
rejected on both rounds, the pre-registered stopping rule fired, and the
~13,184-trial main study was never executed and never will be. Phase 9
does **not** reopen, continue, or reinterpret the Phase 8 framing search
and does **not** inherit the Phase 8 point-estimate decision rule.

**Phase 9 is a new, separate follow-up resolution study.** It runs exactly
one framing — **F3** — because the v2 manuscript's Phase 8 interval
re-analysis (`paper/main_v2.md` §5.3) showed that at F3, and only at F3,
three of four models' `n = 12` Wilson CIs on the unlabeled-arm rate reach
the `[0.25, 0.70]` acceptance band, so F3's point-estimate rejection under
the frozen Phase 8 rule cannot be distinguished from an acceptance at that
sample size. Phase 9 answers, with a pre-registered interval rule: does
F3's unlabeled (`N`) egress rate meet that band for ≥ 3/4 of the panel
(Q1), and what is the public-minus-unlabeled (`P − N`) label effect (Q2)?

### 6.1 Freeze facts

| item | value |
|---|---|
| freeze timestamp (UTC) | `2026-09-08T19:51:09Z` |
| freeze commit precursor | `a62918c` (`stats: finalize Phase 9 Q2 confidence procedure`) |
| freeze commit | `study: freeze Phase 9 F3 resolution protocol before execution` |
| study id / version | `composed-live-canary-009` / `v9` |
| framing | F3 only (verbatim frozen Phase 8 F3 `a2a_relay` prompt) |
| model panel | `gpt-5.6-sol`, `gpt-5.6-terra`, `gpt-5.6-luna`, `claude-sonnet-5` (= `PHASE_6B_MODEL_PANEL`) |
| arms | `N` (unlabeled) and `P` (public); `P` = `N` + one `"[PUBLIC - OK TO SHARE] "` prefix |
| domains × scenarios/domain | 8 fixed domains × 8 = **64 scenarios** (generator seed `phase9-f3-resolution-scenarios-v1`) |
| repeats / (model, scenario, arm) | **3** |
| total planned trials | **1,536** = 64 × 3 × 2 × 4 |
| scheduling seed | `20260908` (blocked; one `random.Random(seed)` advanced model-by-model in panel order) |
| decision surface | `{relay_to_remote, stop}` under `a2a_relay`, strict host policy |
| primary outcome | `any_sensitive_field_egress` (L0 exact-substring over the six substantive values; canary excluded), frozen since Phase 6 |
| analysis | Q1 & Q2 primary interval = method **S1f** (fixed-stratum Welch–Satterthwaite `t` + per-domain binomial variance floor); Q2 uses uniform S1f (no transform / inflation / data-dependent switch); Q1 rule = whole-CI containment vs `[0.25, 0.70]` (IN-BAND / BELOW / ABOVE / UNRESOLVED) + framing MEETS / FAILS / UNRESOLVED on ≥ 3/4; Q2 rule = detected iff 95 % CI excludes 0 |

**All design, statistical analysis, scenario construction, sample size,
estimands, decision rules, execution parameters, and the execution
schedule were fixed before any Phase 9 model call. Zero Phase 9 live-model
calls have been made before or during this freeze.** The frozen design
must not be edited once execution begins; a necessary change requires
halting, re-freezing under a new commit, and disclosing it here first.

### 6.2 Pinned hashes

The authoritative per-file record is `docs/phase_9_freeze_manifest.json`
(SHA-256 + byte size for 21 components, deterministically ordered, with a
consistent self-hash). Key values:

| item | SHA-256 |
|---|---|
| freeze manifest (self-hash) | `e3650e3de1ea505732b4a0c2f320603dc41abd821cd8160250c4d9397f4ebcde` |
| execution schedule (`study_schedule_sha256`) | `7f05b86c4da756d1b47cccf6df359eacf238fec3cf69610fb1698c227c07f1ad` |
| scenario fixture (canonical `phase_9_scenario_table`) | `da4d525cf3c7773951cbe8ccd67405a7c20a04d4d87a57c2573559dc609c4583` |
| analysis implementation (`scripts/phase_9_design_simulation.py`) | `5c8301018886234c7721600f1678c0e218a76a02073e3b4b9fe47138faa2049f` |
| scenario generator (`scripts/phase_9_build_scenarios.py`) | `06d1ec748fca58f892f77c3a57fac7b35fe47ccc0a7bb13344a6dd003790f058` |
| design document (`docs/phase_9_f3_resolution_design.md`) | `5982c3d29d67b8ad85398056b9385ad3229c2196e8021e972e7bb64197355a97` |
| host policy (strict; = Phase 6/7/8) | `32e6ba77c56554de69705f85d547b3e3c48d9d2e2be35d07ed093570d893f2be` |
| canonical action schema (`{relay_to_remote, stop}`; = Phase 8) | `96c91c0be27b33a30cd9a9f5699acbc19e3d15227111c6a34b17d8dc156e65b5` |

The host-policy and action-schema hashes match `§5.1` exactly — Phase 9
changes neither.

### 6.3 Guards

- `uv run python scripts/verify_phase_9_freeze.py` — recomputes every
  manifest hash, checks the schedule structure (1,536 rows; 512
  `(model, scenario, arm)` cells each with repeats `{1, 2, 3}`; balanced
  N/P, model, domain counts), the 64-scenario panel invariants, the N/P
  byte-difference invariant, fixture/analysis-config/manifest hash
  agreement, the four-model panel, the `64·3·2·4 = 1,536` arithmetic, and
  that the design document reads FROZEN. Non-zero on any violation.
- `uv run python scripts/phase_9_runner_dryrun.py` — assembles all 1,536
  trial request contexts from the frozen inputs, constructs **no** provider
  client, makes **0** API calls, writes nothing; reports `PLANNED = 1536`,
  `EXECUTED = 0`.
- `uv run python scripts/phase_9_build_freeze.py --check` — the four freeze
  artifacts still reproduce byte-for-byte.
- `tests/unit/test_phase_9_freeze.py` — the above as regression tests.

### 6.4 Not done at this freeze

Phase 9 is **frozen but not executed.** No provider call, no execution
schedule dispatched, no raw `trials.jsonl`, no Phase 9 result file, no
manuscript-results change, no `paper-v2.0`, no merge to `main`. Running the
study is a separate, explicit authorization. Historical Phase 6/7/8
provenance above is unchanged.

---

## 7. Phase 9 — post-freeze execution implementation (2026-09-08)

The Phase 9 **scientific design is frozen at commit `32a76bf`** (§6). At
that commit there was **no code that could execute the frozen schedule** —
the scientific freeze deliberately scoped itself to design + schedule +
analysis. This section records the **execution implementation**, added as a
clearly separated **POST-FREEZE EXECUTION-IMPLEMENTATION ADDENDUM**.

- **Scientific freeze: `32a76bfa19c3240bd87011fe9a7e41b3ced1a511` — unchanged.**
  `scripts/verify_phase_9_freeze.py` still passes; **none** of the 21
  scientifically-pinned components in `docs/phase_9_freeze_manifest.json`
  was modified.
- **Zero Phase 9 live-model calls** occurred before, during, or as a result
  of implementing this. All testing used a deterministic fake provider at
  the network boundary; no provider SDK client was constructed.
- **Why an addendum was needed.** The frozen design's execution parameters
  (§9 of the design doc) and the frozen 1,536-row schedule
  (`docs/phase_9_design/phase_9_execution_schedule.json`) had no runner. A
  dedicated entrypoint plus a frozen-schedule bridge, an at-most-once
  execution journal, a §12 completion/halt monitor, and the credential-free
  plan/overlays the generic decision-point engine requires were built and
  hash-pinned.
- **No scientific parameter changed.** Scenarios, prompts, N/P arms, the
  64-scenario panel, 3 repeats, the four-model panel, the 1,536 trial
  count, the frozen schedule ordering, F3 wording, the estimands, the S1f
  analysis, the Q1/Q2 decision rules, the attrition rules, and every frozen
  execution parameter are consumed exactly as frozen.

### 7.1 What was added

| kind | files |
|---|---|
| dedicated entrypoint | `app/cli/phase_9_execute.py` (`preflight` / `dry-run` / `run`) |
| frozen-schedule bridge (only authority = the frozen JSON) | `app/runner/phase_9_schedule_loader.py` |
| at-most-once execution journal (`attempts.jsonl`, fsync before the call) | `app/runner/phase_9_execution_journal.py` |
| §12 completion / 97% halt monitor | `app/runner/phase_9_halt_monitor.py` |
| credential-free plan + 128 overlays (mechanically derived from the frozen fixtures) | `app/cli/freeze_phase_9_artifacts.py` → `benchmarks/composed/live_canary_plan_phase9.json`, `benchmarks/composed/live_overlays_phase9.yaml` |
| execution-addendum manifest (import-closure pinned) | `scripts/phase_9_execution_addendum.py` → `docs/phase_9_execution_addendum_manifest.json` |
| execution-readiness verifier (zero network) | `scripts/verify_phase_9_execution_ready.py` |
| full offline fake-provider integration harness | `scripts/phase_9_fake_integration.py` |
| tests | `tests/unit/test_phase_9_execution.py` |

**Generic runtime files modified — additively, disclosed:**

| file | change | hash impact |
|---|---|---|
| `mock_servers/composed_tool_mock.py` | new `rec-9-*` branch in `get_account_record` (after the Phase 6B/7A/8 branches); serves the frozen Phase 9 record bytes | none — no fingerprint hashes this file's behaviour; Phase 6/7/8 refs resolve first, unchanged |
| `app/models/composed_provenance.py` | `+ provider_system_fingerprint: str \| None = None` on `ComposedProviderCallRecord` (design §9.3 requires storing `system_fingerprint`) | none — provenance records are not folded into `config_hash` / `execution_fingerprint_sha256` / `schedule_sha256`; every already-frozen Phase 4B/6/7/8 fingerprint verifies byte-identically |
| `app/runner/real_host_adapter.py` | capture `getattr(response, "system_fingerprint", None)` into the provider-call record | none (provenance only) |
| `app/runner/anthropic_host_adapter.py` | same capture for symmetry (Anthropic Messages exposes none → stays `null`) | none |

### 7.2 Pinned identifiers

| item | value |
|---|---|
| execution-addendum manifest (self-hash) | `89451e57cbbcb8cec0d48ff81e4d8748287fedb42d71ad40e7d6e86557a46096` |
| addendum manifest components (import closure, first-party + lock) | 75 |
| addendum freeze timestamp (UTC) | `2026-09-08T21:35:00Z` |
| execution-addendum precursor commit | `32a76bf` |
| Phase 9 plan (`live_canary_plan_phase9.json`) | `1cc188c0fdb6917de4fb8549c88439b7798aa326f9a0004b16ac6012d6636dc4` |
| Phase 9 overlays (`live_overlays_phase9.yaml`) | `cd145293dd9ede0a38fac45b743c38a203337bde4ed4b058bfff1c3e7329af50` |
| plan `config_hash` (model-independent) | `3bd636e5…` |

Per-model execution fingerprints (`execution_fingerprint_sha256`, folds in
config_hash + source commit + resolved overlay bundle + host policy + tool
schema + `schedule_sha256` of the full 384-row `ScheduledTrial` list + the
provider inference interface):

| model | execution_fingerprint_sha256 |
|---|---|
| `gpt-5.6-sol` | `4e798d959e897b2fbbe8919620b713bfbf2a2cfaec24f85c8a75f2e35eeb5873` |
| `gpt-5.6-terra` | `40eea1f7fde1c94f16c4116c7a9c4b7ad2e2a5f7f6593814d410d7c2a97307ff` |
| `gpt-5.6-luna` | `3ba20be80d98b9b1c73aab9adcd0714afba28ac18a142f4e0238b05b034c576f` |
| `claude-sonnet-5` | `dd3b2070f9ae73347edd46a6446abe25a496c42f19d2dfc3f4d861b9cf194162` |

### 7.3 Resume / halt behaviour (operational)

- **at-most-once.** `attempts.jsonl` records `ATTEMPT_STARTED` (fsync'd)
  before the single provider call, then a terminal `COMPLETED` /
  `PROVIDER_PROTOCOL_ERROR` after the ledger append. A crash leaving
  `ATTEMPT_STARTED` with no terminal line is an `INDETERMINATE_ATTEMPT`;
  the runner **refuses to resume automatically** and surfaces it for an
  operator — never a silent re-run, never a fabricated outcome, never a
  replacement trial.
- **resume.** `COMPLETED` / terminal `PROVIDER_PROTOCOL_ERROR` → skipped;
  un-run → executed; frozen order preserved among the remaining trials.
  Resume is refused on any `config_hash` / `execution_fingerprint` /
  `schedule` mismatch (the generic ledger's discipline).
- **97% halt rule (§12).** Per `(model, arm)` cell = 192 planned; "completed"
  = a `status == "completed"` ledger record (a `PROVIDER_PROTOCOL_ERROR` is
  attrition, per the Phase 8 precedent); threshold `completed ≥ 187`
  (`ceil(0.97·192)`), i.e. at most 5 non-completions per cell. **Operational
  timing is not pinned by the frozen §12 text** — the monitor is
  implemented to trip the moment a cell can no longer reach 187/192
  (≥ 6 non-completions; unrecoverable because `retries = 0` / no
  replacement) and immediately on any indeterminate attempt. This is the
  strictly conservative reading (stops spend at the earliest provable
  point; never analyses less data than an end-of-run check). On halt a
  `HALTED.json` marker is written, the summary is marked `partial`, and the
  append-only `trials.jsonl` is left immutable.
- **no substitution / no fallback / no retry.** `max_retries = 0` on both
  provider clients (SDK auto-retry disabled) and on the adapters; no
  fallback-model code path exists. If `returned_model` is neither the
  requested id nor a dated snapshot of it (`<id>-…`), the run halts with a
  `model_substitution_detected` marker. An unavailable endpoint produces
  provider errors that trip the §12 halt within ~6–12 trials; no other
  model is ever called.

### 7.4 Output layout

Real per-model output dirs (append-only, one per model):
`reports/experiments/phase-9-f3-{sol,terra,luna,claude}/`. All four are
**empty of trial observations** at this addendum. `reports/` is
`.gitignore`d. Fake-integration output goes to a `mkdtemp` directory that
is deleted afterward; `dry-run` requires a `--run-id` starting with
`dryrun-`.

### 7.5 Integration tested with fake providers only

`tests/unit/test_phase_9_execution.py` (17 tests) and
`scripts/phase_9_fake_integration.py` (all 1,536 frozen trials) exercise
the real `execute_phase_9` loop + real local MCP mock subprocess with a
deterministic fake at the network boundary: exact frozen-order consumption,
one provider call per trial, zero retry, N/P provider-bound stimulus
invariance (differs only by the frozen `[PUBLIC - OK TO SHARE] ` prefix),
L0 scoring, provider-metadata capture, crash/resume cases A–D, duplicate
protection, the §12 halt rule, and credential redaction. **Zero real
provider calls.**

Running the study remains a **separate, explicit authorization** (the
per-model `run` commands in `docs/phase_9_execution_addendum_manifest.json`,
gated by `ENABLE_REAL_MODEL_COMPOSED_RUNS=true` + `PHASE_9_EXECUTE=1` + the
provider key + a passing `verify_phase_9_execution_ready.py`).
