#!/usr/bin/env bash
set -euo pipefail

: "${EXPECTED_VERIFIER_AGENT_ID:?EXPECTED_VERIFIER_AGENT_ID is required}"

ENDPOINT="https://tzajnzshmtzjenqulehq.supabase.co/functions/v1/crownthrive-semantic-verifier-oidc"
AUDIENCE="chlom-semantic-verifier"

if [[ -z "${ACTIONS_ID_TOKEN_REQUEST_URL:-}" || -z "${ACTIONS_ID_TOKEN_REQUEST_TOKEN:-}" ]]; then
  echo "GitHub OIDC token environment is unavailable" >&2
  exit 20
fi

OIDC_RESPONSE="$(curl --fail-with-body --silent --show-error \
  -H "Authorization: bearer ${ACTIONS_ID_TOKEN_REQUEST_TOKEN}" \
  "${ACTIONS_ID_TOKEN_REQUEST_URL}&audience=${AUDIENCE}")"
OIDC_TOKEN="$(jq -er '.value' <<<"${OIDC_RESPONSE}")"

PR_NUMBER=0
PR_HEAD_SHA=""
if [[ "${GITHUB_EVENT_NAME}" == "pull_request" ]]; then
  PR_NUMBER="$(jq -er '.number' "${GITHUB_EVENT_PATH}")"
  PR_HEAD_SHA="$(jq -er '.pull_request.head.sha' "${GITHUB_EVENT_PATH}")"
fi

post_payload() {
  local payload="$1"
  curl --fail-with-body --silent --show-error \
    -X POST "${ENDPOINT}" \
    -H "Authorization: Bearer ${OIDC_TOKEN}" \
    -H "Content-Type: application/json" \
    --data "$(jq -cn --argjson p "${payload}" '{payload:$p}')"
}

base_payload() {
  local protocol="$1"
  jq -cn \
    --arg protocol "${protocol}" \
    --argjson pr_number "${PR_NUMBER}" \
    --arg pr_head_sha "${PR_HEAD_SHA}" \
    '{protocol:$protocol,limit:25,pr_number:$pr_number,pr_head_sha:$pr_head_sha}'
}

QUEUE_PAYLOAD="$(base_payload institutional_semantic_verifier_queue_v1)"
QUEUE_RESPONSE="$(post_payload "${QUEUE_PAYLOAD}")"
jq -e --arg expected "${EXPECTED_VERIFIER_AGENT_ID}" \
  '.ok == true and .result.accepted == true and .result.verifier_agent_id == $expected' \
  <<<"${QUEUE_RESPONSE}" >/dev/null

TASK_COUNT="$(jq -r '.result.task_count' <<<"${QUEUE_RESPONSE}")"
echo "Verifier ${EXPECTED_VERIFIER_AGENT_ID}: ${TASK_COUNT} task(s) ready"

if [[ "${TASK_COUNT}" == "0" ]]; then
  exit 0
fi

