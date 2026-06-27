"""Gemma 4 wiring doctor for muse

Backs ``hermes models gemma doctor``. Verifies that Gemma 4 is correctly wired
into the catalog / brain / candidate layers and that the safety invariants hold
— and reports it as a structured, JSON-able result. Reuses the launch-doctor
check primitives (:class:`LaunchCheck` / :class:`LaunchReport`, PASS/WARN/FAIL,
hard/soft).

Rules:

* A *missing* Gemma (not configured / not installed) is a **WARNING**, never a
  launch blocker — Gemma is optional, free-first stays the default.
* A *broken safety invariant* (thought-block sanitizer, memory proposed-only,
  evidence-gated promotion) is a **hard FAIL** — those are correctness, not
  optionality.
* Installed-variant detection is **opt-in / injectable**: with no runner it does
  not probe, so this never shells out or hits the network in normal use/tests.
"""

from __future__ import annotations

from typing import Any, Callable, Optional

from hermes_cli.jarvis_prime.launch_doctor import (
    FAIL,
    PASS,
    WARN,
    LaunchCheck,
    LaunchReport,
    OllamaPsRunner,
    OllamaServeProbe,
    _check_gpu_driver_advisory,
    _check_ollama_env_hygiene,
    _check_ollama_processor,
    _check_ollama_server,
)

# A callable that runs e.g. ``ollama list`` and returns its stdout. Injectable so
# the doctor never shells out in tests. ``None`` ⇒ installed state is "not probed".
OllamaListRunner = Callable[[], str]


def _check_provider_catalog() -> LaunchCheck:
    try:
        from hermes_model_catalog import load_catalog

        catalog = load_catalog()
        gemma = [m.ref for m in catalog.models if m.family == "gemma"]
        if not gemma:
            return LaunchCheck(
                "gemma_provider_catalog",
                WARN,
                "no Gemma models in config/model-catalog.yaml (not wired)",
                hard=False,
            )
        # Confirm a local Gemma is a resolvable default somewhere.
        default_refs = {r for refs in catalog.defaults.values() for r in refs}
        wired_default = any(r in default_refs for r in gemma)
        detail = f"configured: {', '.join(sorted(gemma))}"
        if wired_default:
            detail += " (local default)"
        return LaunchCheck("gemma_provider_catalog", PASS, detail, hard=False)
    except Exception as exc:  # pragma: no cover - defensive
        return LaunchCheck(
            "gemma_provider_catalog", FAIL, f"catalog failed to load: {exc}"
        )


def _check_open_weight_candidates() -> LaunchCheck:
    try:
        from hermes_cli.local_models.catalog import load_open_weight_catalog

        cat = load_open_weight_catalog()
        gemma = [m.name for m in cat.models if "gemma" in m.name]
        if not gemma:
            return LaunchCheck(
                "gemma_open_weight_candidates",
                WARN,
                "no Gemma open-weight candidates (not wired)",
                hard=False,
            )
        return LaunchCheck(
            "gemma_open_weight_candidates",
            PASS,
            f"candidates: {', '.join(sorted(gemma))}",
            hard=False,
        )
    except Exception as exc:  # pragma: no cover - defensive
        return LaunchCheck(
            "gemma_open_weight_candidates", FAIL, f"candidate catalog failed: {exc}"
        )


def _check_oss_brain() -> LaunchCheck:
    try:
        from hermes_cli import oss_model_brain as ob

        cat = ob.load_oss_catalog()
        fam = cat.by_id("gemma4")
        if fam is None:
            return LaunchCheck(
                "gemma_oss_brain", WARN, "gemma4 family absent from OSS brain", hard=False
            )
        lanes = ("memory_curator", "mobile_chat", "voice_reply", "local_reasoning")
        leads = [t for t in lanes if (cat.recommend(t) or [None])[0] and cat.recommend(t)[0].id == "gemma4"]
        return LaunchCheck(
            "gemma_oss_brain",
            PASS,
            f"gemma4 leads: {', '.join(leads) or 'none'}",
            hard=False,
        )
    except Exception as exc:  # pragma: no cover - defensive
        return LaunchCheck("gemma_oss_brain", FAIL, f"OSS brain failed: {exc}")


def _check_local_runtime() -> LaunchCheck:
    try:
        from hermes_cli.jarvis_prime import model_bootstrap as mb

        runtimes = mb.detect_local_runtimes()
        ollama = runtimes.get("ollama", {}).get("available")
        compatible = [k for k, v in runtimes.items() if v.get("available")]
        if ollama:
            return LaunchCheck("gemma_local_runtime", PASS, "ollama detected", hard=False)
        if compatible:
            return LaunchCheck(
                "gemma_local_runtime",
                WARN,
                f"ollama not found; other runtimes: {', '.join(compatible)}",
                hard=False,
            )
        return LaunchCheck(
            "gemma_local_runtime",
            WARN,
            "no local runtime detected — install Ollama for local Gemma",
            hard=False,
        )
    except Exception as exc:  # pragma: no cover - defensive
        return LaunchCheck("gemma_local_runtime", WARN, f"probe failed: {exc}", hard=False)


