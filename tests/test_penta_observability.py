import json
import pathlib
import sys
import unittest

RUNTIME = pathlib.Path(__file__).resolve().parents[1] / "runtime"
sys.path.insert(0, str(RUNTIME))

from penta_observability import (  # noqa: E402
    MetricRegistry, PentaError, PentaLogger, REDACTED, RetryPolicy, Severity,
    TraceContext, bind_trace, dead_letter_payload, guard_call, normalize_error,
    redact, self_test,
)


class PentaObservabilityTests(unittest.TestCase):
    def test_recursive_redaction(self):
        cleaned = redact({"api_key": "abc", "nested": {"password": "xyz"}, "safe": "Bearer supersecrettoken"})
        self.assertEqual(cleaned["api_key"], REDACTED)
        self.assertEqual(cleaned["nested"]["password"], REDACTED)
        self.assertNotIn("supersecrettoken", cleaned["safe"])

    def test_penta_error_safe_envelope(self):
        with bind_trace(TraceContext(correlation_id="corr-1")):
            err = PentaError("internal hunter2", code="PENTA_DATA_FAILURE", safe_message="Data operation failed.", retryable=True, status_code=503, context={"access_token": "top-secret", "record": 7})
            envelope = err.envelope()
        self.assertEqual(envelope["code"], "PENTA_DATA_FAILURE")
        self.assertEqual(envelope["message"], "Data operation failed.")
        self.assertTrue(envelope["retryable"])
        self.assertEqual(envelope["context"]["access_token"], REDACTED)
        self.assertEqual(envelope["trace"]["correlation_id"], "corr-1")
        self.assertNotIn("hunter2", json.dumps(envelope))

    def test_normalize_unknown(self):
        err = normalize_error(RuntimeError("boom"), context={"operation": "x"})
        self.assertIsInstance(err, PentaError)
        self.assertEqual(err.code, "PENTA_UNHANDLED_ERROR")
        self.assertEqual(err.context["operation"], "x")

    def test_structured_logger_trace_and_redaction(self):
        lines = []
        logger = PentaLogger(service="svc", penta_member="penta.logger", sink=lines.append)
        with bind_trace(TraceContext(correlation_id="corr-log")):
            logger.info("hello", event="test.event", context={"client_secret": "never", "ok": True})
        payload = json.loads(lines[0])
        self.assertEqual(payload["schema"], "ct.penta.log.v1")
        self.assertEqual(payload["trace"]["correlation_id"], "corr-log")
        self.assertEqual(payload["context"]["client_secret"], REDACTED)
        self.assertNotIn("never", lines[0])

    def test_logger_level_filter(self):
        lines = []
        logger = PentaLogger(service="svc", minimum_severity=Severity.WARNING, sink=lines.append)
        self.assertIsNone(logger.info("hidden"))
        logger.warning("visible")
        self.assertEqual(len(lines), 1)

    def test_guard_success_and_failure(self):
        lines, metrics = [], MetricRegistry()
        logger = PentaLogger(service="svc", sink=lines.append)
        self.assertEqual(guard_call(logger, "double", lambda x: x * 2, 4, metrics=metrics), 8)
        with self.assertRaises(PentaError):
            guard_call(logger, "explode", lambda: (_ for _ in ()).throw(ValueError("bad")), metrics=metrics)
        snapshot = metrics.snapshot()
        self.assertEqual(snapshot["counters"]["penta.operations.succeeded"], 1.0)
        self.assertEqual(snapshot["counters"]["penta.operations.failed"], 1.0)
        events = [json.loads(line)["event"] for line in lines]
        self.assertIn("operation.success", events)
        self.assertIn("operation.failure", events)

    def test_metric_timer(self):
        metrics = MetricRegistry()
        metrics.increment("requests")
        metrics.gauge("workers", 2)
        with metrics.timer("latency"):
            pass
        snapshot = metrics.snapshot()
        self.assertEqual(snapshot["counters"]["requests"], 1.0)
        self.assertEqual(snapshot["gauges"]["workers"], 2.0)
        self.assertEqual(snapshot["observations"]["latency"]["count"], 1)

    def test_retry_and_dead_letter(self):
        err = PentaError("timeout", code="PENTA_PROVIDER_TIMEOUT", retryable=True)
        policy = RetryPolicy(max_attempts=3, retryable_codes=frozenset({"PENTA_PROVIDER_TIMEOUT"}))
        self.assertTrue(policy.allows(err, 1))
        self.assertFalse(policy.allows(err, 3))
        with bind_trace(TraceContext(correlation_id="corr-dlq")):
            payload = dead_letter_payload("send", {"password": "nope"}, err)
        self.assertEqual(payload["payload"]["password"], REDACTED)
        self.assertEqual(payload["trace"]["correlation_id"], "corr-dlq")

    def test_self_test(self):
        result = self_test()
        self.assertEqual(result["status"], "pass")
        self.assertTrue(all(result["checks"].values()))


if __name__ == "__main__":
    unittest.main()
