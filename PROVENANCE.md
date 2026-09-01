# Provenance

This file is the single, durable record of the frozen chronology and all
byte-pinned identifiers behind the paper
(`paper/arxiv/main.tex` / `paper/main.md`). It replaces the per-phase
provenance notes that were kept during development.

Scope: the paper reports the **Phase 7** three-arm neutral-baseline study
(`composed-live-canary-007a` / `v7a`) as the primary study, and the
**Phase 6** two-arm confirmatory study (`v4r1`) as a descriptive
comparison and as the source of the secondary null experiment and the
harness enforcement property. **Phase 6 and Phase 7 observations are never
pooled.**

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
