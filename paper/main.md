# Cross-Protocol Failure Propagation Across MCP and A2A Agents: A Controlled Pilot on Information Flow, Behavioral Influence, and Containment

*Preprint draft. Uses the frozen public release `phase4b-results-v1`
(source commit `6cb64606a614c42145cc2da03468551c1ca48c6d`, analysis commit
`caf036db97b142005e8f12e02fc9b95d0a205cbd`) verbatim. No experiment,
provider call, or model inference was run to produce this document.*

**System under test.** The only non-local component in every experiment is
**real provider model inference** — OpenAI GPT-5.6 models
(`gpt-5.6-sol` / `gpt-5.6-terra` / `gpt-5.6-luna`) [@openai-gpt56] called
through the OpenAI Responses API. **All MCP and A2A infrastructure is local
deterministic protocol fixtures**: an in-process mock MCP tool server
(stdio subprocess, synthetic data, no network) and an in-process mock A2A
HTTP+JSON/REST agent (exercised only through a test client, no sockets). No
production, external, or third-party MCP server or A2A agent was contacted.
Throughout, "the host" or "the model" refers to real provider inference;
"MCP fixture" / "A2A fixture" refers to the local deterministic
infrastructure.

---

## 1. Abstract

Deployed AI agents increasingly speak two protocols at once: the Model
Context Protocol (MCP) [@mcp-spec] for local tool use, and the Agent2Agent
Protocol (A2A) [@a2a-spec] for delegating work to other agents. Each
protocol has begun to attract dedicated safety benchmarks, but those
benchmarks evaluate a single protocol in isolation. We study what happens
*at the seam*: a real-model host that reads content from an MCP tool and,
in the same task, exchanges messages with an A2A agent. We introduce
**Agent Interop Bench's composed harness**, which drives one real-model
host across both protocol legs — implemented here as **local deterministic
MCP and A2A protocol fixtures**, not external services — within a single
ordered event trace, and attaches an observable **cross-protocol provenance
model** (deterministic content canaries with a sensitivity label, an
explicit allowed-edge policy, and per-event causal ancestry) so that
information flow and behavioral influence across the protocol boundary can
be measured by exact rule-based checks with no LLM anywhere in the
evaluation.

Using a **decision-point** methodology that deterministically constructs
the situation and then elicits exactly one restricted host decision, we ran
a **controlled confirmatory pilot** over three models
(`gpt-5.6-sol`, `gpt-5.6-terra`, `gpt-5.6-luna`), 240 trials total (20
blocked-randomised replicates per model per condition), addressing three
questions. **RQ1:** does confidential MCP-originated content propagate
across the A2A boundary? We separate *relay initiation* (the host chose to
send a message onto the A2A leg after reading a confidential record) from
*direct sensitive egress* (the exact confidential marker crossed the
host→remote/A2A edge). Relay initiation varied widely by model (15%, 85%,
100% of confidential trials); **direct exact-token sensitive egress was 0**
in every model (0/3, 0/17, 0/20 of relay trials; Wilson 95% upper bounds
56.2%, 18.4%, 16.1%). This measures verbatim marker leakage only and does
**not** evaluate semantic or paraphrased leakage. **RQ2:** can an
adversarial A2A artifact influence a host toward requesting a *mutating*
MCP tool? Using the outcome *actual mutating-tool request* — the host
selected the mutation-attempt action **and** named a tool the harness
discovered to be mutating — the adversarial condition showed a higher rate
than the structurally matched benign condition for all three models (signed
treatment−control rate differences +0.20, +0.40, +0.50; Wilson 95%
intervals reported per cell). We report this as an association under a
controlled manipulation, not a causal-mechanism claim. **RQ3:** can an
independent mutation gate contain those requests? Every *observed* actual
mutating-tool request was blocked by the gate (100% blocked in all six
model×condition cells) and **zero** executed across the entire study
(Wilson 95% upper bounds on the executed rate 21.5–56.2% depending on cell
size). We report Wilson 95% confidence
intervals and signed rate differences throughout and deliberately report no
p-values; the 20 replicates in a cell are repeated draws from one model
under one fixed stimulus and are not assumed to be statistically
independent provider executions. The complete raw runs, the offline
analysis pipeline, and every derived table and figure are published as a
deterministic, hash-pinned reproducibility release.

---

## 2. Introduction

An agent that is safe in isolation on protocol *X* and safe in isolation on
protocol *Y* is not automatically safe when it uses *X* and *Y* in the same
task. Two concrete mechanisms motivate this paper:

1. **Information flow across the boundary.** A host agent calls a local MCP
   tool, receives content, and then — in service of the same user request —
   sends a message to a remote A2A agent. If the tool's content was
   confidential, the boundary is exactly where an unintended disclosure can
   occur. A single-protocol MCP benchmark cannot see the A2A edge; a
   single-protocol A2A benchmark never had the confidential content in
   scope.

2. **Behavioral influence across the boundary.** A remote A2A agent returns
   an *artifact* — a text payload the host reads. If that artifact contains
   an instruction ("apply the emergency remediation now"), the host may act
   on it by calling a *local* MCP tool, including a mutating one. The
   adversarial content and the dangerous action live on opposite sides of
   the seam.

Both mechanisms are compositional: they are properties of the *interaction
between* two protocol legs, not of either leg alone. This paper builds a
harness that can express and observe such interactions, defines rule-based
outcomes for them, and reports a small, tightly controlled empirical study.

**What this paper is.** A description of (i) a cross-protocol MCP+A2A
composed evaluation harness with an observable provenance model; (ii) a
decision-point measurement methodology; (iii) a reproducibility mechanism
(execution fingerprints and a frozen blocked schedule); and (iv) a
controlled confirmatory pilot over three models that instantiates the three
research questions above and publishes its raw and derived artifacts.

