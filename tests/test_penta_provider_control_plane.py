import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "runtime" / "penta-provider-control-plane" / "penta_control_plane.py"
SPEC = importlib.util.spec_from_file_location("penta_provider_control_plane_tests", MODULE)
pcp = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = pcp
SPEC.loader.exec_module(pcp)


def registry_payload():
    return {
        "schema": pcp.SCHEMA_VERSION,
        "version": "test",
        "priority": "software",
        "policy": {
            "fail_closed": True,
            "required_provider_certifications": ["resend"],
        },
        "providers": [
            {
                "provider_id": "resend",
                "provider_class": "vendor",
                "priority": "software",
                "auth_model": "none",
                "credential_sets": [],
                "certification_probe": {
                    "operation": "domain_read",
                    "method": "GET",
                    "url_template": "https://example.invalid/domains",
                    "required_env": [],
                    "auth": {"type": "none"},
                    "success_http": [200],
                },
                "adapter": {
                    "adapter_id": "ct.adapter.resend.v1",
                    "version": "test",
                    "operations": [
                        {
                            "operation": "domain_read",
                            "side_effect": False,
                            "authority_class": "D0",
                            "requires_readback": True,
                        },
                        {
                            "operation": "email_send",
                            "side_effect": True,
                            "authority_class": "D1",
                            "requires_readback": True,
                        },
                    ],
                },
            }
        ],
    }


class FakeResponse:
    def __init__(self, payload, status=200):
        self.status = status
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def read(self, _limit):
        return json.dumps(self.payload).encode("utf-8")


