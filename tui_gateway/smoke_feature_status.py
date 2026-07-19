"""Smoke test for tui_gateway.feature_status (Wave 1 PY-Gateway).

Calls the status functions directly and prints their payloads.  In this
workspace the M.U.S.E. agent/cron modules are NOT importable, so this
exercises the import-guard fallback path (available:false) — exactly what
must never raise.  Run from the muse-redesign root:

    python tui_gateway/smoke_feature_status.py
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tui_gateway import feature_status


def show(label, payload):
    print(f"\n=== {label} ===")
    print(json.dumps(payload, indent=2, sort_keys=True, default=str))


def main():
    events = []
    feature_status.set_event_emitter(lambda ev, sid, payload: events.append((ev, payload)))

    show("fusion.status", feature_status.fusion_status(cfg_file={}))
    show("fusion.status (moa in platform_toolsets.cli)",
         feature_status.fusion_status(cfg_file={"platform_toolsets": {"cli": ["moa", "web"]}}))

    ok = feature_status.apply_fusion_override(True)
    print(f"\napply_fusion_override(True) -> {ok} (False expected here: agent modules absent)")

    show("cron.list", feature_status.cron_list())
    show("memory.status", feature_status.memory_status())

    hooked = feature_status.install_fusion_progress_hook()
    print(f"\ninstall_fusion_progress_hook() -> {hooked} (False expected here: agent modules absent)")

    print(f"\nevents emitted: {events}")
    print("\nSMOKE OK — no exceptions raised on the guard path")


if __name__ == "__main__":
    main()
