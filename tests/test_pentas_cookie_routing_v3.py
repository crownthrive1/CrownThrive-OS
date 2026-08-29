from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ROUTING = ROOT / "supabase/migrations/20260829032800_pentas_cookie_capability_routing_v3.sql"
FAILCLOSED = ROOT / "supabase/migrations/20260829032900_pentas_cookie_routing_failclosed_v3.sql"
DOC = ROOT / "penta/crawler/PENTAS-ROUTING.md"


def text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


class PentasCookieRoutingV3Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.routing = text(ROUTING)
        cls.failclosed = text(FAILCLOSED)
        cls.doc = text(DOC)

    def test_delivery_plane_is_durable_bounded_and_not_directly_writable(self) -> None:
        self.assertIn("create table if not exists public.pentas_packet_deliveries_v1", self.routing.lower())
        self.assertIn("unique(packet_id,target_system_key)", self.routing.replace(" ", ""))
        self.assertIn("max_attempts integer not null default 5", self.routing.lower())
        self.assertIn("before delete on public.pentas_packet_deliveries_v1", self.routing.lower())
        self.assertIn(
            "revoke all on public.pentas_packet_deliveries_v1 from public, anon, authenticated, service_role",
            self.routing.lower(),
        )

    def test_cookie_routing_descriptor_is_used_for_capabilities_and_lanes(self) -> None:
        self.assertIn("observed_state->'protocol_routing'", self.routing)
        self.assertIn("oracle_state->'routing'", self.routing)
        self.assertIn("v_oracle_routing->'capabilities'", self.routing)
        self.assertIn("v_observed_routing->'capabilities'", self.routing)
        self.assertIn("v_oracle_routing->'mesh_lanes'", self.routing)
        self.assertIn("v_observed_routing->'mesh_lanes'", self.routing)

    def test_core_pentas_have_message_capability_bootstrap_not_authority_grant(self) -> None:
        for capability in (
            "census.discovery",
            "help.remediate",
            "discovery.route",
            "remediation.pr",
            "remediation.assign",
            "self.diagnose",
            "crawler.roam",
        ):
            self.assertIn(capability, self.routing)
        self.assertIn("message-routing metadata, not an execution-rights registry", self.doc)

    def test_pentaself_capability_registry_is_ingested_without_hard_dependency(self) -> None:
        self.assertIn("to_regclass('penta_self.capability_registry_v1')", self.routing)
        self.assertIn("execute $q$", self.routing.lower())
        self.assertIn("where enabled", self.routing.lower())

    def test_capability_routing_is_capped_by_cookie_authority(self) -> None:
        self.assertIn("v_effective_rank:=least(v_declared_rank,v_cookie_rank)", self.failclosed.replace(" ", ""))
        self.assertIn("if v_declared_rank<0 or v_cookie_rank<0 or v_packet_rank<0 then return false", self.failclosed.lower())
        self.assertIn("else -1", self.failclosed.lower())
        self.assertNotIn("else 99", self.failclosed.lower())

    def test_broadcast_is_bounded(self) -> None:
        self.assertIn("p_target_ref='all-pentas'", self.failclosed)
        self.assertIn("v_packet_rank between 0 and 1", self.failclosed.lower())
        self.assertIn("broadcast_fanout_limit", self.routing)
        self.assertIn("v_broadcast_count>250", self.routing.replace(" ", ""))

    def test_claims_use_visibility_timeout_and_skip_locked(self) -> None:
        self.assertIn("pentas_claim_v1", self.routing)
        self.assertIn("lease_expires_at=now()+interval '5 minutes'", self.routing.replace(" ", ""))
        self.assertIn("for update of d skip locked", self.routing.lower())
        self.assertIn("lease_expired", self.routing)

    def test_ack_requires_exact_target_and_lease(self) -> None:
        self.assertIn("pentas_delivery_target_mismatch", self.failclosed)
        self.assertIn("pentas_delivery_lease_mismatch", self.failclosed)
        self.assertIn("pentas_delivery_lease_expired", self.failclosed)
        self.assertIn("delivery_ack", self.failclosed)

    def test_partial_fanout_failure_never_becomes_full_delivery(self) -> None:
        normalized = self.failclosed.replace(" ", "").lower()
        self.assertIn("whenv_dead>0andv_delivered>0then'held'", normalized)
        self.assertIn("whenv_delivered>0andv_dead=0then'delivered'", normalized)
        self.assertIn("'partial_failure_masked',false", self.failclosed)

    def test_crawler_roam_refreshes_cookie_routes_and_routes_pending_packets(self) -> None:
        self.assertIn("penta_cookie_refresh_routes_v1", self.routing)
        self.assertIn("interval '6 hours'", self.routing)
        self.assertIn("pentas_route_pending_v1", self.routing)
        self.assertIn("'mesh_route',v_mesh_route", self.routing.replace(" ", ""))

    def test_service_role_uses_bounded_rpcs(self) -> None:
        for fn in (
            "penta_cookie_refresh_routes_v1(text)",
            "penta_cookie_accepts_packet_v1(text,text,text,text,text)",
            "pentas_route_packet_v1(uuid,text)",
            "pentas_route_pending_v1(integer)",
            "pentas_claim_v1(text,integer)",
            "pentas_ack_v1(uuid,text,uuid,text,jsonb,text)",
        ):
            self.assertIn(f"grant execute on function public.{fn} to service_role", self.routing + self.failclosed)


if __name__ == "__main__":
    unittest.main()