class PentaProviderControlPlaneTests(unittest.TestCase):
    RUN_ID = "123456789"
    RECIPIENT = "owner@example.com"
    SENDER = "CrownThrive PentaMail <system@example.com>"
    SUBJECT = "[PentaMail Production Validation 123456789] Penta Mesh Report"
    BODY = "Evidence-backed Penta provider validation report."

    @staticmethod
    def content_hash(value):
        return pcp.sha256_bytes(pcp.canonical_json(value).encode("utf-8"))

    def provider_locator(self, message_id="provider-message-123", **overrides):
        timestamp = pcp.now()
        locator = {
            "provider": "resend",
            "operation": "email_send",
            "provider_message_id": message_id,
            "workflow_run_id": self.RUN_ID,
            "correlation_id": "pentamail-live-" + self.RUN_ID,
            "idempotency_key": "pentamail-live-" + self.RUN_ID,
            "authority_ref": "founder-directive-test-pentamail-certification",
            "requested_at": timestamp,
            "recorded_at": timestamp,
            "recipient_sha256": self.content_hash(self.RECIPIENT),
            "sender_sha256": self.content_hash(self.SENDER),
            "subject_sha256": self.content_hash(self.SUBJECT),
            "body_sha256": self.content_hash(self.BODY),
            "correlation_tag_sha256": self.content_hash("pentamail-live-" + self.RUN_ID),
            "idempotency_tag_sha256": self.content_hash("pentamail-live-" + self.RUN_ID),
            "body_tag_sha256": self.content_hash(self.BODY),
        }
        locator.update(overrides)
        return locator

    def provider_payload(self, message_id="provider-message-123", **overrides):
        payload = {
            "id": message_id,
            "last_event": "delivered",
            "created_at": pcp.now(),
            "to": [self.RECIPIENT],
            "from": self.SENDER,
            "subject": self.SUBJECT,
            "text": self.BODY,
            "tags": [
                {
                    "name": pcp.PENTAMAIL_CORRELATION_TAG,
                    "value": self.content_hash("pentamail-live-" + self.RUN_ID),
                },
                {
                    "name": pcp.PENTAMAIL_IDEMPOTENCY_TAG,
                    "value": self.content_hash("pentamail-live-" + self.RUN_ID),
                },
                {
                    "name": pcp.PENTAMAIL_BODY_TAG,
                    "value": self.content_hash(self.BODY),
                },
            ],
        }
        payload.update(overrides)
        return payload

    def make_registry(self, directory):
        path = Path(directory) / "providers.json"
        path.write_text(json.dumps(registry_payload()), encoding="utf-8")
        return pcp.Registry(path)

    @staticmethod
    def trusted_probe(*_args, **_kwargs):
        return {
            "operation": "domain_read",
            "result": "PASS",
            "readback": True,
            "evidence_source": "penta_certify_live_probe",
            "http_status": 200,
            "observed_at": pcp.now(),
        }

    def prepare(self, registry, state):
        pcp.PentaCredentials(registry, state).bind("resend")
        pcp.PentaBuild(registry, state).build("resend")

    def test_run_all_fails_when_required_provider_is_held(self):
        with tempfile.TemporaryDirectory() as td, mock.patch.dict(
            os.environ,
            {"PENTA_DISABLE_NETWORK_PROBES": "1", "GITHUB_RUN_ID": self.RUN_ID},
            clear=True,
        ):
            root = Path(td)
            registry = self.make_registry(root)
            state = root / "state"
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                exit_code = pcp.run_all(registry, state)
            matrix = json.loads((state / "readiness-matrix.json").read_text(encoding="utf-8"))
            self.assertEqual(exit_code, 3)
            self.assertFalse(matrix["required_gate"]["passed"])
            self.assertEqual(matrix["required_gate"]["holds"][0]["provider_id"], "resend")

    def test_run_all_passes_only_with_current_required_probe_certification(self):
        with tempfile.TemporaryDirectory() as td, mock.patch.dict(os.environ, {}, clear=True):
            root = Path(td)
            registry = self.make_registry(root)
            state = root / "state"
            with mock.patch.object(pcp.PentaCertify, "_probe", self.trusted_probe):
                with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                    exit_code = pcp.run_all(registry, state)
            matrix = json.loads((state / "readiness-matrix.json").read_text(encoding="utf-8"))
            self.assertEqual(exit_code, 0)
            self.assertTrue(matrix["required_gate"]["passed"])
            self.assertEqual(matrix["required_gate"]["holds"], [])

    def test_untrusted_live_evidence_dictionary_is_rejected(self):
        with tempfile.TemporaryDirectory() as td, mock.patch.dict(os.environ, {}, clear=True):
            root = Path(td)
            registry = self.make_registry(root)
            state = root / "state"
            self.prepare(registry, state)
            with self.assertRaisesRegex(ValueError, "untrusted live_evidence"):
                pcp.PentaCertify(registry, state).certify(
                    "resend",
                    live_evidence=[
                        {"operation": "email_send", "result": "PASS", "readback": True}
                    ],
                )

    def test_caller_flags_cannot_promote_provider_receipt_to_write_verified(self):
        with tempfile.TemporaryDirectory() as td, mock.patch.dict(
            os.environ,
            {"PENTA_DISABLE_NETWORK_PROBES": "1", "GITHUB_RUN_ID": self.RUN_ID},
            clear=True,
        ):
            root = Path(td)
            registry = self.make_registry(root)
            state = root / "state"
            self.prepare(registry, state)
            with mock.patch.object(pcp.PentaCertify, "_probe", self.trusted_probe):
                cert = pcp.PentaCertify(registry, state).certify(
                    "resend",
                    provider_receipts=[self.provider_locator(
                        "invented-message-id",
                        result="PASS",
                        readback=True,
                    )],
                )
            self.assertEqual(cert.state, "CERTIFIED")
            self.assertEqual(cert.certified_operations, ["domain_read"])
            self.assertEqual(cert.live_evidence[-1]["result"], "SKIP")

    def test_provider_owned_readback_can_verify_exact_write_operation(self):
        with tempfile.TemporaryDirectory() as td, mock.patch.dict(
            os.environ,
            {"RESEND_API_KEY": "test-only-key", "GITHUB_RUN_ID": self.RUN_ID},
            clear=True,
        ):
            root = Path(td)
            registry = self.make_registry(root)
            state = root / "state"
            self.prepare(registry, state)
            with mock.patch.object(pcp.PentaCertify, "_probe", self.trusted_probe), mock.patch.object(
                pcp,
                "open_no_redirect",
                return_value=FakeResponse(self.provider_payload()),
            ) as urlopen:
                cert = pcp.PentaCertify(registry, state).certify(
                    "resend",
                    provider_receipts=[self.provider_locator()],
                )
            self.assertEqual(cert.state, "WRITE_VERIFIED")
            self.assertEqual(cert.certified_operations, ["domain_read", "email_send"])
            request = urlopen.call_args.args[0]
            self.assertEqual(request.full_url, "https://api.resend.com/emails/provider-message-123")
            self.assertTrue(cert.live_evidence[-1]["content_binding_verified"])
            self.assertTrue(cert.live_evidence[-1]["body_binding_verified"])
            self.assertTrue(cert.live_evidence[-1]["correlation_binding_verified"])
            self.assertTrue(cert.live_evidence[-1]["idempotency_binding_verified"])
            self.assertTrue(cert.live_evidence[-1]["freshness_verified"])

    def test_failed_or_unbound_message_cannot_verify_write_operation(self):
        cases = (
            ("bounced", self.provider_payload(last_event="bounced")),
            ("complained", self.provider_payload(last_event="complained")),
            ("failed", self.provider_payload(last_event="failed")),
            ("unknown", self.provider_payload(last_event="unknown")),
            ("recipient", self.provider_payload(to=["attacker@example.com"])),
            ("subject", self.provider_payload(subject="unrelated message")),
            ("body", self.provider_payload(text="substituted report body")),
            (
                "correlation-tag",
                self.provider_payload(
                    tags=[
                        {"name": pcp.PENTAMAIL_CORRELATION_TAG, "value": "0" * 64},
                        *self.provider_payload()["tags"][1:],
                    ]
                ),
            ),
            (
                "idempotency-tag",
                self.provider_payload(
                    tags=[
                        self.provider_payload()["tags"][0],
                        {"name": pcp.PENTAMAIL_IDEMPOTENCY_TAG, "value": "0" * 64},
                        self.provider_payload()["tags"][2],
                    ]
                ),
            ),
            ("missing-tags", self.provider_payload(tags=None)),
            (
                "wrong-provider-returned-headers",
                self.provider_payload(
                    headers={
                        pcp.PENTAMAIL_CORRELATION_HEADER: "wrong-correlation",
                        pcp.PENTAMAIL_IDEMPOTENCY_HEADER: "wrong-idempotency",
                    }
                ),
            ),
        )
        for label, payload in cases:
            with self.subTest(label=label), tempfile.TemporaryDirectory() as td, mock.patch.dict(
                os.environ,
                {"RESEND_API_KEY": "test-only-key", "GITHUB_RUN_ID": self.RUN_ID},
                clear=True,
            ):
                root = Path(td)
                registry = self.make_registry(root)
                state = root / "state"
                self.prepare(registry, state)
                with mock.patch.object(pcp.PentaCertify, "_probe", self.trusted_probe), mock.patch.object(
                    pcp,
                    "open_no_redirect",
                    return_value=FakeResponse(payload),
                ):
                    cert = pcp.PentaCertify(registry, state).certify(
                        "resend",
                        provider_receipts=[self.provider_locator()],
                    )
                self.assertEqual(cert.state, "CERTIFIED")
                self.assertNotIn("email_send", cert.certified_operations)
                self.assertEqual(cert.live_evidence[-1]["result"], "FAIL")

    def test_stale_message_cannot_verify_write_operation(self):
        old = (pcp.dt.datetime.now(pcp.UTC) - pcp.dt.timedelta(hours=2)).replace(
            microsecond=0
        ).isoformat().replace("+00:00", "Z")
        with tempfile.TemporaryDirectory() as td, mock.patch.dict(
            os.environ,
            {"RESEND_API_KEY": "test-only-key", "GITHUB_RUN_ID": self.RUN_ID},
            clear=True,
        ):
            root = Path(td)
            registry = self.make_registry(root)
            state = root / "state"
            self.prepare(registry, state)
            with mock.patch.object(pcp.PentaCertify, "_probe", self.trusted_probe), mock.patch.object(
                pcp,
                "open_no_redirect",
                return_value=FakeResponse(self.provider_payload(created_at=old)),
            ):
                cert = pcp.PentaCertify(registry, state).certify(
                    "resend",
                    provider_receipts=[self.provider_locator()],
                )
            self.assertEqual(cert.state, "CERTIFIED")
            self.assertIn("provider_message_not_fresh", cert.live_evidence[-1]["reason"])

    def test_supabase_probe_credential_requires_exact_project_origin_and_path(self):
        provider = {
            "certification_probe": {
                "operation": "health_read",
                "method": "GET",
                "url_template": "{SUPABASE_URL}/rest/v1/",
                "required_env": ["SUPABASE_URL"],
                "auth": {"type": "supabase", "env": "SUPABASE_ANON_KEY"},
                "success_http": [200],
            }
        }
        with tempfile.TemporaryDirectory() as td, mock.patch.dict(
            os.environ,
            {
                "SUPABASE_URL": "https://attacker.invalid",
                "SUPABASE_ANON_KEY": "must-not-be-materialized",
            },
            clear=True,
        ):
            registry = self.make_registry(Path(td))
            certify = pcp.PentaCertify(registry, Path(td) / "state")
            with mock.patch.object(
                pcp.PentaCertify,
                "_auth_headers",
                return_value={"Authorization": "must-not-be-materialized"},
            ) as auth_headers, mock.patch.object(pcp, "open_no_redirect") as opener:
                evidence = certify._probe("supabase", provider)
            self.assertEqual(evidence["result"], "FAIL")
            self.assertIn("outside the approved project origin/path", evidence["reason"])
            auth_headers.assert_not_called()
            opener.assert_not_called()

        with tempfile.TemporaryDirectory() as td, mock.patch.dict(
            os.environ,
            {
                "SUPABASE_URL": pcp.SUPABASE_ALLOWED_ORIGIN,
                "SUPABASE_ANON_KEY": "test-anon-read-key",
            },
            clear=True,
        ):
            registry = self.make_registry(Path(td))
            certify = pcp.PentaCertify(registry, Path(td) / "state")
            with mock.patch.object(
                pcp,
                "open_no_redirect",
                return_value=FakeResponse({}, status=200),
            ) as opener:
                evidence = certify._probe("supabase", provider)
            self.assertEqual(evidence["result"], "PASS")
            request = opener.call_args.args[0]
            self.assertEqual(
                request.full_url,
                pcp.SUPABASE_ALLOWED_ORIGIN + pcp.SUPABASE_PROBE_PATH,
            )
            self.assertEqual(request.get_header("Apikey"), "test-anon-read-key")

    def test_provider_redirects_are_rejected_without_following_location(self):
        handler = pcp.NoRedirectHandler()
        request = pcp.urllib.request.Request(
            "https://api.resend.com/domains",
            headers={"Authorization": "Bearer test-only-key"},
        )
        redirected = handler.redirect_request(
            request,
            None,
            302,
            "Found",
            {"Location": "https://attacker.invalid/capture"},
            "https://attacker.invalid/capture",
        )
        self.assertIsNone(redirected)

        redirect_error = pcp.urllib.error.HTTPError(
            request.full_url,
            302,
            "Found",
            {"Location": "https://attacker.invalid/capture"},
            io.BytesIO(b"redirect"),
        )
        provider = registry_payload()["providers"][0]
        with tempfile.TemporaryDirectory() as td, mock.patch.dict(
            os.environ,
            {"RESEND_API_KEY": "test-only-key"},
            clear=True,
        ):
            registry = self.make_registry(Path(td))
            certify = pcp.PentaCertify(registry, Path(td) / "state")
            with mock.patch.object(
                pcp, "open_no_redirect", side_effect=redirect_error
            ) as opener:
                evidence = certify._probe("resend", provider)
            self.assertEqual(evidence["result"], "FAIL")
            self.assertEqual(evidence["http_status"], 302)
            self.assertEqual(opener.call_count, 1)

    def test_workflow_does_not_mask_live_certification_failure(self):
        legacy_mail = (
            ROOT / ".github" / "workflows" / "penta-mail-live-certification.yml"
        ).read_text(encoding="utf-8")
        self.assertIn("BUILT_HOLD_AUTHORITY", legacy_mail)
        self.assertNotIn("RESEND_API_KEY", legacy_mail)
        self.assertNotIn("secrets.", legacy_mail)
        self.assertNotIn("workflow_run:", legacy_mail)
        self.assertNotIn("push:", legacy_mail)
        workflow = (ROOT / ".github" / "workflows" / "penta-provider-control-plane.yml").read_text(
            encoding="utf-8"
        )
        live_step = workflow.split("- name: Live certify ${{ matrix.provider }}", 1)[1].split(
            "- name: Record provider disposition", 1
        )[0]
        self.assertNotIn("continue-on-error", live_step)
        self.assertIn("or not gate['eligible']", live_step)
        self.assertIn("provider_receipts=[{", workflow)
        self.assertNotIn("live_evidence=receipt['live_evidence']", workflow)
        self.assertNotIn("pentamail_recipient", workflow)
        self.assertNotIn("contains(github.event.head_commit.message", workflow)
        self.assertNotIn("Founding Member execution directive 2026-08-26", workflow)
        self.assertIn("github.ref == 'refs/heads/main'", workflow)
        self.assertIn("environment: provider-readback", workflow)
        self.assertIn("environment: pentamail-production", workflow)
        provider_job = workflow.split("  provider-live-readback:", 1)[1].split(
            "  pentamail-live-certification:", 1
        )[0]
        self.assertIn("needs: penta-runtime-suite", provider_job)
        self.assertIn("vars.PENTA_PROVIDER_READBACK_ENABLED == 'true'", provider_job)
        provider_prefix, provider_live_step = provider_job.split(
            "      - name: Live certify ${{ matrix.provider }}", 1
        )
        self.assertNotIn("PENTA_PROVIDER_SECRET", provider_prefix)
        self.assertIn("PENTA_PROVIDER_SECRET", provider_live_step)
        pentamail_job = workflow.split("  pentamail-live-certification:", 1)[1]
        self.assertIn("# BUILT_HOLD_AUTHORITY", pentamail_job)
        self.assertRegex(pentamail_job, r"if: >-\n\s+false &&")
        pentamail_prefix, pentamail_steps = pentamail_job.split("    steps:", 1)
        self.assertNotIn("RESEND_API_KEY", pentamail_prefix)
        self.assertNotIn("PENTAMAIL_RECIPIENT", pentamail_prefix)
        self.assertIn("RESEND_API_KEY", pentamail_steps)
        self.assertIn("PENTAMAIL_RECIPIENT", pentamail_steps)
        self.assertIn("PENTAMAIL_AUTHORIZED_ACTORS", workflow)
        self.assertIn("PENTAMAIL_CERTIFICATION_RECIPIENT", workflow)
        self.assertIn("recipient_sha256", workflow)
        self.assertIn("authority_ref", workflow)
        matrix_match = re.search(r"provider: \[([^\]]+)\]", workflow)
        self.assertIsNotNone(matrix_match)
        workflow_providers = {
            item.strip() for item in matrix_match.group(1).split(",") if item.strip()
        }
        registry = json.loads(
            (ROOT / "runtime" / "penta-provider-control-plane" / "providers.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(
            workflow_providers,
            set(registry["policy"]["required_provider_certifications"]),
        )


if __name__ == "__main__":
    unittest.main()
