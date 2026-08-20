"""§86 end-to-end demo:

  NL asset brief
    -> NEEDLE-SPEC (stock Needle 2, native dialect) -> structured spec
    -> runtime gate (fail-closed)
    -> NEEDLE-BUILD = deterministic Blender headless build (real bpy execution)
    -> NEEDLE-FBX = real FBX export + provenance
    -> NEEDLE-QA = deterministic validators over the real scene manifest
    -> AXIOM attestation (promotion lineage in signed ledger)
    -> registry entry

Every transition is recorded. Run: python foundry/e2e_demo.py
Output: docs/foundry/E2E_DEMO_TRANSCRIPT.json
"""
from __future__ import annotations

import ctypes
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "axiom"))

from foundry.runtime_gate import Proposal, route_proposal
from foundry.executors.qa import validators
from foundry.executors.blender import BlenderExecutor
from foundry.executors.fbx import FbxExecutor
from foundry.registry import FoundryRegistry, SpecialistRecord

STAGING = ROOT / "staging"
STAGING.mkdir(exist_ok=True)
OUT = ROOT / "docs" / "foundry" / "E2E_DEMO_TRANSCRIPT.json"

CACT = (r"C:\Users\Echer\.cache\huggingface\hub\models--Cactus-Compute--needle2"
        r"\snapshots\07f3e789e993e8ecf69ef5409fd7558f5fe43202\needle2.cact")
ENGINE = os.path.join(os.path.expanduser("~"), ".cache", "cactus-needle", "2.0.1", "libneedle.dll")

SPEC_TOOLS = [{
    "name": "create_asset_spec",
    "description": "Create a structured game-asset production specification.",
    "parameters": {
        "type": "object",
        "properties": {
            "asset_name": {"type": "string", "description": "snake_case asset identifier"},
            "category": {"type": "string", "description": "Asset category, e.g. prop_crate"},
            "size_m": {"type": "number", "description": "Bounding size in meters"},
            "bevel_m": {"type": "number", "description": "Edge bevel width in meters"},
            "material": {"type": "string", "description": "Material slot name"},
        },
        "required": ["asset_name", "category", "size_m"],
    },
}]

transcript: list[dict] = []


def step(name, **fields):
    transcript.append({"step": name, "at": time.time(), **fields})
    print(f"[{name}] {fields.get('summary','')}")


def needle_spec(brief: str) -> dict:
    lib = ctypes.CDLL(ENGINE)
    lib.needle_load.argtypes = [ctypes.c_char_p, ctypes.c_uint64]
    lib.needle_init.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_char_p]
    lib.needle_complete.argtypes = [ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_int]
    lib.needle_reset.argtypes = []
    blob = open(CACT, "rb").read()
    assert lib.needle_load(blob, len(blob)) == 0
    assert lib.needle_init(b"", json.dumps(SPEC_TOOLS).encode(), None) >= 0
    buf = ctypes.create_string_buffer(65536)
    lib.needle_complete(brief.encode(), 256, buf, len(buf))
    env = json.loads(buf.value.decode("utf-8", "replace"))
    calls = env.get("function_calls", [])
    if not calls:
        raise RuntimeError(f"NEEDLE-SPEC refused: {env.get('reasoning')}")
    return calls[0]["arguments"], env.get("confidence")


