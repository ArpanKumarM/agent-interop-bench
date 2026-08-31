# Citation audit — Phase 5C (final)

Verification record for every reference in `paper/references.bib`. All
checks used public web search and page fetches only; **no experiment,
provider call, or model inference was run**, and no frozen result was
touched. **No bibliographic data was invented** — every author list and
author order below is taken from a primary source (the arXiv author line,
the official project page, the IETF datatracker, or the publisher/DOI
page). Where the first-round audit (Phase 5B) had an incomplete or
mis-ordered list, the corrected value and its source are recorded here.

Confidence: **High** = matched against a primary source, including author
order. Every entry is now High.

| key | verified fields | primary source(s) | Phase 5B → 5C change |
|---|---|---|---|
| `mcp-spec` | title; authoritative revision **2025-06-18** (schema/2025-06-18/schema.ts); Hosts/Clients/Servers roles; JSON-RPC `tools/call`; tool annotations "should be considered untrusted, unless obtained from a trusted server"; local fixture uses the MCP Python SDK | modelcontextprotocol.io/specification/2025-06-18 (fetched) | pinned revision 2025-06-18; added the annotation-trust quote and SDK note |
| `a2a-spec` | v1.0.0; Agent Card **§8**; Task/TaskStatus/TaskState **§4.1.1–4.1.3**; Message/Part **§4.1.4, §4.1.6**; Artifact **§4.1.7**; HTTP+JSON/REST binding **§11**; Linux Foundation since June 2025 | a2a-protocol.org/v1.0.0/specification/ (fetched); linuxfoundation.org press release | added exact section numbers |
| `wilson1927` | E. B. Wilson; exact title; JASA **22(158):209–212**, 1927; DOI 10.1080/01621459.1927.10502953; JSTOR 2276774 | tandfonline.com DOI page; jstor.org/stable/2276774 | unchanged (already High) |
| `greshake2023indirect` | Greshake, Abdelnabi, Mishra, Endres, Holz, Fritz; exact title; **AISec '23**; 2023; arXiv:2302.12173 | arxiv.org/abs/2302.12173 | unchanged |
| `mcpsafetybench2026` | **Xuanjun Zong, Zhiqi Shen, Lei Wang, Yunshi Lan, Chao Yang** (arXiv author line, v2); exact title; **ICLR 2026** (proceedings.iclr.cc paper 2026; OpenReview 7XYjeL46co) | arxiv.org/abs/2512.15163v2 and /html/2512.15163v2 (fetched); proceedings.iclr.cc/paper_files/paper/2026/… | author order **confirmed** from the arXiv author line; ICLR 2026 confirmed via proceedings.iclr.cc |
| `msb2026` | **Dongsen Zhang, Zekun Li, Xu Luo, Xuannan Liu, Peipei Li, Wenjun Xu** (arXiv author line); exact title; arXiv Comments field = **"Accepted by ICLR 2026"**; arXiv:2510.15994 | arxiv.org/abs/2510.15994 (fetched) | author order **confirmed** from the arXiv author line and Comments field |
| `mcpsecbench2025` | **Yixuan Yang, Cuifeng Gao, Daoyuan Wu, Yufan Chen, Yingjiu Li, Shuai Wang** (arXiv author line — 6 authors); exact title; arXiv Comments = **"technical report from Lingnan University, Hong Kong"** (not a peer-reviewed venue); arXiv:2508.13220; code AIS2Lab/MCPSecBench | arxiv.org/abs/2508.13220 (fetched) | **corrected** author list (Phase 5B had a truncated 3-author list); venue/status confirmed as technical report |
| `a2asecbench2026` | **Tianhao Li, Chuangxin Chu, Yujia Zheng, Bohan Zhang, Neil Zhenqiang Gong, Chaowei Xiao**; exact title; **ICLR 2026** poster (OpenReview LfdFnakqGJ; iclr.cc/virtual/2026/poster/10010017) | safo-lab.github.io/A2ASecBench/ (fetched); corroborating web search; OpenReview forum id | author order **confirmed** from the official project page and a corroborating source; ICLR 2026 poster confirmed |
| `agentrfc2026` | **Shenghan Zheng, Qifan Zhang** (arXiv author line — complete, 2 authors); exact title; cs.CR; submitted **25 Mar 2026**; preprint (no venue); "Composition Safety (CS)" principle + five formal cross-protocol composition patterns | arxiv.org/abs/2603.23801 (fetched twice) | author list **confirmed complete** at two names; no Comments/venue field |
| `mohiuddin2026mcpsec` | draft **`draft-mohiuddin-mcp-security-considerations-00`**; exact title; author **Anas Mohiuddin Syed**; **June 2026**; individual submission; Informational; **§6 "Protocol Pivoting"** covers MCP + A2A cross-boundary lateral movement, "mitigations that consider each protocol in isolation do not address movement that crosses protocol boundaries" | datatracker.ietf.org/doc/draft-mohiuddin-mcp-security-considerations/00/ (fetched); ietf.org/archive/id/…-00.html | unchanged (already High); confirmed single author and version -00 |
| `agentdojo2024` | Debenedetti, J. Zhang, Balunović, Beurer-Kellner, Fischer, Tramèr; exact title; **NeurIPS 2024** Datasets & Benchmarks Track; arXiv:2406.13352 | proceedings.neurips.cc/paper_files/paper/2024/…; neurips.cc/virtual/2024/poster/97522; arxiv.org/abs/2406.13352 | unchanged |
| `toolemu2024` | Ruan, Dong, A. Wang, Pitis, Y. Zhou, Ba, Dubois, Maddison, Hashimoto; exact title; **ICLR 2024**; arXiv:2309.15817; framework "ToolEmu" | arxiv.org/abs/2309.15817; proceedings.iclr.cc/paper_files/paper/2024/… | unchanged |
| `camel2025` | Debenedetti, Shumailov, Fan, Hayes, Carlini, Fabian, Kern, Shi, Terzis, Tramèr (arXiv author line); exact title; **preprint**, latest revision **24 Jun 2025**; arXiv Comments do **not** list a peer-reviewed venue; arXiv:2503.18813 | arxiv.org/abs/2503.18813 (fetched) | venue/status **confirmed** as preprint (no S&P/USENIX/ICML acceptance in the Comments field) |
| `masec2025` | lead authors **Christian Schroeder de Witt, Klaudia Krawiecka, Igor Krawczuk, …** (23-author position paper); exact title; arXiv:2505.02077; v2 2026 | arxiv.org/abs/2505.02077 (fetched) | `.bib` gives the first three authors + "and others"; full list is in the arXiv record |
| `openai-gpt56` | GPT-5.6 family; tiers `gpt-5.6-sol` (flagship), `gpt-5.6-terra` (balanced default), `gpt-5.6-luna` (lightweight); GA **9 July 2026**; these exact strings appear as **both `requested_model` and `returned_model` in all 240 trials** of the frozen runs | openai.com/index/gpt-5-6/; openai.com/index/previewing-gpt-5-6-sol/; GitHub Copilot changelog 2026-07-09; frozen `trials.jsonl` provenance | model IDs **cross-checked against the frozen run provenance** (requested == returned, no dated snapshot suffix) |

