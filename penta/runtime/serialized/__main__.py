from __future__ import annotations

import sys

from .core import main as core_main
from .workflow_projection import gate_main


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "git-gate":
        raise SystemExit(gate_main(sys.argv[2:]))
    raise SystemExit(core_main())