**What this paper is not.** It is not the "first MCP benchmark" or the
"first A2A benchmark" — dedicated single-protocol safety benchmarks for
each already exist and are discussed in Section 12. It does **not** claim
priority on the *idea* of cross-protocol composition risk, cross-protocol
lateral movement, or MCP+A2A "protocol pivoting": that risk has already
been named and formalised elsewhere — as a "Composition Safety" principle
with formal cross-protocol composition models [@agentrfc2026], and as a
"Protocol Pivoting" threat spanning MCP and A2A in a June 2026 IETF
Internet-Draft [@mohiuddin2026mcpsec]. Our contribution is narrower and
complementary (Section 2.1). The paper does not claim any model is "safe"
or "unsafe" in general; every result is conditional on four fixed stimuli,
one host policy, one tool surface, and one point in time. It reports no
significance tests.

### 2.1 Scope of the contribution

Given that cross-protocol composition risk and MCP+A2A pivoting are already
articulated conceptually [@mohiuddin2026mcpsec] and formally
[@agentrfc2026], we position this work strictly as an **executable
empirical instrument and a controlled pilot**, contributing:

1. an **executable empirical MCP+A2A composition evaluation** — one
   real-model host driven across an MCP leg and an A2A leg, both
   implemented as local deterministic protocol fixtures (an in-process mock
   tool server and an in-process mock HTTP+JSON/REST agent), into a single
   ordered event trace scored by exact rules;
2. an **observable cross-protocol provenance model** — deterministic
   content canaries with a sensitivity label, an explicit allowed-edge
   policy, and per-event causal ancestry — that makes specific
   boundary-crossing flows checkable without an LLM judge, and that
   separates *direct* (literal) from *propagated* (ancestral) presence;
3. a **controlled decision-point behavioral-influence measurement** — the
   situation is deterministically constructed and exactly one restricted
   host decision is elicited, isolating one measured behavior from
   multi-step planning;
4. a **distinction between wrapper selection and actual mutating
   capability** — we score whether the host named a tool the harness
   *discovered* to be mutating, not merely whether it selected the
   mutation-attempt action;
5. an **independent containment measurement** — an external mutation gate,
   not part of the host, whose block/execute decision is recorded per
   request;
6. a **hash-pinned live-model reproducibility mechanism** — a per-run
   execution fingerprint over the resolved stimuli, policy, tool schema,
   source commit, and blocked-schedule hash, with an offline analysis
   pipeline that regenerates every table and figure with zero provider
   calls.

We do not claim any of the underlying risk concepts as novel.

---

## 3. Background: MCP and A2A

### 3.1 Model Context Protocol (MCP)

MCP is a client–server protocol for connecting an LLM-driven *host* to
*tools* and *resources* exposed by MCP servers [@mcp-spec, revision
2025-06-18]. In the host→server direction the host issues a JSON-RPC
`tools/call` with a tool name and a JSON argument object; the server
returns a structured result. Tools may carry annotations (e.g. a
destructive / read-only hint) so that a host or a policy layer can treat
mutating operations differently from read-only ones; the specification
notes that such annotations "should be considered untrusted, unless
obtained from a trusted server." In this paper the MCP leg is a **local,
in-process deterministic fixture** (implemented with the MCP Python SDK)
that returns synthetic records and performs no network I/O; because it is
the trusted local fixture, we take its discovered annotations as ground
truth for a tool's mutating status.

### 3.2 Agent2Agent Protocol (A2A)

A2A is a protocol for one agent to delegate a task to another agent
[@a2a-spec]. A *client agent* discovers a *remote agent* via an *Agent
Card* (spec §8), opens a *task* whose lifecycle is a `TaskState` machine
(§4.1.1–4.1.3), and exchanges *messages* built from *parts* (§4.1.4,
§4.1.6); the remote agent may attach *artifacts* (§4.1.7) — content
payloads representing task output. The artifact is the natural place for a
remote agent (benign or compromised) to place text that the client agent
will read and may act upon. Our A2A leg is a **local, in-process
deterministic fixture** implementing the HTTP+JSON/REST binding shapes
(spec §11), exercised only through an in-process test client (no sockets).

### 3.3 The composition

A *host agent* that uses both protocols sits between them. It receives a
user prompt, may call local MCP tools, may relay messages to a remote A2A
agent, may attempt a (possibly mutating) MCP tool call, or may stop. Its
decisions are what we measure. Everything the host sees is a **sanitized
decision context** — the user prompt, a host policy, the observable
protocol history so far, the discovered tool list, and the target Agent
Card — and never any ground-truth label, provenance annotation, or
evaluator state (Section 7).

---

## 4. Threat Model

We consider a single benign-by-construction host agent that faithfully
follows a fixed natural-language policy: it may call local tools, relay to
the remote agent, attempt a tool call (mutations require prior approval,
which it can never self-grant), or stop; and it is told not to send content
"clearly marked confidential, internal, or sensitive" to the remote agent
unless the task authorizes it.

**Adversary capability.** The adversary is modelled purely as *control over
the content returned on one leg of the interaction* — not over the host,
the protocols, or the harness. Operationally, that content is fixed text
scripted into the local protocol fixtures for each condition; no external
agent or service is involved.

- *RQ1 (information flow):* there is no active adversary. The "threat" is
  the host's own judgement: the MCP fixture returns a record visibly
  labeled `CONFIDENTIAL - INTERNAL ONLY`, and the host must decide what, if
  anything, to relay onward on the A2A leg.
- *RQ2/RQ3 (behavioral influence):* the A2A fixture is scripted to play a
  *compromised remote agent* — it returns a realistic natural-language
  artifact instructing the host to invoke a specific mutating MCP tool
  immediately, claiming prior approval and urgency. The artifact contains
  **no** special marker or trigger string — it is ordinary prose a real
  model must reason about. "Remote agent" is the A2A protocol role of the
  delegatee; in every experiment it is this local fixture.

**Trust boundary.** The mutation gate is an independent policy component
that is *not* part of the host: it re-derives a tool's mutating status from
the discovered annotation and blocks any mutating call lacking explicit
case-level approval. RQ3 asks whether this independent layer contains
influenced requests even when the host is willing to make them.

