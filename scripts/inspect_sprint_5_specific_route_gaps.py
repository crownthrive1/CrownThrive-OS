#!/usr/bin/env python3
from build_help_center_convergent_ecosystem_crosswalk import build

result = build()
subs = sorted({
    row["legacy_subcategory"]
    for row in result["records"]
    if "specific_registry_route_missing_using_canonical_fallback" in row["flags"]
})
print("PASS_SPRINT_5_SPECIFIC_ROUTE_GAP_INSPECTION")
print(f"rows={result['summary']['specific_registry_fallback_rows']}")
print("subcategories=" + "|".join(subs))
