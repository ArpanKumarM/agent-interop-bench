#!/usr/bin/env bash
#
# Agent Interop Bench — end-to-end demo.
#
# Starts the stack via Docker Compose, waits for it to become healthy,
# discovers MCP tools, lists the benchmark suite, runs a full benchmark
# pass, fetches the generated JSON report, and prints the reliability
# scores together with the intentional evaluator-validation failures.
#
# Everything here is local: the mock MCP server never touches the network,
# and no API key of any kind is required. Docker resources are torn down
# automatically on exit — success, failure, or Ctrl+C.
#
# Modes:
#   (no option)     Detailed: full verbose output of every API response.
#   --presentation  Condensed output for live demos. No timing pauses.
#   --recording     Condensed output plus timed pauses between sections,
#                   paced for a 30-40 second screen recording.
#   --help          Show usage and exit.
#
# Usage: ./scripts/demo.sh [--presentation|--recording|--help]

set -euo pipefail

BASE_URL="http://localhost:8000"
HEALTH_TIMEOUT_SECONDS=60
RUN_TIMEOUT_SECONDS=60

BOLD=$(tput bold 2>/dev/null || echo "")
RESET=$(tput sgr0 2>/dev/null || echo "")
GREEN=$(tput setaf 2 2>/dev/null || echo "")
RED=$(tput setaf 1 2>/dev/null || echo "")
YELLOW=$(tput setaf 3 2>/dev/null || echo "")
CYAN=$(tput setaf 6 2>/dev/null || echo "")

MODE="detailed"
RECORDING=false

usage() {
    cat <<'EOF'
Usage: ./scripts/demo.sh [OPTION]

  (no option)      Detailed mode (default): full verbose output of every
                    API response — good for reading closely or debugging.
  --presentation   Condensed output for live demos. No timing pauses.
  --recording      Condensed output plus timed pauses between sections,
                    paced for a 30-40 second screen recording. Pauses are
                    skipped automatically when stdout is not a terminal,
                    so automated runs stay fast.
  --help, -h       Show this help and exit.

Environment:
  DEMO_DELAY_MULTIPLIER   Scales --recording pause durations (default: 1).
                          Example: DEMO_DELAY_MULTIPLIER=0.5 halves them.

Recording command:
  ./scripts/demo.sh --recording
EOF
}

while [ $# -gt 0 ]; do
    case "$1" in
        --presentation)
            MODE="presentation"
            ;;
        --recording)
            MODE="presentation"
            RECORDING=true
            ;;
        --help | -h)
            usage
            exit 0
            ;;
        *)
            echo "Unknown option: $1" >&2
            usage >&2
            exit 2
            ;;
    esac
    shift
done

DELAY_MULTIPLIER="${DEMO_DELAY_MULTIPLIER:-1}"

section() {
    echo
    echo "${BOLD}${CYAN}=== $1 ===${RESET}"
}

# Sleeps for $1 base seconds, scaled by DEMO_DELAY_MULTIPLIER. Only takes
# effect in --recording mode, and only when stdout is an interactive
# terminal — never during automated/non-interactive runs. This is presen-
# tation pacing only: it is never applied around the real API calls below,
# so it can never be mistaken for measured benchmark latency.
pause() {
    if [ "$RECORDING" != true ] || [ ! -t 1 ]; then
        return 0
    fi
    local secs
    secs=$(python3 -c "print(max(0.0, float(${1}) * float(${DELAY_MULTIPLIER})))")
    sleep "$secs"
}

for cmd in docker curl python3; do
    if ! command -v "$cmd" >/dev/null 2>&1; then
        echo "${RED}Required command not found: $cmd${RESET}" >&2
        exit 1
    fi
done

cleanup() {
    section "Cleaning up Docker resources"
    docker compose down
}
trap cleanup EXIT

# ---------------------------------------------------------------------------
# Title screen (presentation family only — detailed mode is unchanged below)
# ---------------------------------------------------------------------------
if [ "$MODE" = "presentation" ]; then
    section "Agent Interop Bench — Live Demo"
    echo "Reliability, security, and interoperability testing for MCP agents."
    echo "${YELLOW}(Pauses below are presentation pacing only — the benchmark itself runs"
    echo "at its own real, measured speed; see \"Average latency\" further down.)${RESET}"
    pause 3
fi

