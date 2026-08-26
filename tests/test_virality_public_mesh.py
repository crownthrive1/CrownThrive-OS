from __future__ import annotations

import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import sync_virality_public_mesh as sync  # noqa: E402
import validate_virality_public_mesh as validator  # noqa: E402


ORIGIN = "https://vm.crownthrive.com"
TIMESTAMP = "2026-08-26T22:22:23Z"


class PublicMeshFixture:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.resources: dict[str, dict[str, object]] = {}

    def add(
        self,
        url: str,
        filename: str,
        body: str,
        content_type: str,
        *,
        status: int = 200,
    ) -> None:
        (self.root / filename).write_text(body, encoding="utf-8")
        self.resources[url] = {
            "file": filename,
            "content_type": content_type,
            "status": status,
        }

    def error(self, url: str, code: str, message: str, *, retryable: bool = False) -> None:
        self.resources[url] = {"error": code, "message": message, "retryable": retryable}

    def finish(self) -> None:
        (self.root / "index.json").write_text(
            json.dumps({"resources": self.resources}, indent=2, sort_keys=True),
            encoding="utf-8",
        )


def build_fixture(root: Path) -> None:
    fixture = PublicMeshFixture(root)
    fixture.add(
        f"{ORIGIN}/robots.txt",
        "robots.txt",
        "User-agent: *\nDisallow: /api/\nDisallow: /checkout/\nDisallow: /private/\n",
        "text/plain",
    )
    fixture.add(
        f"{ORIGIN}/sitemap.xml",
        "sitemap.xml",
        """<?xml version="1.0" encoding="UTF-8"?>
<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <sitemap><loc>https://vm.crownthrive.com/pages.xml</loc></sitemap>
</sitemapindex>
""",
        "application/xml",
    )
    fixture.add(
        f"{ORIGIN}/pages.xml",
        "pages.xml",
        """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"
        xmlns:image="http://www.google.com/schemas/sitemap-image/1.1">
  <url>
    <loc>https://vm.crownthrive.com/</loc>
    <lastmod>2026-08-25</lastmod>
    <image:image>
      <image:loc>https://cdn.crownthrive.com/hero.webp?signature=redacted-at-ingest</image:loc>
      <image:title>Virality Music public hero</image:title>
    </image:image>
  </url>
  <url><loc>https://vm.crownthrive.com/universes/word-house</loc></url>
  <url><loc>https://vm.crownthrive.com/products/legacy-journal</loc></url>
  <url><loc>https://vm.crownthrive.com/missing</loc></url>
  <url><loc>https://vm.crownthrive.com/checkout/session?token=never-retain</loc></url>
  <url><loc>https://vm.crownthrive.com/library/protected.pdf</loc></url>
  <url><loc>https://vm.crownthrive.com/api/governed-catalog</loc></url>
  <url><loc>https://vm.crownthrive.com/.well-known/crownthrive-governed-catalog</loc></url>
</urlset>
""",
        "application/xml",
    )
    fixture.add(
        f"{ORIGIN}/",
        "home.html",
        """<!doctype html>
<html lang="en"><head>
  <title>Virality Music</title>
  <meta name="description" content="Public Virality Music catalog and universes">
  <meta property="og:image" content="/assets/social.jpg?width=1200">
  <link rel="canonical" href="https://vm.crownthrive.com/">
  <link rel="stylesheet" href="/assets/site.css?v=2">
  <link rel="icon" href="/favicon.png">
  <link rel="preload" as="font" href="/fonts/public.woff2" crossorigin>
  <script src="/assets/app.js?v=7"></script>
</head><body>
  <h1>Virality Music</h1>
  <img src="/images/hero.webp" alt="Virality Music worlds">
  <img srcset="/images/card.webp 1x, /images/card@2x.webp 2x">
  <video poster="/images/program-poster.jpg"><source src="/media/program.mp4" type="video/mp4"></video>
  <audio src="/media/theme.mp3"></audio>
  <a href="/universes/word-house">Word House</a>
  <a href="/library/protected.pdf?download=1">Protected edition reference</a>
  <a href="/checkout/session?token=do-not-retain">Checkout</a>
  <a href="https://soundcloud.com/crownthrive">SoundCloud</a>
</body></html>
""",
        "text/html",
    )
    fixture.add(
        f"{ORIGIN}/universes/word-house",
        "word-house.html",
        """<!doctype html><html lang="en"><head>
<title>Word House</title><meta name="description" content="The Word House universe">
<meta name="twitter:image" content="https://media.crownthrive.com/word-house.png?fit=cover">
</head><body><h1>Word House</h1><img src="/images/room.png" alt=""></body></html>""",
        "text/html",
    )
    fixture.add(
        f"{ORIGIN}/products/legacy-journal",
        "product.html",
        """<!doctype html><html lang="en"><head>
<title>Legacy Journal</title>
<meta property="og:type" content="product">
<meta property="og:title" content="Legacy Journal">
<meta property="og:url" content="https://vm.crownthrive.com/products/legacy-journal">
<meta property="product:price:amount" content="29.00">
<meta property="product:price:currency" content="USD">
<meta property="product:availability" content="https://schema.org/InStock">
<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "Product",
  "name": "Legacy Journal",
  "sku": "VM-LEGACY-001",
  "url": "/products/legacy-journal",
  "image": ["/images/legacy-cover.jpg", {"url": "/images/legacy-back.jpg"}],
  "contentUrl": "/downloads/legacy-master.pdf?signature=never-store",
  "thumbnailUrl": "/images/legacy-thumb.jpg",
  "additionalProperty": [{"@type": "PropertyValue", "name": "Credits label", "value": "PentaCredits observed label"}],
  "offers": {
    "@type": "Offer",
    "name": "Personal-use edition",
    "url": "/checkout/legacy-journal",
    "price": "29.00",
    "priceCurrency": "USD",
    "availability": "https://schema.org/InStock"
  }
}
</script></head><body><h1>Legacy Journal</h1></body></html>""",
        "text/html",
    )
    fixture.error(f"{ORIGIN}/missing", "http_error", "HTTP 503", retryable=True)
    fixture.finish()


