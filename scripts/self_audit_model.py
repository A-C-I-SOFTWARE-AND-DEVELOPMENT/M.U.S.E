#!/usr/bin/env python3
"""stdin (prompt) -> stdout (completion) via the self-audit model bridge.

Usable as ``HERMES_SELF_AUDIT_MODEL_CMD`` so the generic
``self-audit run --target live`` CLI can reach an OpenAI-compatible endpoint
configured by ``SELF_AUDIT_MODEL_BASE_URL`` / ``SELF_AUDIT_MODEL_NAME`` /
``SELF_AUDIT_MODEL_KEY``.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from hermes_cli.jarvis_prime.self_audit.model_bridge import main

if __name__ == "__main__":
    raise SystemExit(main())