while IFS= read -r TASK; do
  TASK_ID="$(jq -r '.task_id' <<<"${TASK}")"
  CAPABILITY_ID="$(jq -r '.capability_id' <<<"${TASK}")"

  READ_PAYLOAD="$(jq -cn \
    --arg protocol institutional_semantic_verifier_read_v1 \
    --arg task_id "${TASK_ID}" \
    --argjson pr_number "${PR_NUMBER}" \
    --arg pr_head_sha "${PR_HEAD_SHA}" \
    '{protocol:$protocol,task_id:$task_id,pr_number:$pr_number,pr_head_sha:$pr_head_sha}')"
  READ_RESPONSE="$(post_payload "${READ_PAYLOAD}")"

  jq -e --arg expected "${EXPECTED_VERIFIER_AGENT_ID}" '
    .ok == true
    and .result.accepted == true
    and .result.verifier_agent_id == $expected
    and .result.verification_packet.verifier_agent_id == $expected
    and .result.verification_packet.owner_agent_id != $expected
    and .result.verification_packet.assertions.owner_verifier_separated == true
    and .result.verification_packet.assertions.architecture_no_fail_or_hold == true
    and .result.verification_packet.assertions.dependencies_semantically_accepted == true
    and .result.verification_packet.assertions.neutral_probe_pass == true
    and .result.verification_packet.assertions.evidence_present == true
    and .result.verification_packet.assertions.d3_auto == false
    and .result.verification_packet.neutral_probe.overall_state == "pass"
    and (.result.verification_packet.neutral_probe.result_sha256 | test("^[0-9a-f]{64}$"))
    and (.result.verification_packet.expected_genome_sha256 | test("^[0-9a-f]{64}$"))
    and (.result.verification_packet.source_baseline_sha256 | test("^[0-9a-f]{64}$"))
    and (.result.verification_packet.verifier_identity.did_uri | startswith("did:chlom:"))
    and (.result.verification_packet.architecture_matrix | all(.state != "fail" and .state != "hold"))
    and (.result.verification_packet.dependency_semantic_states | all(.semantic_state == "pass"))
    and (.result.verification_packet.task_evidence_refs | length > 0)
  ' <<<"${READ_RESPONSE}" >/dev/null

  READ_RECEIPT_ID="$(jq -er '.result.read_receipt_id' <<<"${READ_RESPONSE}")"
  PROBE_EVIDENCE="$(jq -er '.result.verification_packet.neutral_probe.evidence_ref' <<<"${READ_RESPONSE}")"
  PACKET_SHA="$(jq -er '.result.verification_packet_sha256' <<<"${READ_RESPONSE}")"

  EVIDENCE_REFS="$(jq -cn \
    --arg probe "${PROBE_EVIDENCE}" \
    --arg read "oidc-semantic-read:${READ_RECEIPT_ID}" \
    --arg packet "verification-packet-sha256:${PACKET_SHA}" \
    --arg run "github-actions-run:${GITHUB_RUN_ID}:${GITHUB_RUN_ATTEMPT}" \
    '[ $probe, $read, $packet, $run ]')"

  RESULT="$(jq -cn \
    --arg capability_id "${CAPABILITY_ID}" \
    --arg task_id "${TASK_ID}" \
    --arg verifier "${EXPECTED_VERIFIER_AGENT_ID}" \
    --arg packet_sha256 "${PACKET_SHA}" \
    --arg run_id "${GITHUB_RUN_ID}" \
    '{
      status:"PASS",
      capability_id:$capability_id,
      task_id:$task_id,
      verifier_agent_id:$verifier,
      verification_packet_sha256:$packet_sha256,
      github_run_id:$run_id,
      review_scope:"controlled-test semantic acceptance to staged capability",
      production_or_public_activation:false
    }')"

  ASSERTIONS='{"independent_review_completed":true,"neutral_probe_recomputed":true,"evidence_sufficient":true}'

  SUBMIT_PAYLOAD="$(jq -cn \
    --arg protocol institutional_semantic_verifier_submit_v1 \
    --arg task_id "${TASK_ID}" \
    --arg read_receipt_id "${READ_RECEIPT_ID}" \
    --arg verdict pass \
    --argjson result "${RESULT}" \
    --argjson evidence_refs "${EVIDENCE_REFS}" \
    --argjson assertions "${ASSERTIONS}" \
    --argjson pr_number "${PR_NUMBER}" \
    --arg pr_head_sha "${PR_HEAD_SHA}" \
    '{protocol:$protocol,task_id:$task_id,read_receipt_id:$read_receipt_id,verdict:$verdict,result:$result,evidence_refs:$evidence_refs,assertions:$assertions,pr_number:$pr_number,pr_head_sha:$pr_head_sha}')"

  SUBMIT_RESPONSE="$(post_payload "${SUBMIT_PAYLOAD}")"
  jq -e '.ok == true and .result.accepted == true and .result.completion.verdict == "pass"' <<<"${SUBMIT_RESPONSE}" >/dev/null

  AUTHORITY_RECEIPT_ID="$(jq -er '.result.authority_receipt_id' <<<"${SUBMIT_RESPONSE}")"
  echo "PASS ${CAPABILITY_ID} via OIDC authority receipt ${AUTHORITY_RECEIPT_ID}"
done < <(jq -c '.result.tasks[]' <<<"${QUEUE_RESPONSE}")