def crawl_fixture(root: Path, *, timestamp: str = TIMESTAMP) -> tuple[dict[str, object], sync.FixtureFetcher]:
    fetcher = sync.FixtureFetcher(root, ORIGIN)
    inventory = sync.PublicMeshCrawler(
        f"{ORIGIN}/sitemap.xml",
        fetcher,
        source_timestamp=timestamp,
        max_routes=0,
        max_sitemaps=10,
        concurrency=4,
    ).crawl()
    return inventory, fetcher


class ViralityPublicMeshTests(unittest.TestCase):
    def test_fixture_crawl_is_deterministic_complete_and_public_safe(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            build_fixture(root)
            first, first_fetcher = crawl_fixture(root)
            second, second_fetcher = crawl_fixture(root)

            self.assertEqual(first, second)
            self.assertEqual(first["hashes"], sync.compute_inventory_hashes(first))
            self.assertEqual([], validator.validate_inventory(first))
            self.assertEqual(3, first["summary"]["route_count"])
            self.assertEqual(1, first["summary"]["failure_count"])

            requested_urls = {url for url, _purpose in first_fetcher.requests}
            self.assertNotIn(f"{ORIGIN}/library/protected.pdf", requested_urls)
            self.assertNotIn(f"{ORIGIN}/checkout/session", requested_urls)
            self.assertNotIn(f"{ORIGIN}/api/governed-catalog", requested_urls)
            self.assertNotIn(f"{ORIGIN}/.well-known/crownthrive-governed-catalog", requested_urls)
            self.assertFalse(any("/assets/" in url or "/images/" in url or "/media/" in url for url in requested_urls))
            self.assertEqual(set(first_fetcher.requests), set(second_fetcher.requests))

            exclusions = {(row["url"], row["reason"]) for row in first["excluded_routes"]}
            self.assertTrue(any(url.endswith("/checkout/session") for url, _reason in exclusions))
            self.assertTrue(any(url.endswith("/protected.pdf") for url, _reason in exclusions))
            self.assertTrue(any(url.endswith("/api/governed-catalog") for url, _reason in exclusions))
            self.assertTrue(any(".well-known" in url for url, _reason in exclusions))

            assets = {row["url"]: row for row in first["assets"]["references"]}
            self.assertIn("https://cdn.crownthrive.com/hero.webp", assets)
            self.assertTrue(assets["https://cdn.crownthrive.com/hero.webp"]["query_redacted"])
            self.assertIn(f"{ORIGIN}/downloads/legacy-master.pdf", assets)
            self.assertIn("document", assets[f"{ORIGIN}/downloads/legacy-master.pdf"]["asset_types"])
            self.assertIn(f"{ORIGIN}/media/theme.mp3", assets)
            self.assertIn("audio", assets[f"{ORIGIN}/media/theme.mp3"]["asset_types"])
            self.assertIn(f"{ORIGIN}/media/program.mp4", assets)
            self.assertIn("video", assets[f"{ORIGIN}/media/program.mp4"]["asset_types"])
            self.assertTrue(all(row["observation_status"].endswith("not_downloaded") for row in assets.values()))

            images = {row["url"]: row for row in first["assets"]["images"]}
            self.assertEqual([f"{ORIGIN}/"], images["https://cdn.crownthrive.com/hero.webp"]["referenced_by"])
            self.assertIn("Virality Music public hero", images["https://cdn.crownthrive.com/hero.webp"]["alt_texts"])

            self.assertIn("word-house", first["routes"][2]["classification"]["universes"])
            self.assertIn("soundcloud.com", {row["domain"] for row in first["related_domains"]})

    def test_commerce_is_observation_only_under_safe_hold(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            build_fixture(root)
            inventory, _fetcher = crawl_fixture(root)

            commerce = inventory["commerce"]
            self.assertEqual("SAFE_HOLD", commerce["economic_state"])
            self.assertEqual(0, commerce["checkout_requests_performed"])
            self.assertEqual(0, commerce["paid_redeemable"])
            self.assertFalse(commerce["redemption_enabled"])
            self.assertTrue(commerce["observations"])
            self.assertTrue(any(row.get("price") == "29.00" for row in commerce["observations"]))
            self.assertTrue(
                any(
                    "Credits label: PentaCredits observed label" in row.get("credits_labels", [])
                    for row in commerce["observations"]
                )
            )
            self.assertTrue(all(row["source_route"].startswith(ORIGIN) for row in commerce["observations"]))
            self.assertTrue(all(row["observed_at"] == TIMESTAMP for row in commerce["observations"]))

    def test_validator_rejects_paid_redemption_or_checkout_claim_under_safe_hold(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            build_fixture(root)
            inventory, _fetcher = crawl_fixture(root)
            unsafe = copy.deepcopy(inventory)
            unsafe["commerce"]["paid_redeemable"] = 1
            unsafe["commerce"]["redeemable_paid_count"] = 3
            unsafe["commerce"]["redemption_enabled"] = True
            unsafe["commerce"]["checkout_requests_performed"] = 1
            unsafe["hashes"] = sync.compute_inventory_hashes(unsafe)
            errors = validator.validate_inventory(unsafe)
            self.assertTrue(any("paid_redeemable must be zero" in error for error in errors))
            self.assertTrue(any("claims paid redeemable > 0" in error for error in errors))
            self.assertTrue(any("redemption cannot be enabled" in error for error in errors))
            self.assertTrue(any("never call checkout" in error for error in errors))

    def test_validator_detects_hash_tampering(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            build_fixture(root)
            inventory, _fetcher = crawl_fixture(root)
            inventory["routes"][0]["metadata"]["title"] = "Tampered"
            errors = validator.validate_inventory(inventory)
            self.assertTrue(any("top-level deterministic hashes drift" in error for error in errors))

    def test_route_index_contract_and_coverage(self) -> None:
        route_index_path = ROOT / "registry/virality-music/public-route-index-2026-08-26.json"
        route_index = json.loads(route_index_path.read_text(encoding="utf-8"))
        errors, urls = validator.validate_route_index(route_index, ORIGIN)
        self.assertEqual([], errors)
        self.assertEqual(1_825, len(urls))

        unique_urls = set(urls)
        synthetic = {
            "routes": [{"url": min(unique_urls)}],
            "failures": [],
            "excluded_routes": [{"url": url} for url in sorted(unique_urls - {min(unique_urls)})],
        }
        coverage = validator.route_index_coverage(synthetic, urls)
        self.assertTrue(coverage["coverage_complete"])
        self.assertEqual(1_825, coverage["accounted_route_count"])
        self.assertEqual(1_824, coverage["expected_unique_safe_url_count"])

        xml_routes, xml_assets, xml_metadata = sync.load_xml_estate_index(
            ROOT / "registry/virality-music/public-xml-estate-index-2026-08-26.json",
            ORIGIN,
        )
        self.assertEqual(2_389, len(xml_routes))
        self.assertEqual(2_010, sum(len(rows) for rows in xml_assets.values()))
        self.assertEqual(529, len({row["url"] for rows in xml_assets.values() for row in rows}))
        self.assertTrue(xml_metadata["parse_recovery_required"])

    def test_committed_portal_registries_reconcile(self) -> None:
        registry_root = ROOT / "registry/virality-music"
        universe = json.loads(
            (registry_root / "public-universe-directory-2026-08-26.json").read_text(encoding="utf-8")
        )
        self.assertEqual("ct.registry.vm.public-universe-directory.2026-08-26", universe["registry_id"])
        self.assertEqual("PUBLIC", universe["classification"])
        self.assertEqual(66, universe["summary"]["top_level_record_count"])
        self.assertEqual(65, universe["summary"]["direct_http_200_count"])
        self.assertEqual(1, universe["summary"]["redirect_count"])
        self.assertEqual(42, universe["summary"]["unique_public_art_url_count"])
        self.assertEqual(66, len(universe["records"]))
        self.assertEqual(42, len(universe["unique_public_art_references"]))
        self.assertEqual(list(range(1, 67)), [row["position"] for row in universe["records"]])
        self.assertEqual(66, len({row["projection_record_id"] for row in universe["records"]}))
        self.assertEqual(66, len({row["slug"] for row in universe["records"]}))
        self.assertTrue(all(row["public_route"]["observed_url"] == f"{ORIGIN}/{row['slug']}" for row in universe["records"]))
        self.assertTrue(all(row["public_art"]["url"] == ORIGIN + row["art_path"] for row in universe["records"]))
        self.assertTrue(all(validator.is_sha256(row["source_record_sha256"]) for row in universe["records"]))
        self.assertTrue(all(row["licensing"]["state"] == "INQUIRY_ONLY_WORK_LEVEL_CLEARANCE_REQUIRED" for row in universe["records"]))
        self.assertTrue(all(row["licensing"]["inquiry_route"] == f"{ORIGIN}/chlom-licensing" for row in universe["records"]))

        status_counts = {row["status"]: row["record_count"] for row in universe["summary"]["status_distribution"]}
        self.assertEqual(
            {
                "Album world or series": 13,
                "Developed universe": 23,
                "Flagship canon": 11,
                "Official flagship corridor": 2,
                "Official universe card": 10,
                "Production framework": 7,
            },
            status_counts,
        )

        public_web = json.loads((registry_root / "public-web-estate-v1.json").read_text(encoding="utf-8"))
        self.assertEqual(universe["registry_id"], public_web["universe_registry_snapshot"]["directory_registry_id"])
        self.assertNotIn("homepage_credit_listings", public_web)
        self.assertEqual(4, public_web["homepage_credit_listing_observation"]["observed_listing_count"])
        self.assertNotIn("items", public_web["homepage_credit_listing_observation"])
        mesh = json.loads((registry_root / "mesh-bindings-v1.json").read_text(encoding="utf-8"))
        self.assertIn(universe["registry_id"], {row["registry_id"] for row in mesh["source_registries"]})

        products = json.loads(
            (registry_root / "public-product-catalog-observation-2026-08-26.json").read_text(encoding="utf-8")
        )
        self.assertEqual(355, products["record_count"])
        self.assertEqual("SAFE_HOLD", products["commerce_authority"]["global_state"])
        self.assertEqual(0, products["commerce_authority"]["redeemable_paid_count"])
        for record in products["records"]:
            self.assertNotIn("download_limit", record)
            self.assertNotIn("link_ttl", record)
            self.assertNotIn("embedded_amount_raw", record)
            self.assertNotIn("embedded_amount_semantics", record)
            self.assertNotIn("configured_credit_price", record)
            projected = {key: value for key, value in record.items() if key != "public_projection_sha256"}
            self.assertEqual(sync.value_sha256(projected), record["public_projection_sha256"])

        masters = json.loads((registry_root / "source-master-public-metadata-v1.json").read_text(encoding="utf-8"))
        self.assertEqual(16, masters["inventory_summary"]["artifact_count"])
        self.assertEqual("HOLD", masters["inventory_summary"]["collision_disposition"])
        self.assertEqual(2, masters["inventory_summary"]["render_normalized_token_sequence_parity_pair_count"])
        self.assertNotIn("encrypted_pdf_count", masters["inventory_summary"])
        self.assertEqual(
            "ct.method.vm.source-parity.docx-render-pdf-pdftotext-token.v1",
            masters["parity_method"]["method_id"],
        )
        self.assertTrue(all(row["state"] == "RENDER_NORMALIZED_TOKEN_SEQUENCE_PARITY_VERIFIED" for row in masters["parity_pairs"]))
        collision_artifact_ids = {
            "ct.asset.vm.book.what-really-happened.v2-illustrated-collector.candidate-a.pdf",
            "ct.asset.vm.book.what-really-happened.v2-illustrated-collector.candidate-b.pdf",
        }
        collision_artifacts = [row for row in masters["artifacts"] if row["artifact_id"] in collision_artifact_ids]
        self.assertEqual(collision_artifact_ids, {row["artifact_id"] for row in collision_artifacts})
        for artifact in masters["artifacts"]:
            self.assertNotIn("encryption_state", artifact)
        for artifact in collision_artifacts:
            self.assertTrue({"byte_size", "page_count", "image_inventory"}.isdisjoint(artifact))
            self.assertEqual("WITHHELD_PENDING_COLLISION_RESOLUTION", artifact["differentiating_metadata_state"])
            self.assertEqual(["byte_size", "page_count", "image_inventory"], artifact["public_metadata_withheld_fields"])

    def test_validator_no_arg_mode_checks_committed_registries(self) -> None:
        self.assertEqual(0, validator.main([]))

    def test_cli_fixture_output_and_no_drift_report(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            build_fixture(root)
            output = root / "inventory.json"
            report = root / "drift.json"
            rc = sync.main(
                [
                    "--sitemap-url",
                    f"{ORIGIN}/sitemap.xml",
                    "--fixture-dir",
                    str(root),
                    "--output",
                    str(output),
                    "--source-timestamp",
                    TIMESTAMP,
                    "--max-routes",
                    "0",
                    "--concurrency",
                    "2",
                ]
            )
            self.assertEqual(0, rc)
            rc = validator.main(
                [
                    "--input",
                    str(output),
                    "--baseline",
                    str(output),
                    "--report",
                    str(report),
                    "--fail-on-drift",
                ]
            )
            self.assertEqual(0, rc)
            self.assertEqual("no_drift", json.loads(report.read_text(encoding="utf-8"))["status"])

    def test_unsafe_xml_declarations_are_rejected(self) -> None:
        with self.assertRaises(sync.CrawlError) as context:
            sync.parse_sitemap_document(
                b'<!DOCTYPE foo [<!ENTITY x "unsafe">]><urlset><url><loc>&x;</loc></url></urlset>',
                f"{ORIGIN}/sitemap.xml",
            )
        self.assertEqual("unsafe_xml_declaration", context.exception.code)

    def test_malformed_xml_recovers_only_bounded_public_fields(self) -> None:
        malformed = b"""<urlset xmlns:image="http://www.google.com/schemas/sitemap-image/1.1">
<url><loc>https://vm.crownthrive.com/books</loc><lastmod>2026-08-26</lastmod>
<image:image><image:loc>https://vm.crownthrive.com/cover.webp</image:loc>
<image:title>Books & unescaped value</image:title></image:image></url></urlset>"""
        entries, nested, assets, observation = sync.parse_sitemap_document(
            malformed,
            f"{ORIGIN}/sitemap.xml",
        )
        self.assertEqual([(f"{ORIGIN}/books", "2026-08-26")], entries)
        self.assertEqual([], nested)
        self.assertEqual(f"{ORIGIN}/cover.webp", assets[0]["url"])
        self.assertEqual("malformed_xml_recovered_bounded_fields", observation["state"])

    def test_semantic_hash_excludes_observation_time_but_snapshot_hash_preserves_it(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            build_fixture(root)
            first, _ = crawl_fixture(root, timestamp="2026-08-26T00:00:00Z")
            second, _ = crawl_fixture(root, timestamp="2026-08-27T00:00:00Z")
            self.assertEqual(first["hashes"]["semantic_sha256"], second["hashes"]["semantic_sha256"])
            self.assertNotEqual(first["hashes"]["snapshot_sha256"], second["hashes"]["snapshot_sha256"])


if __name__ == "__main__":
    unittest.main()