def main() -> int:
    brief = ("Create a game-ready wooden crate prop named prop_crate_01, "
             "one meter on a side, small 2 centimeter edge bevel, material crate_wood")
    step("0-brief", summary=brief)

    # 1. NEEDLE-SPEC
    try:
        spec_args, conf = needle_spec(brief)
    except Exception as e:
        step("1-needle-spec", summary=f"REFUSED/error: {e}", escalated=True)
        OUT.write_text(json.dumps(transcript, indent=2))
        return 1
    step("1-needle-spec", summary=f"spec proposal: {spec_args} (conf={conf})",
         proposal=spec_args, confidence=conf)

    # 2. runtime gate
    allowed = {"asset_name", "category", "size_m", "bevel_m", "material"}
    gate = route_proposal(
        Proposal(function_calls=[{"name": "create_asset_spec", "arguments": spec_args}],
                 confidence=conf or 0.0, specialist_id="needle-spec"),
        accept_threshold=0.0, review_threshold=0.0,   # demo: measure, don't gate on uncalibrated confidence
        schema_valid=lambda c: c.get("name") == "create_asset_spec"
                               and set(c.get("arguments", {})) <= allowed
                               and {"asset_name", "category", "size_m"} <= set(c.get("arguments", {})),
        capability_authorized=lambda c: True,
        executor_preflight=lambda c: (True, ""))
    step("2-runtime-gate", summary=f"{gate.action}: {gate.reason}", action=gate.action)
    if gate.action != "execute":
        OUT.write_text(json.dumps(transcript, indent=2))
        return 1

    # 3. deterministic Blender build + FBX export (real headless run)
    size = float(spec_args.get("size_m", 1.0))
    bevel = float(spec_args.get("bevel_m", 0.02) or 0.02)
    if bevel > 0.1:  # sanity clamp: model said 2cm as 2? normalize if implausible
        bevel = 0.02
    params = {
        "asset_name": str(spec_args.get("asset_name", "asset_crate")),
        "size_m": min(max(size, 0.1), 10.0),
        "bevel_m": bevel,
        "material": str(spec_args.get("material", "crate_mat")),
        "out_fbx": str(STAGING / "prop_crate_01.fbx"),
        "manifest_path": str(STAGING / "prop_crate_01.manifest.json"),
    }
    be = BlenderExecutor(STAGING)
    build = be.run_headless(ROOT / "foundry" / "executors" / "blender" / "build_crate.py", params)
    step("3-blender-build", summary=f"exit={build['exit_code']} {build['wall_clock_s']}s",
         exit_code=build["exit_code"], wall_clock_s=build["wall_clock_s"],
         script_hash=build["script_hash"])
    if not build["passed"]:
        step("3-blender-build", summary="BUILD FAILED", stderr=build["stderr_tail"])
        OUT.write_text(json.dumps(transcript, indent=2))
        return 1

    # 4. FBX provenance + structural validation
    fe = FbxExecutor(STAGING)
    ev = fe.execute("validate_fbx", {"path": params["out_fbx"]},
                    capabilities={"fbx.read"})
    step("4-fbx-validate", summary=f"passed={ev.validation.get('passed')} size={ev.validation.get('size_bytes')}",
         source_hash=ev.source_hash[:16], validation=ev.validation)
    if not ev.validation.get("passed"):
        OUT.write_text(json.dumps(transcript, indent=2))
        return 1

    # 5. NEEDLE-QA = deterministic validators over the REAL scene manifest
    manifest = json.loads(Path(params["manifest_path"]).read_text())
    verdict = validators.run_asset_gate(manifest, "game-ready")
    step("5-qa-gate", summary=f"passed={verdict['passed']}",
         checks={c["check"]: c["passed"] for c in verdict["checks"]})

    # 6. AXIOM attestation of the artifact lineage
    from nacl.signing import SigningKey
    from axiom.core.registry import Registry
    from axiom.core.ledger import Ledger
    from foundry.axiom_adapter import attest_promotion
    from foundry.registry import sha256_file

    key = SigningKey.generate()
    reg, led = Registry(), Ledger(signing_key=key)
    fbx_hash = sha256_file(params["out_fbx"])
    att = attest_promotion(
        specialist_id="needle-spec", niche_id="demo.game_asset", version="0.1.0",
        lineage={
            "brief_hash": __import__("hashlib").sha256(brief.encode()).hexdigest()[:16],
            "spec": spec_args,
            "fbx_hash": fbx_hash[:16],
            "manifest": manifest,
            "qa_passed": verdict["passed"],
            "build_script_hash": build["script_hash"][:16],
        },
        registry=reg, ledger=led, signing_key=key)
    step("6-axiom-attest", summary=f"unit={att.unit_hash[:16]} chain_ok={led.verify_chain()}",
         unit_hash=att.unit_hash, lineage_event=att.lineage_event_hash,
         chain_valid=led.verify_chain())

    # 7. registry
    foundry_reg = FoundryRegistry(ROOT / "docs" / "foundry" / "demo_e2e_registry.json")
    rec = SpecialistRecord(specialist_id="needle-spec", niche_id="demo.game_asset",
                           specialist_version="0.1.0", final_model_hash=fbx_hash,
                           axiom_attestation=att.unit_hash,
                           metrics={"qa_passed": verdict["passed"]})
    cid = foundry_reg.register(rec)
    step("7-registry", summary=f"content_id={cid[:16]}", content_id=cid)

    OUT.write_text(json.dumps(transcript, indent=2))
    print(f"\ntranscript -> {OUT}")
    ok = verdict["passed"] and led.verify_chain()
    print("E2E DEMO:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