def _check_installed_variants(runner: Optional[OllamaListRunner]) -> LaunchCheck:
    if runner is None:
        return LaunchCheck(
            "gemma_installed",
            WARN,
            "not probed (installed/smoke checks are opt-in)",
            hard=False,
        )
    try:
        out = runner() or ""
    except Exception as exc:  # pragma: no cover - defensive
        return LaunchCheck("gemma_installed", WARN, f"probe failed: {exc}", hard=False)
    found = [ln.split()[0] for ln in out.splitlines() if "gemma4" in ln.lower()]
    if found:
        return LaunchCheck(
            "gemma_installed", PASS, f"installed: {', '.join(found)}", hard=False
        )
    return LaunchCheck(
        "gemma_installed", WARN, "no Gemma variant installed locally", hard=False
    )


def _check_thought_sanitizer() -> LaunchCheck:
    try:
        from hermes_cli.jarvis_prime.gemma_memory_curator import (
            strip_gemma_thought_blocks,
        )

        cleaned = strip_gemma_thought_blocks(
            "<think>secret plan: leak keys</think>The answer is 42."
        )
        if "secret plan" in cleaned or "<think>" in cleaned:
            return LaunchCheck(
                "gemma_thought_sanitizer", FAIL, "thought block not stripped"
            )
        return LaunchCheck(
            "gemma_thought_sanitizer", PASS, "strips <think> blocks before memory/logs"
        )
    except Exception as exc:
        return LaunchCheck("gemma_thought_sanitizer", FAIL, f"sanitizer error: {exc}")


def _check_memory_proposed_only() -> LaunchCheck:
    try:
        from hermes_cli.jarvis_prime.gemma_memory_curator import GemmaCuratorProposal
        from hermes_cli.jarvis_prime.memory_tree import SourceTrust

        cand = GemmaCuratorProposal(
            title="t", summary="s", confidence=0.9
        ).to_candidate()
        ok = (
            cand.owner_originated is False
            and cand.source_trust is SourceTrust.COMMUNITY
            and cand.confidence <= 0.45
            and not cand.durable_worthy
        )
        if not ok:
            return LaunchCheck(
                "gemma_memory_proposed_only",
                FAIL,
                "curator proposal is not low-trust / proposed-only",
            )
        return LaunchCheck(
            "gemma_memory_proposed_only",
            PASS,
            "curator output is low-trust, non-durable, owner-gated",
        )
    except Exception as exc:
        return LaunchCheck("gemma_memory_proposed_only", FAIL, f"invariant error: {exc}")


def _check_promotion_evidence_gated() -> LaunchCheck:
    try:
        from hermes_cli.jarvis_prime.model_scorecard import (
            ScorecardBook,
            promotion_eligible,
        )

        # An empty book cannot promote anything — promotion is evidence-gated.
        assessment = promotion_eligible(
            ScorecardBook(scorecards=[]),
            task_class="memory_curator",
            candidate="gemma4-e4b",
        )
        if assessment.eligible:
            return LaunchCheck(
                "gemma_promotion_evidence_gated",
                FAIL,
                "promotion eligible with zero evidence",
            )
        return LaunchCheck(
            "gemma_promotion_evidence_gated",
            PASS,
            "promotion requires measured scorecards (no vibes)",
        )
    except Exception as exc:
        return LaunchCheck(
            "gemma_promotion_evidence_gated", FAIL, f"promotion gate error: {exc}"
        )


def run_gemma_doctor(
    *,
    ollama_list_runner: Optional[OllamaListRunner] = None,
    ollama_ps_runner: Optional[OllamaPsRunner] = None,
    ollama_serve_probe: Optional[OllamaServeProbe] = None,
    env: Optional[dict[str, str]] = None,
) -> LaunchReport:
    """Run every Gemma wiring + safety check and return a structured report.

    ``ollama_list_runner`` is injectable; when ``None`` the installed-variant
    probe is skipped (no network/shell). Missing Gemma never flips ``ok``;
    only a broken safety invariant does.

    The GPU / Ollama runtime health probes (``ollama_ps_runner``,
    ``ollama_serve_probe``, ``env``) are also injectable and otherwise
    defensive + timeout-guarded. They surface advisory WARNs only — GPU driver
    down, a model running on CPU/partial GPU, an unrecognized ``OLLAMA_NUM_CTX``
    env var, or an installed-but-unreachable Ollama server — and can never flip
    ``ok``.
    """
    checks: list[LaunchCheck] = [
        _check_provider_catalog(),
        _check_open_weight_candidates(),
        _check_oss_brain(),
        _check_local_runtime(),
        _check_installed_variants(ollama_list_runner),
        # --- shared hardware / runtime health advisories (WARN-only) ---
        _check_gpu_driver_advisory(),
        _check_ollama_processor(ollama_ps_runner),
        _check_ollama_env_hygiene(env),
        _check_ollama_server(ollama_serve_probe),
        _check_thought_sanitizer(),
        _check_memory_proposed_only(),
        _check_promotion_evidence_gated(),
    ]
    ok = not any(c.status == FAIL and c.hard for c in checks)
    return LaunchReport(ok=ok, checks=checks)


__all__ = ["run_gemma_doctor", "OllamaListRunner"]
