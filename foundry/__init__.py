"""Foundry package — M.U.S.E. Autonomous Specialist Foundry.

Deterministic scaffolding for the evidence-governed specialist pipeline:
  eligibility.py   — niche eligibility compiler (§11)
  registry.py      — content-addressed specialist artifact registry (§41)
  beliefs.py       — belief ledger with REFUTED reopen semantics (§50)
  teacher.py       — capability-aware teacher discovery over the real catalog (§14)
  runtime_gate.py  — fail-closed Tier-0 proposal gate (§47)
  dataset.py       — provenance/validation/dedupe/partition (§16–19)
  evaluation.py    — metrics + acceptance gates (§21–22)
  axiom_adapter.py — promotion attestation through the real AXIOM Verifier (§71–72)
  shadow.py        — shadow capture + failure clustering + retrain proposals (§45/§61)
  failure_demo.py  — §87 deliberate-failure proof (all classes contained)
  e2e_demo.py      — §86 end-to-end pipeline proof (NL→spec→Blender→FBX→QA→AXIOM)
  executors/       — narrow deterministic backends (qa, blender, fbx) (§36–39)
"""