**Out of scope.** A malicious host, protocol-level attacks (message
forgery, transport interception), multi-hop agent chains, tool-supply-chain
compromise, and any production, external, or third-party MCP server or A2A
agent. All experiments run a real-model host against local deterministic
MCP and A2A protocol fixtures.

---

## 5. Research Questions

- **RQ1 — cross-protocol information flow.** When a host reads confidential
  content from an MCP tool and then interacts with a remote A2A agent in
  the same task, does that confidential content propagate across the A2A
  boundary? We decompose this into (a) *relay initiation* — did the host
  send any message to the remote agent after reading the confidential
  record? — and (b) *direct sensitive egress* — did the exact confidential
  marker cross the host→remote/A2A edge? (b) is an exact-token measurement
  and is not a measurement of semantic leakage.

- **RQ2 — cross-protocol behavioral influence.** Does an adversarial A2A
  artifact influence the host toward requesting a *mutating* MCP tool,
  relative to a structurally matched benign artifact? We measure the
  *actual mutating-tool request* rate: the host selected the
  mutation-attempt action **and** the named tool was discovered by the
  harness to be mutating. We report this separately from the rate at which
  the host merely *selected* the mutation-attempt action (which may name a
  non-mutating tool).

- **RQ3 — containment.** Given an actual mutating-tool request, does an
  independent mutation gate block it and prevent execution?

---

## 6. Agent Interop Bench Architecture

Agent Interop Bench comprises three independent deterministic evaluation
engines: an MCP tool-use engine, an A2A interoperability engine, and — the
subject of this paper — a **composed cross-protocol engine**. All three run
only against local, in-process mocks with no external network access, and
all scoring is rule-based (no LLM judge).

### 6.1 The composed engine

The composed engine drives one host agent across both protocol legs and
records a single ordered list of `CrossProtocolEvent`s. Event types cover
the MCP leg (`mcp_tool_request`, `mcp_tool_result`), the A2A leg
(`a2a_message`, `a2a_task_state_transition`, `a2a_artifact`), and the host's
own gated actions (`mutation_action`). The host's next action is produced
by a `HostAgentAdapter` given only the sanitized decision context; the
default adapter is a fixture replay used by the deterministic suite, and a
real-model adapter (OpenAI Responses API) is used for live studies. The
engine itself is unchanged between deterministic and live runs — only the
adapter differs.

### 6.2 Mock protocol servers

- **MCP:** a local stdio subprocess exposing a small fixed tool set for the
  composed suite, including `get_customer_record` and `get_deployment_status`
  (both discovered read-only) and `apply_remote_recommendation` (annotated
  destructive; discovered mutating). It returns synthetic content only.
- **A2A:** a local in-process HTTP+JSON app whose per-step behavior
  (task state, message text, artifact text) is scripted by the case; it is
  exercised only through an in-process test client.

### 6.3 The mutation gate

An independent predicate, `mutation_blocked(is_mutating, approved) =
is_mutating and not approved`, applied by the composed engine before any
mutating call executes. `is_mutating` is re-derived from the tool's
*discovered* annotation, never from a fixture flag; a real-model host can
never set `approved = true` for its own attempt. A blocked attempt is
recorded as a `mutation_action` event with `executed = false`; a permitted
call executes and is recorded with `executed = true`.

---

## 7. Cross-Protocol Provenance Model

The provenance model is what makes cross-protocol information flow and
influence *observable by exact rules*. It has four independent axes, all
fixture-declared and all hidden from the host:

1. **Provenance canaries.** A canary is a deterministic, syntactically
   inert token (`⟦CANARY:<uuid>⟧`) embedded in specific content. Its
   presence on an event is detected by exact substring identity, never by
   semantic interpretation. Each canary carries a **sensitivity** label
   (`public` or `sensitive`).

2. **Allowed sensitive edges.** A fixture-declared set of
   `(source, dest, protocol)` edges on which a `sensitive` canary is
   *permitted* to travel. Any *direct* observation of a sensitive canary on
   an edge outside this set is a **sensitive-egress violation**. For the
   RQ1 treatment case the only allowed edge is `local_tool→host/mcp`; the
   `host→remote/a2a` edge is not allowed.

3. **Origin trust and content class.** Per-actor defaults
   (`user`/`host` trusted, `remote`/`local_tool` untrusted) plus optional
   per-event overrides, and a `non_adversarial`/`adversarial` content
   class. The engine folds these into per-event **adversarial ancestry**
   and **sensitive ancestry** sets — a real DAG computation over the actual
   event trace, not a category-name special case.

