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
# automatically on exit, whether the script succeeds or fails.
#
# Usage: ./scripts/demo.sh

set -euo pipefail

BASE_URL="http://localhost:8000"
HEALTH_TIMEOUT_SECONDS=60

BOLD=$(tput bold 2>/dev/null || echo "")
RESET=$(tput sgr0 2>/dev/null || echo "")
GREEN=$(tput setaf 2 2>/dev/null || echo "")
RED=$(tput setaf 1 2>/dev/null || echo "")
YELLOW=$(tput setaf 3 2>/dev/null || echo "")
CYAN=$(tput setaf 6 2>/dev/null || echo "")

section() {
    echo
    echo "${BOLD}${CYAN}=== $1 ===${RESET}"
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

section "Starting Agent Interop Bench (docker compose up --build)"
docker compose up --build -d

section "Waiting for the health endpoint"
elapsed=0
until curl -sf "$BASE_URL/health" >/dev/null 2>&1; do
    elapsed=$((elapsed + 1))
    if [ "$elapsed" -ge "$HEALTH_TIMEOUT_SECONDS" ]; then
        echo "${RED}Service did not become healthy within ${HEALTH_TIMEOUT_SECONDS}s.${RESET}" >&2
        exit 1
    fi
    sleep 1
done
echo "${GREEN}Healthy after ${elapsed}s${RESET}"
curl -s "$BASE_URL/health"
echo

section "MCP tool discovery (GET /tools)"
curl -sf "$BASE_URL/tools" | python3 -c "
import json, sys
for tool in json.load(sys.stdin):
    print(f\"  - {tool['name']:<16} {tool['description']}\")
"

section "Benchmark suite (GET /benchmarks)"
curl -sf "$BASE_URL/benchmarks" | python3 -c "
import json, sys
cases = json.load(sys.stdin)
print(f'{len(cases)} deterministic benchmark cases loaded:')
for c in cases:
    print(f\"  - {c['id']:<38} [{c['category']}]\")
"

section "Running the full benchmark suite (POST /runs)"
run_response=$(curl -sf -X POST "$BASE_URL/runs")
run_id=$(echo "$run_response" | python3 -c "import json, sys; print(json.load(sys.stdin)['run_id'])")
echo "Run ID: ${BOLD}${run_id}${RESET}"

section "Fetching the generated report (GET /runs/${run_id}/report)"
report=$(curl -sf "$BASE_URL/runs/${run_id}/report")

section "Reliability scores (real numbers from this run, not hard-coded)"
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

section "Intentional evaluator-validation failures — NOT broken software"
echo "${YELLOW}These cases are deliberately designed to fail. Their job is to prove the"
echo "evaluators correctly CATCH bad agent behavior (a wrong tool, a missing"
echo "argument, a hallucinated tool) rather than to always pass.${RESET}"
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

section "Demo complete"
echo "Report fetched from: ${BASE_URL}/runs/${run_id}/report"
echo "Docker resources will now be torn down."
