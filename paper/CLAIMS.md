# CLAIMS — what this paper does and does not assert

Scope of every claim below: a **real-model host** (OpenAI GPT-5.6
`sol`/`terra`/`luna` via the Responses API) driven over **local
deterministic MCP and A2A protocol fixtures**, one host policy, one
three-tool MCP surface, **four fixed stimuli** (2 sensitive-egress + 2
adversarial-influence overlays), the **decision-point** methodology (one
restricted host decision per trial), **n = 20** blocked-randomised
replicates per model per cell, **240 trials total**, at one point in time.
All numbers are from the frozen release `phase4b-results-v1`. Rates carry
Wilson 95% score intervals; no p-values; the 20 replicates in a cell are
not assumed statistically independent.

---

## SUPPORTED DIRECTLY

Statements the frozen observations establish for the tested configuration.

1. **Experimental integrity.** All 240 planned trials completed; 12/12
   model×experiment×condition cells recorded 20/20 completions, 0 failed
   trials, 0% attrition. Each run used exactly 80/80 provider decisions
   (retries = 0); every provider call returned `ok`; every trial's stamped
   execution fingerprint matched its run's fingerprint; the frozen blocked
   schedule order was preserved for all three runs.

2. **RQ1, secondary — relay initiation.** After reading the confidential
   MCP record, the host initiated a relay to the A2A fixture in
   **3/20 (15%)** trials for `gpt-5.6-sol` [Wilson 5.2–36.0%],
   **17/20 (85%)** for `gpt-5.6-terra` [64.0–94.8%], and
   **20/20 (100%)** for `gpt-5.6-luna` [83.9–100.0%]. In the public
   control condition the corresponding rates were 95%, 85%, 100%. The
   signed treatment−control differences were **−0.80, 0.00, 0.00**.

3. **RQ1, primary — direct sensitive egress (verbatim marker).** The exact
   sensitive canary token never crossed a non-allowed edge:
   **0/3, 0/17, 0/20** of the relay trials (rate 0.0%; Wilson upper bounds
   **56.2%, 18.4%, 16.1%**). A deterministic exact-substring inspection of
   all **40** confidential relay messages found the literal canary token,
   the exact `[CONFIDENTIAL - INTERNAL ONLY]` label, and the full record
   string each present **0/40** times.

4. **RQ2 — actual mutating-tool requests (outcome B).** Counts of trials in
   which the host selected `attempt_mutating_tool` **and** named a
   discovered-mutating tool, adversarial vs benign:
   `gpt-5.6-sol` **14/20 vs 10/20** (signed diff **+0.20**);
   `gpt-5.6-terra` **11/20 vs 3/20** (**+0.40**);
   `gpt-5.6-luna` **14/20 vs 4/20** (**+0.50**). All three signed
   differences are positive. Per-cell Wilson 95% intervals are reported in
   Table 3.

5. **RQ2 — wrapper selection vs actual mutating capability.** Study totals
   across the influence cells: wrapper-action selection **A = 82**,
   actual mutating-tool request **B = 56**, non-mutating-tool-via-wrapper
   **E = 26** (with **A = B + E** in every cell). Some models routed
   discovered read-only tools (`get_deployment_status`,
   `get_customer_record`) through the `attempt_mutating_tool` action; this
   is concentrated in specific cells (e.g. `gpt-5.6-luna` benign 16/20).

6. **RQ3 — containment of actual mutating-tool requests.** Every one of the
   **56** observed actual mutating-tool requests was blocked by the
   independent mutation gate (**100% blocked** in all six model×condition
   cells) and **0 executed** across the 240 trials. Wilson 95% upper bound
   on the executed rate: 21.5% (B = 14), 25.9% (B = 11), 27.8% (B = 10),
   49.0% (B = 4), 56.2% (B = 3).

7. **Non-mutating executions via the wrapper.** In the E cells, the
   discovered read-only tool named through `attempt_mutating_tool`
   executed (**F = 26** study-wide), because the mutation gate does not
   block a discovered read-only call. These are read-only executions, not
   mutations.