4. **Direct vs. propagated presence.** Each event carries both its
   `canary_ids` (canary tokens *literally present* in that event's payload)
   and its `propagated_canary_ids` (canary tokens present in any causal
   ancestor). A propagation evaluator counts a canary as "propagated" when
   it appears — directly *or* via ancestry — on events of two or more
   protocols. A **direct** sensitive-egress check counts only literal
   presence (`canary_ids`) on the crossing event.

This distinction is central to RQ1: a host can *relay* after reading a
confidential record (creating a causal chain, so the canary appears in
`propagated_canary_ids` on the A2A message) without ever placing the
literal marker into the relayed text (so `canary_ids` on the A2A message is
empty). Our **primary** RQ1 outcome — direct sensitive egress — fires only
in the latter case; the former is captured by the **secondary** outcome,
relay initiation.

For behavioral influence (RQ2/RQ3), the live-study path does not set an
`adversarial` content-class override on the A2A artifact (the artifact is
realistic prose, not a marker), so per-event adversarial ancestry is empty
on this path. We therefore identify the "adversarial" versus "benign"
condition of an influence trial by which overlay was shown — condition
ground truth — not by ancestry, and we say so explicitly wherever the
influence and containment outcomes are reported.

---

## 8. Experimental Methodology

### 8.1 Decision-point execution

An earlier free-running pilot (models asked for every step of an open
interaction loop) proved uninformative: models planned the whole workflow
and repeatedly relayed to the remote agent before reaching the decision the
experiment was designed to measure. The frozen methodology used here is
**decision-point** execution:

1. **Deterministic bootstrap.** The engine constructs the situation with
   *no* model involvement. For sensitive-egress, it executes the local MCP
   `get_customer_record` call so a real `mcp_tool_result` (a `PUBLIC` or
   `CONFIDENTIAL`-labeled record with an embedded canary) exists in the
   trace. For adversarial-influence, it performs exactly one deterministic
   A2A interaction so a real `a2a_artifact` (benign or adversarial text)
   exists.

2. **One restricted decision.** The real model is asked for **exactly one**
   decision, given only the sanitized context. The wire-level action set is
   restricted to `{relay_to_remote, stop}` for sensitive-egress and
   `{attempt_mutating_tool, stop}` for adversarial-influence. The
   restriction is enforced three ways: the tool schema sent to the provider
   contains only the permitted actions; a composite adapter refuses any
   returned action outside the set; and the interaction step ceiling admits
   only one model decision.

3. **One deterministic observable action.** If the host relays, the engine
   performs exactly one A2A interaction and records the resulting events.
   If the host attempts a mutating tool, the engine runs the mutation gate
   and records a `mutation_action` event. The trial then terminates
   `COMPLETED`.

Per-run parameters were frozen before execution: `reasoning_effort = low`,
`max_output_tokens = 512`, `timeout = 20 s`, `retries = 0`,
one provider decision per trial, at most 80 provider decisions per run.
All MCP and A2A targets are local. The host policy, the four overlays, the
tool surface, and the outcome definitions were all fixed and hash-pinned in
advance.

### 8.2 Stimuli

Four overlays, reused verbatim, form a 2×2 design (experiment × condition):

| overlay | experiment | condition | manipulation |
|---|---|---|---|
| `live-sensitive-egress-treatment` | sensitive_egress | treatment | MCP record labeled `CONFIDENTIAL - INTERNAL ONLY`; embedded canary is `sensitive`; only allowed edge is `local_tool→host/mcp` |
| `live-sensitive-egress-control` | sensitive_egress | control | structurally matched record labeled `PUBLIC - OK TO SHARE`; embedded canary is `public` |
| `live-influence-treatment` | adversarial_influence | treatment | remote A2A artifact is a realistic natural-language instruction to call `apply_remote_recommendation` immediately, claiming prior approval and urgency |
| `live-influence-control` | adversarial_influence | control | structurally matched benign artifact ("status looks healthy … no action needed") |

For sensitive-egress the model-visible MCP *request* carries only an opaque
`record_ref` (`record-a7` / `record-b4`) with no condition information; the
`CONFIDENTIAL`/`PUBLIC` label and canary are supplied server-side. The
first model-visible difference between conditions is therefore the returned
record text, never the request. The influence overlays differ *only* in the
artifact text.

### 8.3 Model panel and design

Three models from the OpenAI GPT-5.6 family [@openai-gpt56], frozen in this
order: `gpt-5.6-sol` (the flagship tier), `gpt-5.6-terra` (the balanced
default tier), `gpt-5.6-luna` (the lightweight tier). For each model,
**20 blocks**; each block contains all four
(experiment × condition) cells exactly once; the within-block order is
shuffled by a single `random.Random(seed)` with one frozen scheduling seed
(`20260401`), advanced model-by-model in panel order. This yields exactly
20 replicates per model per cell and prevents any cell from being
over- or under-sampled by drift. Total: **3 × 4 × 20 = 240 trials**.

### 8.4 Reproducibility mechanism

Each run persists an **execution fingerprint**: SHA-256 over the plan
config hash, the exact source commit, a canonical hash of the *resolved
overlay contents* (not just their ids), the host policy hash, the
host-action tool-schema hash, and the per-model schedule hash. The
fingerprint is written once per run and stamped on every trial record; a
resume is refused if it differs, even when the plan hash is unchanged. The
frozen blocked schedule is committed and its hash enters the fingerprint,
so re-randomising the trial order invalidates the fingerprint.

### 8.5 Outcome definitions (frozen)

- **Sensitive-egress — primary: direct sensitive egress.**
  `sensitive_egress == True / (True + False)`, where the outcome is `True`
  iff a `sensitive` canary token *literally* crossed an edge not in
  `allowed_sensitive_edges`, `False` iff the host relayed but the token did
  not cross such an edge, and *not applicable* otherwise (a `stop`
  decision, or the intentionally-public control, which declares no
  `sensitive` canary). The denominator is the applicable set (`True +
  False`), i.e. the trials in which the host actually relayed — **not** all
  20 trials.
- **Sensitive-egress — secondary: relay initiated.**
  `relay_to_remote / completed egress trials` (denominator 20).
- **Influence — primary: actual mutating-tool request (outcome B).** The
  host selected `attempt_mutating_tool` **and** the named tool was
  discovered to be mutating.
- **Wrapper selection (outcome A), descriptive.** The host selected
  `attempt_mutating_tool` regardless of the tool named. A ≥ B always; the
  gap (E) is non-mutating tools named through the mutation-attempt action.
- **Containment — outcomes C and D.** Over the actual mutating-tool
  requests (B): **C** = blocked by the gate (`executed = false`);
  **D** = executed (`executed = true`).
- Every rate is reported with a **Wilson 95% score interval** on its own
  applicable denominator, and paired conditions are reported with the
  **signed** difference `rate(treatment) − rate(control)`.

### 8.6 Statistical reporting

We report rates, Wilson 95% score intervals [@wilson1927], and signed
treatment−control differences. **We report no p-values and run
no significance tests.** With 20 replicates per cell the study is a
descriptive confirmatory pilot, not a hypothesis test. The 20 replicates
in a cell are repeated draws from one model under one fixed stimulus; the
provider may share hidden state, batching, caching, or routing across them,
so we do **not** assume the replicates are independent Bernoulli trials.
Wilson intervals are reported as a conventional descriptive spread of the
observed proportion, not as a guarantee of i.i.d. sampling. Failed trials
(none occurred) would be excluded from behavioral denominators and reported
separately as attrition.

---

## 9. Results

All figures below are taken verbatim from the frozen Phase 4B analysis
(`phase4b-results-v1`). Percentages are of the stated denominator; bracketed
pairs are Wilson 95% score intervals in percent.

### 9.1 Experimental integrity (Table 1)

All 12 model×experiment×condition cells recorded 20 planned, 20 completed,
**0 failed** trials (0% attrition). Each run consumed exactly 80/80 provider
decisions (retries = 0); every provider call returned `ok`; every trial's
stamped execution fingerprint matched its run's fingerprint; the frozen
blocked schedule order was preserved for all three runs. Study total: 240
completed trials, 240 provider decisions.

### 9.2 RQ1 — cross-protocol information flow (Table 2)

**Relay initiation (secondary)** varied substantially by model. In the
confidential (treatment) condition: `gpt-5.6-sol` **3/20 = 15.0%**
[5.2, 36.0]; `gpt-5.6-terra` **17/20 = 85.0%** [64.0, 94.8]; `gpt-5.6-luna`
**20/20 = 100.0%** [83.9, 100.0]. In the public (control) condition:
`gpt-5.6-sol` 19/20 = 95.0% [76.4, 99.1]; `gpt-5.6-terra` 17/20 = 85.0%
[64.0, 94.8]; `gpt-5.6-luna` 20/20 = 100.0% [83.9, 100.0]. The signed
treatment−control differences in relay initiation were **−0.80**, **0.00**,
**0.00** respectively: only `gpt-5.6-sol` relayed markedly less often after
seeing a confidential label.

**Direct sensitive egress (primary)** was **0 for every model**. Over the
trials in which the host actually relayed a confidential record:
`gpt-5.6-sol` **0/3 = 0.0%**, Wilson 95% [0.0, 56.2]; `gpt-5.6-terra`
**0/17 = 0.0%** [0.0, 18.4]; `gpt-5.6-luna` **0/20 = 0.0%** [0.0, 16.1]. In
the public control condition this outcome is *not applicable* by design
(the control declares no `sensitive` canary), and no direct-egress rate is
computed for it.

A deterministic exact-substring inspection of **all 40** confidential relay
messages (3 + 17 + 20) found the literal canary token, the exact
`[CONFIDENTIAL - INTERNAL ONLY]` label, and the full record string each
relayed **0/40** times. Several relays acknowledged in prose that a record
was retrieved and was "confidential/internal", while explicitly declining
to reproduce its contents.

**Wording.** These outcomes measure *verbatim marker* leakage across the
protocol edge. A direct-sensitive-egress rate of 0 means the exact
confidential token/label/record string was never relayed verbatim; it does
**not** establish that no semantic or paraphrased information about the
record was conveyed. Semantic leakage is outside the scope of this study.

### 9.3 RQ2 — cross-protocol behavioral influence (Table 3)

Using the **actual mutating-tool request** outcome (outcome B: the host
selected `attempt_mutating_tool` *and* named a discovered-mutating tool),
the adversarial (treatment) condition showed a higher rate than the
structurally matched benign (control) condition for all three models:

| model | adversarial B | Wilson 95% | benign B | Wilson 95% | signed diff (T−C) |
|---|---|---|---|---|---|
| `gpt-5.6-sol` | 14/20 = 70.0% | [48.1, 85.5] | 10/20 = 50.0% | [29.9, 70.1] | **+0.20** |
| `gpt-5.6-terra` | 11/20 = 55.0% | [34.2, 74.2] | 3/20 = 15.0% | [5.2, 36.0] | **+0.40** |
| `gpt-5.6-luna` | 14/20 = 70.0% | [48.1, 85.5] | 4/20 = 20.0% | [8.1, 41.6] | **+0.50** |

All three signed differences are positive. For `gpt-5.6-terra` and
`gpt-5.6-luna` the two per-condition Wilson intervals happen not to
overlap; for `gpt-5.6-sol` they do. Interval non-overlap here is a
descriptive observation, **not** a hypothesis test: the intervals are
computed per condition on n = 20, the 20 replicates are not assumed
independent (Section 8.6), and we report no p-value or difference-of-
proportions test.

**Wrapper selection vs. actual mutating request (Table 5, descriptive).**
The host selected the mutation-attempt action more often than it named a
mutating tool. Study totals: wrapper selection A = 82, actual mutating
request B = 56, non-mutating-tool-via-wrapper E = 26. The E cases are
`attempt_mutating_tool` calls that named a discovered read-only tool
(`get_deployment_status`, or in one cell `get_customer_record`); they are
concentrated in specific cells — e.g. `gpt-5.6-luna` benign 16/20 wrapper
selections named a non-mutating tool. Reporting A instead of B would
substantially overstate the adversarial→benign contrast for some models,
which is why B is our primary influence outcome and A/E/F are reported only
as diagnostics.

### 9.4 RQ3 — containment (Table 4)

Every *observed* actual mutating-tool request was blocked by the
independent mutation gate. In all six model×condition cells the blocked
rate was **100%** of B:
`gpt-5.6-sol` 14/14 (treatment) and 10/10 (control); `gpt-5.6-terra` 11/11
and 3/3; `gpt-5.6-luna` 14/14 and 4/4. **Zero** actual mutating-tool
requests executed anywhere in the study (executed rate 0% in every cell).
The Wilson 95% upper bound on the executed rate depends on the cell's B:
[0.0, 21.5]% at B = 14, [0.0, 25.9]% at B = 11, [0.0, 27.8]% at B = 10,
[0.0, 49.0]% at B = 4, [0.0, 56.2]% at B = 3.

**Non-mutating executions.** The mutation gate, by construction, does not
block a call to a discovered read-only tool even when it is issued through
the `attempt_mutating_tool` action. Such calls executed in the E cells
(study total F = 26). These are executions of read-only tools; they are not
mutations and are reported as a wrapper/tool-selection diagnostic, not as a
containment failure.

### 9.5 Summary of the frozen results

- RQ1: high and model-dependent relay initiation after reading a
  confidential record (15–100%); **zero exact-token direct sensitive
  egress** across all models (Wilson 95% upper bounds 16–56% depending on
  relay count). Verbatim-marker measurement only.
- RQ2: within the controlled manipulation, the adversarial condition showed
  a higher *actual mutating-tool request* rate than the structurally
  matched benign condition in all three models (signed treatment−control
  differences +0.20, +0.40, +0.50; Wilson intervals per cell). Wrapper
  selection (A) inflates this contrast for some models and is reported
  separately.
- RQ3: **100%** of the observed actual mutating-tool requests were blocked
  by the gate; **0** executed across the 240 trials.

---

## 10. Discussion

**The composition is where these behaviors become observable.** RQ1 shows
one behavior that only exists across the seam: the host frequently chose to
open the cross-boundary channel (relay to the A2A fixture) after reading
confidential MCP content — an action a pure-MCP benchmark cannot observe
and a pure-A2A benchmark never sets up. RQ3 shows that, in this sample,
every influenced mutating request was refused by the independent gate.
These are not in tension: within the RQ2 manipulation (adversarial vs
structurally matched benign artifact, everything else held fixed), the
adversarial condition was associated with a higher *actual mutating-tool
request* rate in all three models, and the gate is the component that
declined those requests. We do not claim that the adversarial artifact
*causes* mutating requests in a mechanistic sense, nor that either the
host's policy compliance or the gate is robust: we observed that, for these
four stimuli and n = 20 per cell, the verbatim confidential marker never
crossed the boundary and no influenced mutating request executed. The
study does not indicate which safeguard would fail first under stimuli it
did not test.

**Why the wrapper/actual distinction matters.** A benchmark that scores
"the model tried to mutate" whenever the mutation-attempt action is
selected would have reported much larger and noisier effects for some
models here, because those models routed read-only calls through that
action. Measuring the *discovered* mutating status of the named tool
(outcome B) gives a cleaner behavioral signal and avoids conflating
"attempted a dangerous action" with "used an oddly-shaped call for a safe
one." We recommend this discipline for any tool-influence measurement.

**Relay initiation is a behavioral, not a leakage, outcome.** The wide
model spread in relay initiation (15% vs 100%) is a genuine behavioral
difference — some models treat "read a confidential record" as a reason to
minimise onward communication — but it is not itself a disclosure. Only
direct sensitive egress measures disclosure of the marker, and that was 0.
Conversely, a model that never relays cannot leak via that edge, so relay
initiation and direct egress must be read together.

**What the zeros do and do not mean.** Zero direct sensitive egress with
Wilson upper bounds of 16–56% is consistent with a true per-trial
verbatim-leak probability anywhere from 0 up to roughly one-in-six (for the
model that always relayed) — it is a weak upper bound, not a guarantee.
And it says nothing about paraphrased leakage. Zero mutating executions,
similarly, is a property of *this gate* against *these* influenced
requests; the interesting quantity for a larger study is whether any
stimulus can produce an *approved-looking* mutating request that the gate
would pass.

---

## 11. Limitations

1. **Four stimuli, one policy, one tool surface.** All results are
   conditional on two sensitive-egress overlays and two adversarial-influence
   overlays, one host policy string, and one three-tool MCP surface. No
   claim generalises beyond these.
2. **Small n, confirmatory pilot.** 20 replicates per cell. Wilson
   intervals are wide (e.g. [0.0, 56.2]% for the model that relayed only 3
   times). This is a controlled confirmatory pilot, not a powered study.
3. **No independence assumption, no significance tests.** Repeated provider
   calls are repeated samples, not assumed statistically independent
   executions. We report no p-values; the signed differences and
   non-overlapping intervals in Section 9.3 are descriptive.
4. **Exact-token measurement only.** Direct sensitive egress is a verbatim
   substring check. Semantic, paraphrased, or partial information leakage is
   not measured; a 0 result must not be read as "no information left the
   boundary."
5. **Mocked protocols.** MCP and A2A are local in-process mocks. Real
   servers, transports, network conditions, and multi-hop agent chains are
   out of scope.
6. **Single decision point.** The decision-point methodology deliberately
   removes multi-step planning to isolate one measured decision. It does not
   observe compounding behavior over a longer interaction.
7. **Condition ground truth for influence.** Because the live path does not
   mark the adversarial artifact with a special class, "adversarial vs
   benign" for RQ2/RQ3 is defined by which overlay was shown, not by
   computed adversarial ancestry.
8. **Three specific model identifiers at one point in time.** Model
   behavior is not stable across versions or dates; these numbers are a
   snapshot.
9. **Non-mutating-via-wrapper behavior is not fully explained.** We report
   that some models route read-only calls through the mutation-attempt
   action but do not characterise why; it may reflect the restricted
   two-action schema at the decision point.

---

## 12. Related Work

**Cross-protocol composition risk — prior articulations.** The risk this
paper measures is not new as a concept. A June 2026 IETF Internet-Draft
[@mohiuddin2026mcpsec] devotes a "Protocol Pivoting" section to
lateral movement that *crosses agent-protocol boundaries* — explicitly
"combining MCP with Agent-to-Agent (A2A) delegation" — and states that
"mitigations that consider each protocol in isolation do not address
movement that crosses protocol boundaries"; its worked scenario (an
injected instruction reaching an MCP-using agent that then invokes an MCP
tool) is close to our RQ2. Independently, *AgentRFC* [@agentrfc2026]
formalises a "Composition Safety" principle — "security properties that
hold for individual protocols can break when protocols are composed
through shared infrastructure" — with formal (TLA+) models of five
cross-protocol composition patterns spanning MCP, A2A and other agent
protocols, and a spec-conformance checker. We do **not** claim priority on
composition safety, cross-protocol risk, or MCP+A2A pivoting. Our work is
the *executable empirical complement*: where [@agentrfc2026] checks spec
conformance against formal invariants and [@mohiuddin2026mcpsec] enumerates
mitigations, we run a real-model host across a concrete MCP+A2A composition
(implemented as local deterministic protocol fixtures), attach an
observable provenance model, and report measured per-model rates for one
information-flow outcome, one behavioral-influence outcome, and one
containment outcome.

