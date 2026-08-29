#!/usr/bin/env python3
"""Run the remediation worker with the workflow-scoped GitHub installation token.

The canonical PENTA_PM_GITHUB_TOKEN remains vaulted and unchanged. This wrapper
shadows it only inside this worker process with GITHUB_TOKEN so same-repository
PR/issue/content readback does not consume the shared founder PAT rate bucket.
"""
from __future__ import annotations

import os

from scripts import penta_remediation_worker_execute as worker


def main() -> int:
    native = os.environ.get("GITHUB_TOKEN") or ""
    if not native:
        raise SystemExit("workflow_scoped_github_token_required")
    os.environ["PENTA_PM_GITHUB_TOKEN"] = native
    return worker.main()


if __name__ == "__main__":
    raise SystemExit(main())