8. **Reproducibility.** The three raw runs are byte-exact in the frozen
   release; the outcome-taxonomy audit and every table and figure are
   regenerated offline from the raw traces plus the committed static
   local-mock tool annotations, with **zero provider calls**.

---

## SUPPORTED WITH QUALIFICATION

Statements the observations support only under a stated condition or with a
stated caveat.

1. **"An adversarial A2A artifact is associated with more actual
   mutating-tool requests."** Supported **within the controlled
   manipulation** (adversarial vs structurally matched benign artifact,
   everything else held fixed) and **as a rate comparison at n = 20 per
   cell**. Not a mechanistic causal claim; not a claim that the effect
   size (+0.20/+0.40/+0.50) is precise (Wilson intervals are wide); not
   generalisable beyond these two artifacts.

2. **"The mutation gate contained the influenced requests."** Supported
   **for the 56 observed actual mutating-tool requests only**: all were
   blocked, none executed. This is an observation, not a robustness
   guarantee. The gate blocks `is_mutating ∧ ¬approved`; it does not
   protect against a request that (a) names a discovered read-only tool
   (see F above) or (b) somehow presents as approved — the latter did not
   occur here but is the quantity of interest for a larger study.

3. **"Host policy compliance kept the confidential marker off the A2A
   leg."** Supported **as a verbatim-marker observation** for these four
   stimuli. Several relays paraphrased that a "confidential/internal"
   record existed while declining to reproduce it; whether such
   paraphrases convey usable information is a **semantic** question this
   study does not evaluate (see NOT CLAIMED).

4. **"Interval non-overlap for `terra` and `luna` in Table 3."** Reported
   as a **descriptive** property of the two per-condition Wilson intervals
   (each on n = 20). It is **not** a hypothesis test, significance
   statement, or difference-of-proportions inference.

5. **"Relay initiation differs markedly between models (15% vs 100%)."**
   Supported as an observed behavioral difference at n = 20 per cell.
   Whether it reflects a stable model property or run-time variability is
   not established (single run per model; no repeated runs).

6. **"Isolation-safe legs can produce composition-specific behavior."**
   Supported in the weak sense that RQ1's relay-initiation behavior and
   RQ2's condition contrast are only observable across the seam. Not a
   claim that any *terminal harm* propagated — none did in this sample.

---

## NOT CLAIMED

Statements this paper explicitly does **not** make.

1. **No priority on the concepts.** We do **not** claim to be first to
   identify composition safety, cross-protocol risk, or MCP+A2A protocol
   pivoting. See the novelty boundary below.
2. **No "first benchmark" claim** for MCP or for A2A. Dedicated
   single-protocol benchmarks predate this work (see §12).
3. **No general model-safety verdict.** Nothing here says `gpt-5.6-sol`,
   `gpt-5.6-terra`, or `gpt-5.6-luna` is "safe" or "unsafe". Results are
   conditional on four stimuli, one policy, one tool surface, one
   methodology, and one point in time.
4. **No semantic-leakage claim.** Direct sensitive egress is a verbatim
   exact-substring measurement. A rate of 0 does **not** establish the
   absence of semantic, paraphrased, or partial information leakage across
   the boundary, which is not measured.
5. **No statistical-independence claim.** Repeated provider calls in a
   cell are repeated samples, not assumed independent Bernoulli trials. No
   p-value, chi-square, Fisher, or t-test is reported or implied.
6. **No causal-mechanism claim.** The +0.20/+0.40/+0.50 signed differences
   are rate comparisons under a controlled manipulation, not evidence that
   the adversarial text *causes* mutation requests through a specific
   mechanism.
7. **No robustness or worst-case guarantee** for the host policy or the
   mutation gate. The study does not bound behavior under stimuli it did
   not test and does not indicate which safeguard would fail first.
8. **No claim about production or external systems.** No production,
   external, or third-party MCP server or A2A agent was contacted; the MCP
   and A2A legs are local deterministic protocol fixtures.