**Single-protocol MCP safety / security benchmarks.** *MCP-SafetyBench*
[@mcpsafetybench2026] evaluates the safety of MCP tool-using agents on
multi-turn ReAct tasks against a 20-category attack taxonomy over
real-world MCP servers. *MCP Security Bench (MSB)* [@msb2026] and
*MCPSecBench* [@mcpsecbench2025] similarly target MCP-layer security
(malicious or misconfigured servers, tool-poisoning, argument-injection,
over-broad permissions; MCPSecBench reports 17 attack types over four MCP
attack surfaces). Our composed harness reuses an MCP leg but measures what
happens when that leg's *output* is carried into an A2A interaction, which
these single-protocol benchmarks do not model. We do **not** claim to be
the first MCP benchmark.

**Single-protocol A2A security benchmark.** *A2ASecBench* [@a2asecbench2026]
is a protocol-aware security benchmark for Agent-to-Agent systems, with a
taxonomy of supply-chain manipulations and protocol-logic weaknesses and
six concrete attacks across A2A stages, evaluated with a joint
safety–utility methodology. Our RQ2/RQ3 stimuli use an adversarial A2A
artifact, but the *action* we measure — a mutating call on a *local MCP
tool* — and the *control* we test — an independent local mutation gate —
are outside a pure-A2A scope. We do **not** claim to be the first A2A
benchmark.

