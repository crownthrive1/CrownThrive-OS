#!/usr/bin/env python3
"""Deterministic validator and inventory emitter for the CrownThrive agent suite."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "governance/agent-suite-v1/agent-registry.json"
COMMITTEES = ROOT / "governance/agent-suite-v1/committee-registry.json"
SCHEDULES = ROOT / "governance/agent-suite-v1/schedule-registry.json"
SKILLS = ROOT / "developers/manifests/agent-skill-catalog.v1.json"
CUSTODY = ROOT / "developers/manifests/custody-policy.v1.json"
QUARANTINE = ROOT / "developers/manifests/source-generation-quarantine.v1.json"
PRICING = ROOT / "developers/manifests/pricing-policy-candidates.v1.json"
FRAMEWORK_CANDIDATE = ROOT / "framework-candidates/thrivealumni-committee-support.v1.json"
MASTER = ROOT / "developers/manifests/agent-capability-master-suite.v1.json"
SCHEMA = ROOT / "developers/schemas/agent-capability-master-suite.schema.v1.0.1.json"
LINKAGE = ROOT / "linkage/linkage-candidates.v1.json"
BASELINE_SNAPSHOT = ROOT / "developers/manifests/canonical-agent-reference-snapshot.v1.json"
CANONICAL_BASELINE_MANIFESTS = (
    ROOT / "developers/manifests/agent-federation-bindings.v1.json",
    ROOT / "developers/manifests/agent-sovereign-governance.v1.json",
)
AGENT_REFERENCE_RE = re.compile(r"^ct\.(?:agent|subagent|relay)\.[a-z0-9.-]+$")


class SuiteValidationError(ValueError):
    pass


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise SuiteValidationError(f"{path}: top-level value must be an object")
    return value


def canonical_sha256(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def collect_agent_references(value: Any) -> set[str]:
    references: set[str] = set()
    if isinstance(value, str) and AGENT_REFERENCE_RE.fullmatch(value):
        references.add(value)
    elif isinstance(value, list):
        for item in value:
            references.update(collect_agent_references(item))
    elif isinstance(value, dict):
        for item in value.values():
            references.update(collect_agent_references(item))
    return references


def resolve_baseline_agents(root: Path, require_canonical: bool) -> tuple[set[str], str]:
    canonical_paths = tuple(root / path.relative_to(ROOT) for path in CANONICAL_BASELINE_MANIFESTS)
    available = [path for path in canonical_paths if path.is_file()]
    primary = root / CANONICAL_BASELINE_MANIFESTS[0].relative_to(ROOT)
    if primary.is_file():
        references: set[str] = set()
        for path in available:
            references.update(collect_agent_references(load_json(path)))
        if not references:
            raise SuiteValidationError("canonical baseline manifests contain no agent references")
        return references, "CANONICAL_REPOSITORY_MANIFESTS"
    if require_canonical:
        raise SuiteValidationError(f"canonical baseline manifest missing: {primary.relative_to(root)}")
    snapshot_path = root / BASELINE_SNAPSHOT.relative_to(ROOT)
    snapshot = load_json(snapshot_path)
    if snapshot.get("state") != "DETACHED_REFERENCE_SNAPSHOT_NOT_RUNTIME_ATTESTATION":
        raise SuiteValidationError("portable baseline snapshot state is invalid")
    if not re.fullmatch(r"[0-9a-f]{40}", str(snapshot.get("source_blob_sha", ""))):
        raise SuiteValidationError("portable baseline snapshot lacks an exact source blob SHA")
    references = set(snapshot.get("agent_ids", []))
    if not references or any(not AGENT_REFERENCE_RE.fullmatch(item) for item in references):
        raise SuiteValidationError("portable baseline snapshot contains invalid agent identifiers")
    return references, "DETACHED_SNAPSHOT_CONTROLLED_TEST_ONLY"


def resolve_json_pointer(root_schema: dict[str, Any], reference: str) -> dict[str, Any]:
    if not reference.startswith("#/"):
        raise SuiteValidationError(f"unsupported non-local schema reference: {reference}")
    value: Any = root_schema
    for token in reference[2:].split("/"):
        token = token.replace("~1", "/").replace("~0", "~")
        if not isinstance(value, dict) or token not in value:
            raise SuiteValidationError(f"unresolved schema reference: {reference}")
        value = value[token]
    if not isinstance(value, dict):
        raise SuiteValidationError(f"schema reference does not resolve to an object: {reference}")
    return value


def json_type_matches(value: Any, declared: str) -> bool:
    return {
        "object": isinstance(value, dict),
        "array": isinstance(value, list),
        "string": isinstance(value, str),
        "boolean": type(value) is bool,
        "integer": type(value) is int,
        "number": type(value) in {int, float},
        "null": value is None,
    }.get(declared, False)


def validate_schema_instance(
    value: Any,
    schema: dict[str, Any],
    root_schema: dict[str, Any],
    path: str = "$",
) -> list[str]:
    errors: list[str] = []
    if "$ref" in schema:
        errors.extend(validate_schema_instance(value, resolve_json_pointer(root_schema, schema["$ref"]), root_schema, path))
    for branch in schema.get("allOf", []):
        errors.extend(validate_schema_instance(value, branch, root_schema, path))
    declared_type = schema.get("type")
    if declared_type is not None:
        allowed_types = [declared_type] if isinstance(declared_type, str) else declared_type
        if not any(json_type_matches(value, item) for item in allowed_types):
            return errors + [f"{path}: expected JSON type {allowed_types}, got {type(value).__name__}"]
    if "const" in schema and value != schema["const"]:
        errors.append(f"{path}: value does not match const")
    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"{path}: value is outside enum")
    if isinstance(value, str):
        if len(value) < schema.get("minLength", 0):
            errors.append(f"{path}: string is shorter than minLength")
        if "pattern" in schema and not re.fullmatch(schema["pattern"], value):
            errors.append(f"{path}: string does not match pattern")
        try:
            if schema.get("format") == "date":
                date.fromisoformat(value)
            elif schema.get("format") == "date-time":
                datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            errors.append(f"{path}: invalid {schema.get('format')} format")
    if isinstance(value, list):
        if len(value) < schema.get("minItems", 0):
            errors.append(f"{path}: array is shorter than minItems")
        if schema.get("uniqueItems"):
            encoded = [json.dumps(item, sort_keys=True, separators=(",", ":")) for item in value]
            if len(encoded) != len(set(encoded)):
                errors.append(f"{path}: array items are not unique")
        if isinstance(schema.get("items"), dict):
            for index, item in enumerate(value):
                errors.extend(validate_schema_instance(item, schema["items"], root_schema, f"{path}[{index}]"))
        if isinstance(schema.get("contains"), dict):
            if not any(not validate_schema_instance(item, schema["contains"], root_schema, f"{path}[*]") for item in value):
                errors.append(f"{path}: array does not satisfy contains")
    if isinstance(value, dict):
        required = schema.get("required", [])
        for key in required:
            if key not in value:
                errors.append(f"{path}: missing required property {key}")
        properties = schema.get("properties", {})
        for key, item in value.items():
            if key in properties:
                errors.extend(validate_schema_instance(item, properties[key], root_schema, f"{path}.{key}"))
            elif schema.get("additionalProperties") is False:
                errors.append(f"{path}: additional property forbidden: {key}")
    return errors


def validate(*, require_canonical_baseline: bool = False) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    registry = load_json(REGISTRY)
    committees = load_json(COMMITTEES)
    schedules = load_json(SCHEDULES)
    skills = load_json(SKILLS)
    custody = load_json(CUSTODY)
    quarantine = load_json(QUARANTINE)
    pricing = load_json(PRICING)
    framework = load_json(FRAMEWORK_CANDIDATE)
    master = load_json(MASTER)
    schema = load_json(SCHEMA)
    linkage = load_json(LINKAGE)
    baseline_agents, baseline_state = resolve_baseline_agents(ROOT, require_canonical_baseline)

    schema_errors = validate_schema_instance(registry, schema, schema)
    errors.extend(f"schema: {error}" for error in schema_errors)

    agents = registry.get("agents", [])
    if len(agents) != 26:
        errors.append(f"expected 26 scoped subagents, found {len(agents)}")
    ids = [agent.get("agent_id") for agent in agents]
    if len(ids) != len(set(ids)):
        errors.append("agent IDs are not unique")
    names = [agent.get("canonical_name") for agent in agents]
    if len(names) != len(set(names)):
        errors.append("agent canonical names are not unique")

    modes = {"rigid": 0, "fluid": 0, "hybrid": 0}
    for agent in agents:
        agent_id = agent.get("agent_id", "<missing>")
        mode = agent.get("mode")
        if mode not in modes:
            errors.append(f"{agent_id}: invalid operating mode {mode!r}")
        else:
            modes[mode] += 1
        if agent.get("authority_ceiling") == "D3":
            errors.append(f"{agent_id}: D3 must remain human-reserved")
        if agent.get("autonomy_class") not in {"A0", "A1", "A2"}:
            errors.append(f"{agent_id}: autonomy above A2 is not allowed in controlled test")
        forbidden = set(agent.get("forbidden", []))
        if "self_approve" not in forbidden:
            errors.append(f"{agent_id}: self approval prohibition missing")
        if not agent.get("allowed"):
            errors.append(f"{agent_id}: empty allowed capability set")
        parent_binding = agent.get("parent_binding", {})
        if parent_binding.get("parent_agent_id") not in baseline_agents:
            errors.append(f"{agent_id}: parent is absent from canonical baseline references")
        if parent_binding.get("privilege_inheritance") is not False:
            errors.append(f"{agent_id}: parent privilege inheritance must be false")
        identity = agent.get("identity_record", {})
        if identity.get("state") != "CANDIDATE_UNATTESTED" or identity.get("runtime_attestation_verified") is not False:
            errors.append(f"{agent_id}: controlled-test identity state is invalid")
        heartbeat = agent.get("heartbeat_record", {})
        if heartbeat.get("required") is not True or heartbeat.get("state") != "PENDING_FIRST_HEARTBEAT":
            errors.append(f"{agent_id}: heartbeat must remain required and pending first observation")
        if heartbeat.get("last_verified_at") is not None:
            errors.append(f"{agent_id}: unobserved heartbeat cannot have a verification time")
        privilege = agent.get("privilege_record", {})
        if privilege.get("state") != "DENY_BY_DEFAULT" or privilege.get("inheritance") is not False:
            errors.append(f"{agent_id}: privileges must deny by default and remain non-inheritable")
        if privilege.get("max_authority") != agent.get("authority_ceiling"):
            errors.append(f"{agent_id}: privilege ceiling differs from agent authority ceiling")
        if privilege.get("special_privileges") != "DENIED_PENDING_SEPARATE_RECEIPT":
            errors.append(f"{agent_id}: special privileges are not fail-closed")
        if privilege.get("break_glass_allowed") is not False:
            errors.append(f"{agent_id}: machine break-glass must remain forbidden")
        if agent.get("lifecycle_state") != "REGISTERED_CONTROLLED_TEST":
            errors.append(f"{agent_id}: lifecycle state must remain controlled test")
    if any(count == 0 for count in modes.values()):
        errors.append("rigid, fluid and hybrid modes must all be represented")

    contract = registry.get("operating_contract", {})
    required_true = {
        "human_authority_reserved",
        "self_approval_forbidden",
        "silent_delete_forbidden",
        "append_only_correction_history",
    }
    for key in required_true:
        if contract.get(key) is not True:
            errors.append(f"operating_contract.{key} must be true")
    for key in {"vote_eligible", "quorum_eligible", "privilege_inheritance"}:
        if contract.get(key) is not False:
            errors.append(f"operating_contract.{key} must be false")

    known_agents = set(ids) | baseline_agents
    committee_rows = committees.get("committees", [])
    if len(committee_rows) != 14:
        errors.append(f"expected 14 public ThriveAlumni surfaces, found {len(committee_rows)}")
    required_assessments = {"roster", "charter", "quorum", "delegation", "authority", "recusal"}
    for committee in committee_rows:
        for agent_id in committee.get("support_agents", []):
            if agent_id not in known_agents:
                errors.append(f"{committee.get('committee_id')}: unknown agent {agent_id}")
        if committee.get("drift_state") == "PASS":
            errors.append(f"{committee.get('committee_id')}: unresolved public drift cannot be PASS")
        assessment = committee.get("evidence_assessment")
        if not isinstance(assessment, dict) or set(assessment) != required_assessments:
            errors.append(f"{committee.get('committee_id')}: six-field evidence assessment is required")
        elif any(value != "NOT_ASSESSED" for value in assessment.values()):
            errors.append(f"{committee.get('committee_id')}: unavailable governance evidence must remain NOT_ASSESSED")

    schedule_rows = schedules.get("schedules", [])
    if len(schedule_rows) != 8:
        errors.append(f"expected 8 consolidated schedules, found {len(schedule_rows)}")
    schedule_ids = [row.get("schedule_id") for row in schedule_rows]
    if len(schedule_ids) != len(set(schedule_ids)):
        errors.append("schedule IDs are not unique")
    for row in schedule_rows:
        if not row.get("skill", "").startswith("$crownthrive-"):
            errors.append(f"{row.get('schedule_id')}: schedule must invoke an installed suite skill")
        for agent_id in row.get("agents", []):
            if agent_id not in known_agents:
                errors.append(f"{row.get('schedule_id')}: unknown scheduled agent {agent_id}")
        if row.get("route_state") != "REGISTERED_PARENT_SUBROUTE_PENDING_FIRST_HEARTBEAT":
            errors.append(f"{row.get('schedule_id')}: route state must remain pending first heartbeat")
        if row.get("execution_receipt") is not None:
            errors.append(f"{row.get('schedule_id')}: unobserved subroute cannot carry an execution receipt")
    dispatcher = schedules.get("dispatcher", {})
    if dispatcher.get("new_active_task_created") is not False:
        errors.append("suite must not claim creation of a new active parent task")
    if dispatcher.get("provider_update_observed") is not True:
        errors.append("parent dispatcher update observation is missing")
    if dispatcher.get("runtime_execution_verified") is not False:
        errors.append("runtime execution must remain unverified until a subroute heartbeat exists")
    if dispatcher.get("first_subroute_heartbeat_observed") is not False:
        errors.append("first subroute heartbeat is not yet evidenced")

    master_skills = skills.get("master_skills", [])
    covered_agents = {
        agent_id
        for skill in master_skills
        for agent_id in skill.get("agent_registry_filter", [])
    }
    uncovered = set(ids) - covered_agents
    if uncovered:
        errors.append("agents missing from master skills: " + ", ".join(sorted(uncovered)))
    if skills.get("commercial_state") != "HOLD":
        errors.append("skill catalog must remain commercial HOLD")
    if skills.get("checkout_enabled") is not False or skills.get("entitlements_active") is not False:
        errors.append("skill checkout and entitlements must remain disabled")

    destinations = {row.get("store_class") for row in custody.get("destinations", []) if row.get("required")}
    if destinations != {"human_recovery_archive", "replaceable_private_object_store", "secret_seal_store"}:
        errors.append("custody policy must require independent recovery, object, and secret-seal store classes")
    if custody.get("state") != "POLICY_REQUIRED_NOT_FULLY_PROVEN":
        errors.append("custody policy must remain not fully proven until both artifact receipts exist")
    secret_store = next((row for row in custody.get("destinations", []) if row.get("store_class") == "secret_seal_store"), {})
    if secret_store.get("artifact_bytes_allowed") is not False:
        errors.append("secret-seal store must forbid bulk artifact bytes")

    if quarantine.get("state") != "HOLD_NEED_TO_DO":
        errors.append("detached generation evidence must remain quarantined")
    if quarantine.get("classification") != "PUBLIC_STANDARD_METADATA_ONLY":
        errors.append("public source quarantine must remain metadata-only")
    if quarantine.get("retained_generation", {}).get("semantic_compilation_allowed") is not False:
        errors.append("retained title-level evidence cannot authorize semantic compilation")
    if quarantine.get("detached_generation", {}).get("certifies_retained_generation") is not False:
        errors.append("detached generation cannot certify the retained generation")

    if pricing.get("state") != "GOVERNED_HOLD":
        errors.append("pricing must remain governed HOLD")
    if pricing.get("checkout_enabled") is not False or pricing.get("stripe_objects_created") is not False:
        errors.append("pricing catalog cannot enable checkout or claim Stripe objects")
    if pricing.get("top_up_candidates") != [] or pricing.get("controlled_candidate_reference") != "PRIVATE_CONTROL_PLANE_REFERENCE":
        errors.append("public pricing manifest must remain qualitative and omit controlled tiers")

    if framework.get("candidate_type") != "capability_pack":
        errors.append("ThriveAlumni candidate must be a capability pack, not a ninth framework")
    if framework.get("framework_count_delta") != 0:
        errors.append("capability suite must not change the eight-framework factory count")
    consequential = (
        "activation_allowed",
        "public_claim_allowed",
        "commercialization_allowed",
        "checkout_enabled",
        "can_vote",
        "delete_allowed",
    )
    if any(type(framework.get(key)) is not bool or framework.get(key) is not False for key in consequential):
        errors.append("candidate consequential controls must be explicit false JSON booleans")
    if framework.get("authority_ceiling") not in {"D0", "D1", "D2"}:
        errors.append("candidate authority must remain within D0-D2")

    expected_refs = {
        "canonical_registry_ref": REGISTRY.relative_to(ROOT).as_posix(),
        "committee_registry_ref": COMMITTEES.relative_to(ROOT).as_posix(),
        "schedule_registry_ref": SCHEDULES.relative_to(ROOT).as_posix(),
        "schema_ref": SCHEMA.relative_to(ROOT).as_posix(),
    }
    for key, expected in expected_refs.items():
        if master.get(key) != expected:
            errors.append(f"master manifest {key} must resolve to {expected}")
    if master.get("parent_agent_id") not in baseline_agents:
        errors.append("master-suite parent must resolve in the canonical baseline")
    if master.get("parent_certifier_id") != "ct.relay.agent-d" or master.get("parent_certifier_id") not in baseline_agents:
        errors.append("Agent D must remain the canonical parent certifier")
    if master.get("framework_count_delta") != 0 or master.get("sovereign_voter_count_delta") != 0:
        errors.append("master suite cannot change framework or sovereign-voter counts")

    if linkage.get("state") != "CANDIDATE_HOLD":
        errors.append("linkage manifest must remain candidate HOLD")
    for edge in linkage.get("edges", []):
        edge_id = edge.get("edge_id", "<missing>")
        if edge.get("originator_id") not in set(ids):
            errors.append(f"{edge_id}: linkage originator is not a registered suite agent")
        if edge.get("status") == "CANDIDATE":
            if edge.get("approval_receipt_ref") is not None or edge.get("approval_receipt_file_sha256") is not None:
                errors.append(f"{edge_id}: candidate linkage must not carry an approval receipt")
        for key in ("source", "target"):
            relative = edge.get(key)
            if not isinstance(relative, str) or Path(relative).suffix.lower() not in {".md", ".mdx"}:
                errors.append(f"{edge_id}: {key} must be a Markdown document path")
                continue
            resolved = ROOT / relative
            if require_canonical_baseline and not resolved.is_file():
                errors.append(f"{edge_id}: canonical linkage {key} does not exist: {relative}")
            elif not resolved.is_file():
                warnings.append(f"portable package does not contain canonical linkage {key}: {relative}")

    if errors:
        raise SuiteValidationError("\n".join(errors))

    return {
        "status": "PASS_CONTROLLED_TEST_PENDING_INDEPENDENT_VERIFICATION",
        "scope": "manifest_schema_reference_and_invariant_validation_only",
        "release_state": registry.get("release_state"),
        "agent_count": len(agents),
        "committee_surface_count": len(committee_rows),
        "schedule_count": len(schedule_rows),
        "mode_counts": modes,
        "master_skill_count": len(master_skills),
        "per_agent_skill_candidate_count": len(agents),
        "manifest_sha256": canonical_sha256(registry),
        "schema_sha256": canonical_sha256(schema),
        "canonical_baseline_state": baseline_state,
        "warnings": warnings,
        "not_proven": [
            "runtime execution",
            "human governance approval",
            "dual-custody restore",
            "MCP publication",
            "commercial activation",
            "detached v2 corpus validity",
            "first scheduled subroute heartbeat",
        ],
    }


def inventory() -> dict[str, Any]:
    registry = load_json(REGISTRY)
    return {
        "suite_id": registry["suite_id"],
        "release_state": registry["release_state"],
        "agents": [
            {
                "agent_id": row["agent_id"],
                "name": row["canonical_name"],
                "family": row["family"],
                "mode": row["mode"],
                "autonomy": row["autonomy_class"],
                "authority": row["authority_ceiling"],
            }
            for row in registry["agents"]
        ],
    }


def skill_candidates() -> dict[str, Any]:
    registry = load_json(REGISTRY)
    return {
        "catalog_state": "CANDIDATE_HOLD",
        "packages": [
            {
                "skill_id": f"ct.skill.agent.{row['agent_id'].split('.')[-1]}.v1",
                "agent_id": row["agent_id"],
                "version": "1.0.0",
                "mcp_state": "DISABLED",
                "commercial_state": "HOLD",
                "price_credits": None,
                "manifest_sha256": canonical_sha256(row),
            }
            for row in registry["agents"]
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--validate", action="store_true")
    group.add_argument("--inventory", action="store_true")
    group.add_argument("--skill-candidates", action="store_true")
    parser.add_argument(
        "--require-canonical-baseline",
        action="store_true",
        help="fail unless canonical repository agent manifests and linkage targets are present",
    )
    args = parser.parse_args()
    try:
        if args.validate:
            value = validate(require_canonical_baseline=args.require_canonical_baseline)
        elif args.inventory:
            value = inventory()
        else:
            value = skill_candidates()
    except (OSError, json.JSONDecodeError, SuiteValidationError) as exc:
        print(json.dumps({"status": "FAIL", "error": str(exc)}, indent=2), file=sys.stderr)
        return 1
    print(json.dumps(value, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