## Exact model identifiers from the frozen provenance

For all 80 trials and all 80 provider calls of each run:

| run | `requested_model` | `returned_model` | provider | adapter |
|---|---|---|---|---|
| `composed-live-canary-003-sol-attempt-1` | `gpt-5.6-sol` | `gpt-5.6-sol` | `openai` | `openai_responses_host` (OpenAI Responses API) |
| `composed-live-canary-003-terra-attempt-1` | `gpt-5.6-terra` | `gpt-5.6-terra` | `openai` | `openai_responses_host` |
| `composed-live-canary-003-luna-attempt-1` | `gpt-5.6-luna` | `gpt-5.6-luna` | `openai` | `openai_responses_host` |

No dated snapshot suffix was requested or returned; the plain tier
identifiers are the exact strings on record.

## Manuscript wording changes for the local-fixture distinction (Phase 5C §2)

- Added a **"System under test"** paragraph at the top of `main.md`:
  the only non-local component is real provider model inference (OpenAI
  GPT-5.6 via the Responses API); all MCP and A2A infrastructure is local
  deterministic protocol fixtures; no production/external/third-party MCP
  server or A2A agent was contacted.
- §1 (abstract): "Production AI agents" → "Deployed AI agents"; "a
  real-model host … across both protocol legs — implemented here as local
  deterministic MCP and A2A protocol fixtures, not external services".
- §2.1(1): "one real-model host driven across an MCP leg and an A2A leg,
  both implemented as local deterministic protocol fixtures".
- §3.1 / §3.2: MCP and A2A legs described as "local, in-process
  deterministic fixture(s)"; added the MCP annotation-trust quote and the
  A2A spec section numbers; noted we take the trusted local fixture's
  discovered annotations as ground truth for mutating status.