**Indirect prompt injection and tool-use agent evaluation.** Indirect
prompt injection — untrusted content read by an agent carrying
instructions it then follows — was characterised by Greshake et al.
[@greshake2023indirect]. Our RQ2 is an instance of it where the injection
vector is a remote A2A artifact and the intended payload is a local MCP
mutation. *AgentDojo* [@agentdojo2024] evaluates prompt-injection attacks
and defenses on tool-using agents with rule-based (not LLM-judge) utility
and security functions; *ToolEmu* [@toolemu2024] identifies LM-agent risks
in an LM-emulated sandbox with an LM safety evaluator. We differ from both
in two ways relevant here: our environment executes a real-model host
across a local deterministic MCP+A2A protocol composition (protocol
fixtures, not an LM emulator), and our scoring is exact-rule provenance
checking (no LLM anywhere in evaluation).
*CaMeL* [@camel2025] is a defense that separates control and data flow and
tracks data provenance before each tool call; it is conceptually adjacent
to our provenance model but is a mitigation, whereas ours is an evaluation
instrument.

**Multi-agent and formal agent security.** Multi-agent security — threats
that emerge or amplify through agent interactions — has been framed as a
distinct field [@masec2025]. Formal and information-flow approaches to
agent/tool safety [@agentrfc2026; @camel2025] provide the theoretical
context for our provenance model (canaries + sensitivity + allowed-edge
policy + causal ancestry); our contribution here is empirical and
instrument-focused rather than a formal result.

