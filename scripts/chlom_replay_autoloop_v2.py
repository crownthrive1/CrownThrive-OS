#!/usr/bin/env python3
"""In-run wrapper for the CHLOM replay autoloop.

GitHub suppresses recursive workflow events created by GITHUB_TOKEN. This wrapper
loads the v1 engine but suppresses only its workflow-dispatch API call. The calling
workflow reads the returned next validation branch/commit and invokes a fresh Python
process for the next cycle in the same bounded job. All Git/Supabase verification,
provider-custody checks, PR creation, and Penta gates remain unchanged.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

ENGINE = Path(__file__).with_name("chlom_replay_autoloop.py")
spec = importlib.util.spec_from_file_location("chlom_replay_autoloop_v1", ENGINE)
if spec is None or spec.loader is None:
    raise SystemExit("HOLD_AUTLOOP_ENGINE_IMPORT_SPEC")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

original_gh = module.gh


def gh_without_recursive_dispatch(path: str, *, method: str = "GET", body=None):
    if method == "POST" and path.startswith("actions/workflows/") and path.endswith("/dispatches"):
        return {"suppressed": True, "reason": "caller_continues_in_same_bounded_job"}
    return original_gh(path, method=method, body=body)


module.gh = gh_without_recursive_dispatch

try:
    module.main()
except RuntimeError as exc:
    module.hold("AUTLOOP_HTTP_OR_GIT_FAILURE", error=str(exc))
except (OSError, ValueError, module.json.JSONDecodeError) as exc:
    module.hold("AUTLOOP_RUNTIME_FAILURE", error=str(exc))
