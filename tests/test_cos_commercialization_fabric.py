"""Aggregate COS commercialization regression suite."""

from tests.test_cos_commercialization_catalog import CatalogTests
from tests.test_cos_commercialization_adapters_mesh import AdapterTests, MeshRouterTests
from tests.test_cos_commercialization_wallet_package import WalletBridgeTests, PackageTests

__all__ = [
    "CatalogTests", "AdapterTests", "MeshRouterTests", "WalletBridgeTests", "PackageTests"
]