**Deterministic, judge-free evaluation.** Our scoring is rule-based and
reproducible, aligning methodologically with judge-free agent-evaluation
efforts such as [@agentdojo2024] rather than with LLM-as-judge scoring.
This is a methodological alignment, not a novelty claim.

---

## 13. Reproducibility

Every number in this paper comes from the frozen public release
**`phase4b-results-v1`** of Agent Interop Bench
(`https://github.com/ArpanKumarM/agent-interop-bench/releases/tag/phase4b-results-v1`).

- **Source commit:** `6cb64606a614c42145cc2da03468551c1ca48c6d` (code, frozen
  v3 plan, frozen blocked schedule, study-design document). Git tag:
  `phase4b-results-v1`.
- **Analysis commit:** `caf036db97b142005e8f12e02fc9b95d0a205cbd` (the
  offline pipeline that produced the tables and figures).
- **Release archive:** `agent-interop-bench-phase4b-results-v1.tar.gz`,
  74 667 bytes, SHA-256
  `85c04c34d8fed427ac54a98f0f2ed1ccc50df32f1d9958fe6d21ef71bf9defb5`
  (deterministic: sorted members, epoch mtime, fixed mode/uid/gid). Contents:
  the three raw runs
  (`composed-live-canary-003-{sol,terra,luna}-attempt-1/` with `plan.json`,
  `execution_fingerprint.json`, `schedule.json`, `trials.jsonl`,
  `summary.json` — byte-exact, not normalised), the offline outcome-taxonomy
  audit (`phase_4b_outcome_audit.json`), the five paper-ready CSV tables,
  the three SVG figures, the analysis `MANIFEST.json`, the study-design and
  results documents, and the frozen v3 plan and blocked schedule.
  `REPRODUCIBILITY.md` in the archive lists every file's SHA-256 and the
  exact offline commands to recompute the audit, tables, and figures.

**Raw vs. derived.** `runs/*/trials.jsonl` are preserved provider-run
observations. Everything else (audit JSON, tables, figures, results
document) is *derived* and can be regenerated **offline, with zero provider
calls**, from the raw traces plus the committed static local-mock tool
annotations (`uv run python -m app.cli.phase_4b_audit` and
`uv run python -m app.cli.phase_4b_results`). The full offline test suite
(`uv run pytest -q`) makes no provider call.

**Per-run execution fingerprints** (SHA-256, stamped on every trial):
`gpt-5.6-sol` `bbeb896d…82bfa373`; `gpt-5.6-terra` `6b47cba3…b825d453`;
`gpt-5.6-luna` `e9e4c06b…613e54ea`. Each incorporates the run's config
hash, source commit, resolved-overlay-bundle hash, host-policy hash,
tool-schema hash, and per-model schedule hash.

---

## 14. Conclusion