# ---------------------------------------------------------------------------
# Start the stack and wait for health
# ---------------------------------------------------------------------------
if [ "$MODE" = "detailed" ]; then
    section "Starting Agent Interop Bench (docker compose up --build)"
    docker compose up --build -d
else
    docker compose up --build -d >/dev/null 2>&1
fi

if [ "$MODE" = "detailed" ]; then
    section "Waiting for the health endpoint"
fi
elapsed=0
until curl -sf "$BASE_URL/health" >/dev/null 2>&1; do
    elapsed=$((elapsed + 1))
    if [ "$elapsed" -ge "$HEALTH_TIMEOUT_SECONDS" ]; then
        echo "${RED}Service did not become healthy within ${HEALTH_TIMEOUT_SECONDS}s.${RESET}" >&2
        exit 1
    fi
    sleep 1
done

if [ "$MODE" = "detailed" ]; then
    echo "${GREEN}Healthy after ${elapsed}s${RESET}"
    curl -s "$BASE_URL/health"
    echo
else
    section "Container & Health Status"
    echo "Container:    ${GREEN}agent-interop-bench-api-1 (healthy)${RESET}"
    echo -n "Health check: "
    curl -s "$BASE_URL/health"
    echo "  (ready after ${elapsed}s)"
    pause 2
fi

# ---------------------------------------------------------------------------
# Tool discovery
# ---------------------------------------------------------------------------
tools_json=$(curl -sf "$BASE_URL/tools")
if [ "$MODE" = "detailed" ]; then
    section "MCP tool discovery (GET /tools)"
    echo "$tools_json" | python3 -c "
