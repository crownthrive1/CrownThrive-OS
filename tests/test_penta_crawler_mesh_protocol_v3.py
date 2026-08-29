from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BASE_MIGRATION = ROOT / "supabase/migrations/20260829032500_penta_crawler_mesh_protocol_v3.sql"
NORMALIZE_MIGRATION = ROOT / "supabase/migrations/20260829032600_penta_discovery_packet_normalization_v3.sql"
EDGE = ROOT / "supabase/functions/penta-crawler/index.ts"
COOKIE_SCHEMA = ROOT / "schemas/penta/penta-cookie-v1.schema.json"
PACKET_SCHEMA = ROOT / "schemas/penta/pentas-packet-v1.schema.json"
DOC = ROOT / "penta/crawler/README.md"


def text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


class PentaCrawlerMeshProtocolV3Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.base = text(BASE_MIGRATION)
        cls.normalize = text(NORMALIZE_MIGRATION)
        cls.edge = text(EDGE)
        cls.doc = text(DOC)
        cls.cookie_schema = json.loads(text(COOKIE_SCHEMA))
        cls.packet_schema = json.loads(text(PACKET_SCHEMA))

    def test_expected_source_artifacts_exist(self) -> None:
        for path in (BASE_MIGRATION, NORMALIZE_MIGRATION, EDGE, COOKIE_SCHEMA, PACKET_SCHEMA, DOC):
            self.assertTrue(path.is_file(), path)

    def test_protocol_registry_is_implemented_not_production_promoted(self) -> None:
        self.assertIn("('ct.penta.crawler.systemwide.v3','3.0.0','implemented'", self.base)
        self.assertNotIn("'penta.crawler','PentaCrawler'", self.base)
        self.assertIn("productionPromoted: false", self.edge)
        self.assertIn("Source state:** implemented candidate", self.doc)

    def test_cookie_is_server_side_not_user_tracking(self) -> None:
        description = self.cookie_schema["description"].lower()
        self.assertIn("server-side", description)
        self.assertIn("not a browser", description)
        self.assertIn("not a browser cookie", self.doc.lower())
        required = set(self.cookie_schema["required"])
        self.assertTrue({"system_key", "current_revision", "mutation_seq", "oracle_policy"} <= required)

    def test_cookie_history_and_concurrency_are_fail_closed(self) -> None:
        self.assertIn("penta_protocol_cookie_mutations_append_only_v1", self.base)
        self.assertIn("penta_cookie_tombstone_or_hold_required", self.base)
        self.assertIn("stale_cookie_revision", self.base)
        self.assertIn("idempotency_key_reused_for_different_mutation", self.base)
        self.assertIn("semantic_fingerprint", self.base)
        self.assertIn("expected_revision", self.base)

    def test_oracle_mutation_cannot_create_d3_authority(self) -> None:
        self.assertIn("d3_cookie_mutation_human_reserved", self.base)
        self.assertIn("oracle_adjudication_requires_founder", self.base)
        self.assertIn("oracle_adjudication_requires_professional", self.base)
        self.assertIn("oracle_adjudication_not_auto_resolve_eligible", self.base)
        self.assertIn("oracle_confidence_below_cookie_policy", self.base)
        self.assertIn("oracle_disagreement_above_cookie_policy", self.base)
        self.assertIn("oracle_quorum_below_cookie_policy", self.base)
        self.assertIn("count(distinct actor_id)", self.base.lower())
        self.assertIn("minimum_distinct_oracles", self.base)

    def test_packet_schema_binds_source_cookie_and_content_address(self) -> None:
        required = set(self.packet_schema["required"])
        self.assertTrue({
            "source_system_key",
            "source_cookie_id",
            "source_cookie_revision",
            "content_address",
            "payload_sha256",
            "max_hops",
            "ttl_seconds",
        } <= required)
        self.assertEqual(
            self.packet_schema["properties"]["content_address"]["pattern"],
            "^sha256:[0-9a-f]{64}$",
        )
        then = self.packet_schema["allOf"][0]["then"]["properties"]["authority_class"]
        self.assertEqual(then["const"], "human_reserved")

    def test_packets_are_bounded_immutable_and_receipted(self) -> None:
        self.assertIn("octet_length(payload::text) <= 65536", self.base)
        self.assertIn("hop_count <= max_hops", self.base)
        self.assertIn("pentas_packet_envelope_is_immutable", self.base)
        self.assertIn("pentas_packet_receipts_append_only_v1", self.base)
        self.assertIn("previous_receipt_sha256", self.base)
        self.assertIn("d3_packet_requires_human_reserved_authority_class", self.base)

    def test_direct_service_role_table_mutation_is_not_granted(self) -> None:
        tables = [
            "penta_protocol_registry_v1",
            "penta_protocol_cookies_v1",
            "penta_protocol_cookie_mutations_v1",
            "pentas_packets_v1",
            "pentas_packet_receipts_v1",
            "penta_discovery_cases_v1",
        ]
        for table in tables:
            self.assertIn(f"revoke all on public.{table} from service_role", self.base)
        self.assertIn("grant execute on function public.penta_crawler_roam_v1(integer) to service_role", self.base)

    def test_new_pentas_get_cookies_and_existing_pentas_backfill_incrementally(self) -> None:
        self.assertIn("penta_cookie_registry_autoinstall_trigger_v1", self.base)
        self.assertIn("penta_cookie_backfill_v1", self.base)
        self.assertIn("limit v_limit", self.base.lower())
        self.assertIn("order by coalesce(c.last_seen_at", self.base.lower())

    def test_crawler_faults_create_incident_flag_tags_and_discovery(self) -> None:
        self.assertIn("insert into public.penta_incidents_v1", self.base.lower())
        self.assertIn("'penta-crawler:broken'", self.base)
        self.assertIn("'penta:discovered'", self.base)
        self.assertIn("'penta:needs-help'", self.base)
        self.assertIn("'penta:crawler-observed'", self.base)
        self.assertIn("penta_discovery_raise_v1", self.base)

    def test_discovery_routes_census_vs_helper_without_replacing_either(self) -> None:
        self.assertIn("'penta.discovery','PentaDiscovery'", self.base)
        self.assertIn("'namespace_state','candidate'", self.base)
        self.assertIn("'penta_census_authority',true", self.base)
        self.assertIn("penta_help.raise_v1", self.base)
        self.assertIn("'penta.census'", self.base)
        self.assertIn("'penta.helper'", self.base)
        self.assertIn("D3_HUMAN_RESERVED", self.base)

    def test_malformed_discovery_payload_is_normalized_not_batch_poison(self) -> None:
        self.assertIn("v_signal_kind:='discovery_requested'", self.normalize)
        self.assertIn("v_severity:='WARN'", self.normalize)
        self.assertIn("jsonb_typeof(v_packet.payload->'evidence')='object'", self.normalize)
        self.assertIn("'malformed_payloads_fail_batch',false", self.normalize)

    def test_edge_runtime_has_systemwide_and_communications_modes(self) -> None:
        self.assertIn('service: "ct.penta.crawler.systemwide.v3"', self.edge)
        self.assertIn('communicationsService: "ct.penta.crawler.communications.v1"', self.edge)
        for action in ('"tick"', '"roam"', '"communications"', '"status"'):
            self.assertIn(action, self.edge)
        self.assertIn('rpc("penta_crawler_roam_v1"', self.edge)
        self.assertIn('rpc("penta_marketer_claim_research_v1"', self.edge)

    def test_edge_runtime_repairs_stale_pr_security_findings(self) -> None:
        self.assertIn("decodeEntitiesOnce", self.edge)
        self.assertIn("stripUnsafeMarkup", self.edge)
        self.assertIn("nonstandard_port_forbidden", self.edge)
        self.assertIn("resolved_private_target_forbidden", self.edge)
        self.assertIn("MAX_RESPONSE_BYTES = 1_000_000", self.edge)
        self.assertIn("MAX_REQUEST_BYTES = 64 * 1024", self.edge)
        self.assertIn("stack_exposed: false", self.edge)
        self.assertNotIn("error.stack", self.edge)
        self.assertNotIn("response.text()", self.edge)
        self.assertNotIn("String(error)", self.edge)
        self.assertNotIn("raw_secret_exposed: true", self.edge)
        self.assertNotIn("raw_body_archived: true", self.edge)

    def test_edge_runtime_does_not_claim_arbitrary_internal_roaming(self) -> None:
        self.assertIn("arbitrary_internal_crawling: false", self.edge)
        self.assertIn("provider_write: false", self.edge)
        self.assertIn("authority_created: false", self.edge)
        self.assertIn("d3_execution: false", self.edge)
        self.assertIn("registered CrownThrive estate", self.doc)
        self.assertIn("does not mean scan arbitrary networks", self.doc)

    def test_no_duplicate_clock_is_introduced(self) -> None:
        combined = (self.base + self.normalize + self.edge).lower()
        self.assertNotIn("create extension if not exists pg_cron", combined)
        self.assertNotIn("cron.schedule", combined)
        self.assertIn("creates no new clock", self.edge.lower())
        self.assertIn("zero new external scheduler slots", self.doc.lower())

    def test_decentralization_fields_exist_without_chain_activation_claim(self) -> None:
        for field in ("signature_ref", "signature_state", "origin_node_ref", "network_epoch", "content_address"):
            self.assertIn(field, self.packet_schema["properties"])
        self.assertIn("Decentralization-ready, not decentralization-by-claim", self.doc)
        self.assertIn("No token, public chain, decentralized settlement", self.doc)


if __name__ == "__main__":
    unittest.main()