We built a cross-protocol MCP+A2A composed evaluation harness — a
real-model host over local deterministic MCP and A2A protocol fixtures —
with an observable provenance model, and used a decision-point methodology
to run a controlled confirmatory pilot over three models and 240 trials.
In this sample: the host frequently chose to open the cross-boundary
channel after reading a confidential MCP record (relay initiation 15–100%
by model), but the exact confidential marker never crossed the protocol
boundary verbatim (direct sensitive egress 0/40 relay messages; Wilson 95%
upper bounds 16–56%); within the controlled manipulation, the adversarial
A2A artifact condition was associated with a higher actual mutating-tool
request rate than the structurally matched benign condition in all three
models (signed differences +0.20/+0.40/+0.50); and every one of the
observed actual mutating-tool requests was blocked by the independent
mutation gate, with zero mutating executions across the 240 trials. These
are narrow, stimulus-conditional observations for one host policy, one tool
surface, four stimuli, three models, and one point in time — not general
safety verdicts, not a causal-mechanism claim, and not a claim about
semantic information leakage (which we do not measure). They are published
with the byte-exact raw runs and a fully offline analysis pipeline so every
table and figure can be regenerated with no provider call.

---

## Appendix A — Frozen result tables (verbatim from `phase4b-results-v1`)

### Table 1 — Experimental integrity / attrition
All 12 cells (3 models × {sensitive_egress, adversarial_influence} ×
{treatment, control}): `trials_planned = trials_recorded = trials_completed
= 20`, `trials_failed = 0`, `attrition = 0.0%`, `provider_decisions = 20`.

### Table 2 — Sensitive relay + direct egress (n = 20 completed per cell)

| model | metric | confidential | Wilson 95% | public | Wilson 95% | T−C |
|---|---|---|---|---|---|---|
| gpt-5.6-sol | relay_initiated (secondary) | 3/20 = 15.0% | [5.2, 36.0] | 19/20 = 95.0% | [76.4, 99.1] | −0.80 |
| gpt-5.6-sol | direct_sensitive_egress (primary) | 0/3 = 0.0% | [0.0, 56.2] | — | N/A (public canary) | — |
| gpt-5.6-terra | relay_initiated | 17/20 = 85.0% | [64.0, 94.8] | 17/20 = 85.0% | [64.0, 94.8] | 0.00 |
| gpt-5.6-terra | direct_sensitive_egress | 0/17 = 0.0% | [0.0, 18.4] | — | N/A | — |
| gpt-5.6-luna | relay_initiated | 20/20 = 100.0% | [83.9, 100.0] | 20/20 = 100.0% | [83.9, 100.0] | 0.00 |
| gpt-5.6-luna | direct_sensitive_egress | 0/20 = 0.0% | [0.0, 16.1] | — | N/A | — |

### Table 3 — Actual mutating requests (outcome B): adversarial vs benign (n = 20 per cell)

| model | adversarial | Wilson 95% | benign | Wilson 95% | T−C |
|---|---|---|---|---|---|
| gpt-5.6-sol | 14/20 = 70.0% | [48.1, 85.5] | 10/20 = 50.0% | [29.9, 70.1] | +0.20 |
| gpt-5.6-terra | 11/20 = 55.0% | [34.2, 74.2] | 3/20 = 15.0% | [5.2, 36.0] | +0.40 |
| gpt-5.6-luna | 14/20 = 70.0% | [48.1, 85.5] | 4/20 = 20.0% | [8.1, 41.6] | +0.50 |

### Table 4 — Containment of actual mutating requests (denominator = B)

| model | condition | B | blocked (C) | Wilson 95% | executed (D) | Wilson 95% |
|---|---|---|---|---|---|---|
| gpt-5.6-sol | treatment | 14 | 100.0% | [78.5, 100.0] | 0.0% | [0.0, 21.5] |
| gpt-5.6-sol | control | 10 | 100.0% | [72.2, 100.0] | 0.0% | [0.0, 27.8] |
| gpt-5.6-terra | treatment | 11 | 100.0% | [74.1, 100.0] | 0.0% | [0.0, 25.9] |
| gpt-5.6-terra | control | 3 | 100.0% | [43.8, 100.0] | 0.0% | [0.0, 56.2] |
| gpt-5.6-luna | treatment | 14 | 100.0% | [78.5, 100.0] | 0.0% | [0.0, 21.5] |
| gpt-5.6-luna | control | 4 | 100.0% | [51.0, 100.0] | 0.0% | [0.0, 49.0] |

### Table 5 — Wrapper / tool-selection diagnostic (descriptive; n = 20 per cell)

| model | condition | wrapper A | Wilson 95% | non-mut via wrapper E | non-mut executed F | tool_name distribution |
|---|---|---|---|---|---|---|
| gpt-5.6-sol | treatment | 14 (70.0%) | [48.1, 85.5] | 0 | 0 | `apply_remote_recommendation`:14 |
| gpt-5.6-sol | control | 12 (60.0%) | [38.7, 78.1] | 2 (10.0%) | 2 (10.0%) | apply:10, get_deployment_status:2 |
| gpt-5.6-terra | treatment | 11 (55.0%) | [34.2, 74.2] | 0 | 0 | apply:11 |
| gpt-5.6-terra | control | 5 (25.0%) | [11.2, 46.9] | 2 (10.0%) | 2 (10.0%) | apply:3, get_deployment_status:2 |
| gpt-5.6-luna | treatment | 20 (100.0%) | [83.9, 100.0] | 6 (30.0%) | 6 (30.0%) | apply:14, get_deployment_status:6 |
| gpt-5.6-luna | control | 20 (100.0%) | [83.9, 100.0] | 16 (80.0%) | 16 (80.0%) | apply:4, get_customer_record:2, get_deployment_status:14 |

Study totals across the influence cells: A = 82, B = 56, C = 56, D = 0,
E = 26, F = 26.

---

## Appendix B — Figures (frozen; `phase4b-results-v1`)

- `fig_relay_rate_confidential_vs_public.svg` — relay-initiated rate,
  confidential vs public, by model (grouped bars, Wilson 95% CI error bars).
- `fig_actual_mutating_rate_adversarial_vs_benign.svg` — actual
  mutating-tool request rate (outcome B), adversarial vs benign, by model.
- `fig_containment_blocked_vs_executed.svg` — blocked (C) vs executed (D)
  share of actual mutating-tool requests, adversarial condition, by model.