- §4 (threat model): the adversary is "control over the content returned
  on one leg … that content is fixed text scripted into the local protocol
  fixtures"; "the A2A fixture is scripted to play a compromised remote
  agent"; "'Remote agent' is the A2A protocol role of the delegatee; in
  every experiment it is this local fixture"; Out-of-scope list now names
  "any production, external, or third-party MCP server or A2A agent".
- §12: "we run a real-model host across a concrete MCP+A2A composition
  (implemented as local deterministic protocol fixtures)"; "our
  environment executes a real-model host across a local deterministic
  MCP+A2A protocol composition (protocol fixtures, not an LM emulator)".
- §14 (conclusion): "a real-model host over local deterministic MCP and
  A2A protocol fixtures".

## Claim-audit edits (Phase 5C §3)

- **Title** changed from *"When Safe Agents Compose Unsafely: Cross-Protocol
  Failure Propagation Across MCP and A2A Agent Systems"* to
  *"Cross-Protocol Failure Propagation Across MCP and A2A Agents: A
  Controlled Pilot on Information Flow, Behavioral Influence, and
  Containment"* — the old title asserts a general conclusion the data
  (0 direct egress, 100% containment) does not support.
- **Causal language softened.** §9.3: "exceeded" → "showed a higher rate
  than". §10: removed "the adversarial artifact did shift the host …" and
  "were both effective"; replaced with association language ("was
  associated with a higher … rate") and an explicit "We do not claim that
  the adversarial artifact *causes* mutating requests in a mechanistic
  sense, nor that either … is robust." §14: "shifted every model toward" →
  "was associated with a higher … rate … in all three models"; added "not
  a causal-mechanism claim".
- **General-safety language removed.** "held under cross-protocol pressure"
  / "both effective" → per-trial observational statements ("every one of
  the observed actual mutating-tool requests was blocked"; "no influenced
  mutating request executed"). §9.4: "Every actual mutating-tool request
  was blocked" → "Every *observed* actual mutating-tool request was
  blocked". §9.5 bullets rewritten to observation form.
- **Interval non-overlap.** §9.3 now states explicitly that non-overlap of
  the two per-condition Wilson intervals "is a descriptive observation,
  **not** a hypothesis test," reiterating the no-independence and
  no-p-value stance.
- **Semantic leakage.** Unchanged and already correct — abstract, §7,
  §9.2, §10, §11, §14 all state that direct sensitive egress is a
  verbatim-marker measurement and that a 0 result does not establish the
  absence of semantic/paraphrased leakage, which is not measured.
- **"First" claims.** §2 already disclaims "first MCP/A2A benchmark" and
  now also disclaims priority on composition safety / cross-protocol
  lateral movement / MCP+A2A protocol pivoting, citing [@agentrfc2026] and
  [@mohiuddin2026mcpsec]. No "first" claim remains anywhere in the paper.

---

UNRESOLVED SUBMISSION-BLOCKING ITEMS: NONE

---

## Phase 6F addendum (v4r1 manuscript rebuild)

The manuscript was rebuilt from the frozen v4r1 Phase 6 study. Five
references were added: one model reference plus four related-work
references.

## Phase 6F.1 — the four related-work references: WEB-VERIFIED FROM PRIMARY SOURCES

The four related-work references below were **independently web-verified
against their primary arXiv records** (author lists in the arXiv author
line, exact titles, primary class, submission dates, DOIs) and, for
ProtocolBench, the ICML 2026 / PMLR camera-ready. Confidence: **High**.

| key | verified fields | primary source(s) |
|---|---|---|
| `mcphunt2026` | **Haonan Li, Tianjun Sun, Yongqing Wang, Qisheng Zhang**; exact title *"MCPHunt: An Evaluation Framework for Cross-Boundary Data Propagation in Multi-Server MCP Agents"*; **cs.AI**; submitted **30 Apr 2026**; DOI **10.48550/arXiv.2604.27819** | arXiv:2604.27819 (arXiv abstract page) |
| `agentrfc2026` | **Shenghan Zheng, Qifan Zhang** (2 authors, complete); exact title *"AgentRFC: Security Design Principles and Conformance Testing for Agent Protocols"*; **cs.CR**; submitted **25 Mar 2026**; DOI **10.48550/arXiv.2603.23801** | arXiv:2603.23801 (arXiv abstract page); already High from Phase 5C, DOI added |
| `agentthread2026` | **Shenghan Zheng, Qifan Zhang, Zheng Zhang, Haonan Li, Christophe Hauser** (5 authors); exact title *"Formal Security Analysis of Agent Protocol Composition"* — **AgentThread is the framework this paper introduces, NOT the paper title**; **cs.CR**; submitted **27 Jun 2026**; DOI **10.48550/arXiv.2606.28690** | arXiv:2606.28690 (arXiv abstract page) |
| `protocolbench2026` | **Hongyi Du, Jiaqi Su, Jisen Li, Lijie Ding, Yingxuan Yang, Peixuan Han, Xiangru Tang, Kunlun Zhu, Jiaxuan You** (9 authors); exact current title *"ProtocolBench: Which LLM MultiAgent Protocol to Choose?"*; **cs.AI**; arXiv:2510.17149 (v1 **20 Oct 2025**, v3 **2 Jun 2026**), DOI 10.48550/arXiv.2510.17149; **accepted to ICML 2026** — camera-ready cites *Proceedings of the 43rd International Conference on Machine Learning, PMLR 306, 2026* | arXiv:2510.17149 (arXiv abstract/versions page); ICML 2026 / PMLR camera-ready |

`protocolbench2026` is entered as **`@inproceedings` (ICML 2026, PMLR 306)**
with the arXiv identifier retained in the `note` for traceability, rather
than a 2026-dated `@misc`. `anthropic-claude` model id is cross-checked
against the frozen v4r1 provenance (`requested_model == returned_model ==
claude-sonnet-5` for every Anthropic trial).

Related-work prose accuracy (verified against the above): MCPHunt =
multi-server MCP cross-boundary propagation / canary tracking; AgentRFC =
security design principles, TLA+ invariants, conformance checking, and
protocol-composition safety; Formal Security Analysis / AgentThread =
source-linked formal analysis plus SDK replay and findings that emerge
under protocol composition; ProtocolBench = evaluates protocol choice
primarily through task success, latency, communication overhead, and
failure robustness — **not our MCP→A2A information-flow experiment**.
No priority claim is made over any of them.

Bibliographic note corrections: the `mcp-spec` entry's SDK note was
corrected from "MCP Python SDK v1.6.0" to `mcp==2.0.0` (the actual version
in the frozen v4r1 run environment; resolved dependency lock SHA-256
`6b0d8279010a57be250d134ca291403061b4a8f7937fd2c93563ef9f6243fb56`).

`wilson1927` remains in the database but is **no longer cited**: the v4r1
manuscript reports 10-pair descriptive bootstrap intervals (seed
`20260615`), not Wilson score intervals. All 18 cited keys resolve;
`pdflatex` + `bibtex` produce 0 undefined citations.

The historical "240 trials" figures elsewhere in this file describe the
superseded Phase 4B pilot and are retained as a record of that audit; the
v4r1 study has **320 RQ1 trials, 320 planned / 319 analysable RQ2 trials,
640 scheduled total**.

## Phase 6F.2 — bibliography brace-protection and numeric-table provenance

- **Brace-protection for `plainnat` title lowercasing.** `plainnat`
  lowercases every title word not inside braces. Proper nouns that would
  otherwise render lowercased were brace-protected in **both**
  `paper/references.bib` and `paper/arxiv/references.bib` (identical files):
  `mcp-spec` and `mohiuddin2026mcpsec` → `{Model Context Protocol}`;
  `anthropic-claude` → `{Anthropic}`; `protocolbench2026` →
  `{Protocol to Choose?}`. No author list, title wording, venue, DOI, year,
  or URL changed; this is rendering-only. The rebuilt `main.bbl` shows these
  as capitalised; `pdflatex` + `bibtex` still produce 0 undefined citations.
- **Numeric tables are now machine-generated.** Every numeric table body in
  `paper/arxiv/main.tex` (RQ1 model summary, RQ1 pair-level appendix, RQ1
  relay diagnostics, RQ2 model summary, RQ2 diagnostics, execution/integrity
  summary, pinned identifiers) and the RQ1 pair-effect figure data are
  produced by `paper/arxiv/gen_tables.py` from the frozen Phase 6E.2
  artifacts (`reports/phase_6e_v4r1/`), `\input`-ed from
  `paper/arxiv/generated/`, and re-verified by
  `paper/arxiv/audit_numbers.py`. This replaced hand-transcription and
  **fixed a Phase 6F data error**: Appendix A `gpt-5.6-sol` /
  `saas-support` printed `0.00` but the frozen `rq1_pair_results.csv` value
  is **−0.75** (it now reconciles with that model's mean −0.250 / median
  −0.125 and with the RQ1 model-summary table). No frozen artifact was
  modified.

UNRESOLVED SUBMISSION-BLOCKING ITEMS: NONE.