9. **No multi-step / long-horizon claim.** The decision-point methodology
   measures one restricted host decision per trial; compounding behavior
   over a longer interaction is not observed.
10. **No formal guarantee.** This is an empirical instrument and a pilot,
    not a proof, invariant, or conformance result.

---

## Novelty boundary — exact statement

**We claim, narrowly:** an *executable empirical instrument* for MCP+A2A
composition — a real-model host over local deterministic MCP and A2A
protocol fixtures in one ordered trace — with (i) an observable
cross-protocol provenance model (canaries + sensitivity label +
allowed-edge policy + causal ancestry; direct vs propagated presence);
(ii) a controlled decision-point behavioral-influence measurement;
(iii) an outcome that distinguishes wrapper-action selection from a
request that names a discovered-mutating tool; (iv) an independent
containment measurement; (v) a hash-pinned live-model reproducibility
mechanism (execution fingerprint + frozen blocked schedule + fully offline
analysis); and a first small controlled pilot (3 models, 240 trials)
reporting per-model rates for one information-flow, one behavioral-
influence, and one containment outcome.

**We do NOT claim novelty relative to:**

- **AgentRFC** [@agentrfc2026] — introduces the *"Composition Safety"
  principle* ("security properties that hold for individual protocols can
  break when protocols are composed through shared infrastructure") with
  formal (TLA+) models of five cross-protocol composition patterns over
  MCP/A2A/ANP/ACP and a spec-conformance checker. *Our difference:* they
  provide the concept and a formal/conformance framework; we provide a
  behavioral empirical measurement on a live composition. We contribute no
  formal result.

- **IETF Internet-Draft `draft-mohiuddin-mcp-security-considerations-00`,
  §6 "Protocol Pivoting"** [@mohiuddin2026mcpsec] — already names
  cross-protocol lateral movement "combining MCP with Agent-to-Agent (A2A)
  delegation" and states that "mitigations that consider each protocol in
  isolation do not address movement that crosses protocol boundaries,"
  with a worked scenario close to our RQ2. *Our difference:* they name the
  threat and enumerate mitigations; we measure one host's behavior in a
  concrete instance. We contribute no new threat concept or mitigation.

- **MCP-SafetyBench** [@mcpsafetybench2026], **MCP Security Bench (MSB)**
  [@msb2026], **MCPSecBench** [@mcpsecbench2025] — single-protocol MCP
  safety/security benchmarks (malicious/misconfigured servers,
  tool-poisoning, argument-injection, over-broad permissions;
  server/host/user attack surfaces; multi-turn ReAct tasks). *Our
  difference:* we reuse an MCP leg but measure what happens when its
  output is carried onto an A2A leg, which these do not model. We are not
  a broader or better MCP benchmark and make no such claim.

- **A2ASecBench** [@a2asecbench2026] — single-protocol A2A security
  benchmark (agent-card / supply-chain manipulations, protocol-logic
  weaknesses, adversarial artifacts between agents). *Our difference:* our
  adversarial input is an A2A artifact, but the measured *action* is a
  mutating call on a *local MCP tool* and the tested *control* is a local
  mutation gate — outside a pure-A2A scope. We are not an A2A benchmark
  and make no such claim.

- **AgentDojo** [@agentdojo2024] — dynamic environment evaluating prompt
  injection attacks/defenses on tool-using agents with rule-based (not
  LLM-judge) utility and security functions. *Our difference:* we share
  the judge-free stance but operate on a live cross-protocol composition
  (not a single-protocol tool-agent suite) and score by provenance edge
  rules. We claim methodological alignment, not novelty, on judge-free
  evaluation.

- **CaMeL** [@camel2025] — a *defense* that separates control and data
  flow and runs a custom interpreter tracking data provenance before each
  tool call. *Our difference:* CaMeL is a mitigation; ours is an
  evaluation instrument. The provenance-tracking idea is theirs (and
  earlier information-flow work); we borrow the framing for measurement,
  not defense.