import json, sys
for tool in json.load(sys.stdin):
    print(f\"  - {tool['name']:<16} {tool['description']}\")
"
else
    section "Discovered MCP Tools"
    echo "$tools_json" | python3 -c "
import json, sys
tools = json.load(sys.stdin)
print(f'{len(tools)} tools discovered from the mock MCP server:')
for tool in tools:
    print(f\"  - {tool['name']}\")
"
    pause 4
fi

# ---------------------------------------------------------------------------
# Benchmark suite
# ---------------------------------------------------------------------------
benchmarks_json=$(curl -sf "$BASE_URL/benchmarks")
if [ "$MODE" = "detailed" ]; then
    section "Benchmark suite (GET /benchmarks)"
    echo "$benchmarks_json" | python3 -c "
import json, sys
cases = json.load(sys.stdin)
print(f'{len(cases)} deterministic benchmark cases loaded:')
for c in cases:
    print(f\"  - {c['id']:<38} [{c['category']}]\")
"
else
    section "Benchmark Suite Overview"
    echo "$benchmarks_json" | python3 -c "
import json, sys
from collections import Counter
cases = json.load(sys.stdin)
counts = Counter(c['category'] for c in cases)
print(f'{len(cases)} deterministic benchmark cases across {len(counts)} categories:')
for category, n in sorted(counts.items()):
    print(f'  - {category:<28} x{n}')
"
    pause 3
fi

# ---------------------------------------------------------------------------
# Run the benchmark — real work, no artificial delay of any kind here.
# ---------------------------------------------------------------------------
if [ "$MODE" = "detailed" ]; then
    section "Running the full benchmark suite (POST /runs)"
else
    section "Running Benchmark"
    echo "Executing all cases against the mock MCP server..."
fi
run_response=$(curl -sf -X POST "$BASE_URL/runs")
run_id=$(echo "$run_response" | python3 -c "import json, sys; print(json.load(sys.stdin)['run_id'])")
if [ "$MODE" = "detailed" ]; then
    echo "Run ID: ${BOLD}${run_id}${RESET}"
    echo "Run queued (202 Accepted) — polling GET /runs/${run_id} until it completes..."
fi

# POST /runs is asynchronous: it queues the run and returns immediately.
# Poll status until it leaves queued/running.
elapsed=0
run_status=""
until [ "$run_status" = "completed" ] || [ "$run_status" = "failed" ]; do
    elapsed=$((elapsed + 1))
    if [ "$elapsed" -ge "$RUN_TIMEOUT_SECONDS" ]; then
        echo "${RED}Run did not finish within ${RUN_TIMEOUT_SECONDS}s.${RESET}" >&2
        exit 1
    fi
    sleep 1
    run_status=$(curl -sf "$BASE_URL/runs/${run_id}" | python3 -c "import json, sys; print(json.load(sys.stdin)['status'])")
done

if [ "$run_status" = "failed" ]; then
    echo "${RED}Run failed.${RESET} See GET /runs/${run_id} for error details." >&2
    exit 1
fi

if [ "$MODE" = "detailed" ]; then
    section "Fetching the generated report (GET /runs/${run_id}/report)"
fi
report=$(curl -sf "$BASE_URL/runs/${run_id}/report")

# ---------------------------------------------------------------------------
# Results — real numbers from this run, never hard-coded.
# ---------------------------------------------------------------------------
if [ "$MODE" = "detailed" ]; then
    section "Reliability scores (real numbers from this run, not hard-coded)"
else
    section "Results"
fi
if [ "$MODE" = "detailed" ]; then
    echo "$report" | python3 -c "
import json, sys
r = json.load(sys.stdin)
s = r['summary']
print(f\"Suite:                        {r['suite_name']}\")
print(f\"Total tests:                  {s['total_tests']}\")
print(f\"Passed:                       {s['passed_tests']}\")
print(f\"Failed:                       {s['failed_tests']}\")
print(f\"Tool selection accuracy:      {s['tool_selection_accuracy']:.1%}\")
print(f\"Argument accuracy:            {s['argument_accuracy']:.1%}\")
print(f\"Recovery rate:                {s['recovery_rate']:.1%}\")
print(f\"Unsafe action rate:           {s['unsafe_action_rate']:.1%}  (lower is better)\")
print(f\"Prompt injection resistance:  {s['prompt_injection_resistance']:.1%}\")
print(f\"Average latency:              {s['average_latency_ms']:.1f} ms\")
"
else
    echo "$report" | python3 -c "
import json, sys
r = json.load(sys.stdin)
s = r['summary']
print(f\"Run ID:                       {r['run_id']}\")
print(f\"Suite:                        {r['suite_name']}\")
print(f\"Total tests:                  {s['total_tests']}\")
print(f\"Passed:                       {s['passed_tests']}\")
print(f\"Failed:                       {s['failed_tests']}\")
print(f\"Tool selection accuracy:      {s['tool_selection_accuracy']:.1%}\")
print(f\"Argument accuracy:            {s['argument_accuracy']:.1%}\")
print(f\"Recovery rate:                {s['recovery_rate']:.1%}\")
print(f\"Unsafe action rate:           {s['unsafe_action_rate']:.1%}  (lower is better)\")
print(f\"Prompt injection resistance:  {s['prompt_injection_resistance']:.1%}\")
print(f\"Average latency:              {s['average_latency_ms']:.1f} ms  (measured, not simulated)\")
"
    pause 8
fi

# ---------------------------------------------------------------------------
# Intentional evaluator-validation failures — NOT broken software.
# ---------------------------------------------------------------------------
section "Intentional evaluator-validation failures — NOT broken software"
echo "${YELLOW}These cases are deliberately designed to fail. Their job is to prove the"
echo "evaluators correctly CATCH bad agent behavior (a wrong tool, a missing"
echo "argument, a hallucinated tool) rather than to always pass.${RESET}"
if [ "$MODE" = "detailed" ]; then
    echo "$report" | python3 -c "
import json, sys
r = json.load(sys.stdin)
failing = [c for c in r['per_test'] if not c['passed']]
if not failing:
    print('No failing cases in this run.')
for c in failing:
    print(f\"\n  - {c['case_id']}  [{c['category']}]\")
    for reason in c['failure_reasons']:
        print(f'      -> {reason}')
"
else
    echo "$report" | python3 -c "
import json, sys
r = json.load(sys.stdin)
failing = [c for c in r['per_test'] if not c['passed']]
if not failing:
    print('No failing cases in this run.')
for c in failing:
    reason = '; '.join(c['failure_reasons'])
    print(f\"  - {c['case_id']:<38} {reason}\")
"
    pause 7
fi

# ---------------------------------------------------------------------------
# Closing screen
# ---------------------------------------------------------------------------
if [ "$MODE" = "detailed" ]; then
    section "Demo complete"
    echo "Report fetched from: ${BASE_URL}/runs/${run_id}/report"
    echo "Docker resources will now be torn down."
else
    section "Agent Interop Bench"
    echo "https://github.com/ArpanKumarM/agent-interop-bench"
    echo "Cleaning up automatically now."
    pause 5
fi
