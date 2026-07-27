"""Seed ~150 niche YAML specs from DOMAIN_MAP + AOS-style domain slices."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable
import argparse

from hermes_cli.jarvis_prime.niches.schema import NicheSpec
from hermes_cli.jarvis_prime.niches.loader import write_niche, update_runtime_registry, niches_dir

# Domain → niche slices (super-niche specialists)
NICHE_SLICES: dict[str, list[tuple[str, str, list[str]]]] = {
    "architecture": [
        ("system.design", "system design tradeoffs", ["architecture", "design", "scalability"]),
        ("data.models", "data model design", ["schema", "erd", "data-model"]),
        ("api.contracts", "API contract design", ["openapi", "rest", "grpc"]),
        ("event.driven", "event-driven architecture", ["events", "pubsub", "queue"]),
        ("caching.layers", "caching strategy", ["cache", "redis", "cdn"]),
        ("multi.tenant", "multi-tenant isolation", ["tenant", "isolation", "saas"]),
        ("observability", "observability design", ["metrics", "tracing", "logs"]),
        ("failure.modes", "failure mode analysis", ["sre", "failover", "chaos"]),
    ],
    "security": [
        ("owasp.injection", "OWASP injection defenses", ["injection", "sqli", "xss"]),
        ("authn.oauth", "OAuth/OIDC authentication", ["oauth", "oidc", "auth"]),
        ("authz.rbac", "RBAC/ABAC authorization", ["rbac", "abac", "permissions"]),
        ("secrets.mgmt", "secrets management", ["secrets", "vault", "keystore"]),
        ("threat.model", "threat modeling", ["stride", "threat", "attack"]),
        ("crypto.tls", "TLS and crypto hygiene", ["tls", "crypto", "certificates"]),
        ("supply.chain", "supply-chain security", ["sbom", "deps", "provenance"]),
        ("pentest.triage", "pentest finding triage", ["pentest", "vuln", "cve"]),
    ],
    "qa": [
        ("flaky.pytest", "flaky pytest diagnosis", ["flaky", "pytest", "race"]),
        ("e2e.playwright", "Playwright e2e coverage", ["playwright", "e2e", "browser"]),
        ("contract.tests", "API contract tests", ["pact", "contract", "schema"]),
        ("perf.regression", "performance regression", ["benchmark", "latency", "perf"]),
        ("mutation.testing", "mutation testing strategy", ["mutation", "coverage"]),
        ("ci.gating", "CI quality gates", ["ci", "gate", "junit"]),
        ("fuzz.inputs", "fuzz and property tests", ["fuzz", "hypothesis", "property"]),
        ("snapshot.ui", "UI snapshot review", ["snapshot", "visual", "regression"]),
    ],
    "hazmat-command": [
        ("cfr49.placards", "49 CFR placarding", ["placard", "49cfr", "hazmat"]),
        ("shipping.papers", "shipping paper compliance", ["shipping", "bol", "manifest"]),
        ("erg.guide", "ERG emergency response", ["erg", "emergency", "spill"]),
        ("un.numbers", "UN number classification", ["un", "class", "division"]),
        ("tdg.canada", "TDG Canada rules", ["tdg", "canada", "transport"]),
        ("segregation", "load segregation rules", ["segregation", "incompatible"]),
        ("training.records", "hazmat training records", ["training", "certificate"]),
        ("incident.report", "hazmat incident reporting", ["incident", "dot", "report"]),
    ],
    "compliance": [
        ("gdpr.rights", "GDPR data subject rights", ["gdpr", "privacy", "dsar"]),
        ("hipaa.phi", "HIPAA PHI handling", ["hipaa", "phi", "healthcare"]),
        ("pci.dss", "PCI DSS controls", ["pci", "cardholder", "dss"]),
        ("soc2.controls", "SOC2 control mapping", ["soc2", "controls", "audit"]),
        ("retention", "data retention policy", ["retention", "deletion", "policy"]),
        ("consent.ux", "consent UX compliance", ["consent", "cookie", "opt-in"]),
        ("cross.border", "cross-border data transfer", ["transfer", "scc", "schrems"]),
        ("vendor.dpas", "vendor DPA review", ["dpa", "processor", "vendor"]),
    ],
    "research": [
        ("citation.check", "citation verification", ["citation", "source", "doi"]),
        ("lit.review", "literature review synthesis", ["papers", "review", "survey"]),
        ("claim.evidence", "claim-to-evidence mapping", ["claim", "evidence", "support"]),
        ("market.scan", "market scan research", ["market", "competitor", "landscape"]),
        ("stat.literacy", "statistics literacy checks", ["p-value", "sample", "bias"]),
        ("primary.sources", "primary source hunting", ["primary", "archive", "original"]),
        ("contradiction", "contradiction detection", ["conflict", "disagree", "retract"]),
        ("summarize.long", "long-doc summarization", ["summary", "digest", "brief"]),
    ],
    "product": [
        ("roadmap.prioritize", "roadmap prioritization", ["roadmap", "rice", "priority"]),
        ("user.stories", "user story writing", ["story", "acceptance", "persona"]),
        ("metrics.northstar", "north-star metrics", ["kpi", "north-star", "funnel"]),
        ("pricing.packaging", "pricing packaging", ["pricing", "tier", "packaging"]),
        ("launch.checklist", "launch checklist", ["launch", "ga", "beta"]),
        ("feedback.triage", "user feedback triage", ["feedback", "nps", "ticket"]),
        ("experiment.design", "A/B experiment design", ["ab-test", "experiment", "power"]),
        ("competitive.matrix", "competitive matrix", ["competitor", "matrix", "diff"]),
    ],
    "ux": [
        ("a11y.wcag", "WCAG accessibility", ["a11y", "wcag", "aria"]),
        ("onboarding.flow", "onboarding flow design", ["onboarding", "activation"]),
        ("empty.states", "empty-state UX", ["empty", "zero-state", "placeholder"]),
        ("error.messages", "error message craft", ["error", "copy", "recovery"]),
        ("forms.validation", "form validation UX", ["forms", "validation", "inline"]),
        ("mobile.touch", "mobile touch targets", ["mobile", "touch", "gesture"]),
        ("design.tokens", "design token systems", ["tokens", "theme", "figma"]),
        ("info.architecture", "information architecture", ["ia", "nav", "taxonomy"]),
    ],
    "release": [
        ("semver.bump", "semver and changelogs", ["semver", "changelog", "release"]),
        ("canary.deploy", "canary deploy strategy", ["canary", "rollout", "flag"]),
        ("rollback.plan", "rollback planning", ["rollback", "revert", "hotfix"]),
        ("feature.flags", "feature flag ops", ["flag", "toggle", "launchdarkly"]),
        ("store.submit", "app store submission", ["play", "appstore", "review"]),
        ("migration.db", "DB migration safety", ["migration", "alembic", "ddl"]),
        ("blue.green", "blue/green deploy", ["blue-green", "cutover"]),
        ("postmortem", "release postmortem", ["postmortem", "incident", "blameless"]),
    ],
    "hermes": [
        ("skill.author", "Hermes skill authoring", ["skill", "skill.md", "hermes"]),
        ("mcp.wiring", "MCP server wiring", ["mcp", "stdio", "tools"]),
        ("tool.registry", "tool registry hygiene", ["registry", "toolset"]),
        ("gateway.routes", "gateway route design", ["gateway", "route", "ws"]),
        ("memory.tree", "memory tree design", ["memory", "namespace", "graphrag"]),
        ("delegate.budget", "delegation budgets", ["delegate", "spawn", "budget"]),
        ("flywheel.loop", "flywheel improvement loop", ["flywheel", "learn", "promote"]),
        ("axiom.gates", "AXIOM gate profiles", ["axiom", "gate", "ledger"]),
    ],
    "memory": [
        ("recall.ranking", "recall ranking quality", ["recall", "rank", "relevance"]),
        ("dedupe.facts", "fact deduplication", ["dedupe", "merge", "entity"]),
        ("namespace.design", "memory namespaces", ["namespace", "scope", "tenant"]),
        ("forget.policy", "forget/TTL policy", ["ttl", "forget", "expiry"]),
        ("embed.chunk", "embedding chunk strategy", ["chunk", "embed", "rag"]),
        ("provenance", "memory provenance tags", ["provenance", "source", "uri"]),
        ("conflict.resolve", "memory conflict resolve", ["conflict", "override"]),
        ("session.summary", "session summarization", ["session", "summary", "compress"]),
    ],
    "business": [
        ("gtm.narrative", "GTM narrative", ["gtm", "positioning", "story"]),
        ("buyer.persona", "buyer persona research", ["persona", "icp", "buyer"]),
        ("pricing.model", "pricing model choice", ["pricing", "arpu", "margin"]),
        ("sales.enable", "sales enablement", ["sales", "deck", "objection"]),
        ("partner.ecosystem", "partner ecosystem", ["partner", "channel", "oem"]),
        ("unit.econ", "unit economics", ["ltv", "cac", "payback"]),
        ("forecast", "revenue forecast", ["forecast", "pipeline", "quota"]),
        ("procurement", "procurement readiness", ["procurement", "rfp", "security-q"]),
    ],
    "nourish": [
        ("meal.plan", "meal planning logic", ["meal", "plan", "macros"]),
        ("nutrient.claims", "nutrient claim accuracy", ["nutrient", "label", "claim"]),
        ("allergy.safety", "allergy safety checks", ["allergy", "allergen", "cross"]),
        ("habit.loop", "nutrition habit loops", ["habit", "streak", "nudge"]),
        ("recipe.scale", "recipe scaling", ["recipe", "portion", "scale"]),
        ("grocery.list", "grocery list generation", ["grocery", "pantry", "list"]),
        ("coach.tone", "coach tone of voice", ["coach", "tone", "motivation"]),
        ("lab.markers", "lab marker interpretation", ["lab", "biomarker", "range"]),
    ],
    "psychology": [
        ("motivation", "motivation design", ["motivation", "drive", "goal"]),
        ("friction.audit", "friction audit", ["friction", "drop-off", "hesitation"]),
        ("trust.signals", "trust signal design", ["trust", "social-proof"]),
        ("cognitive.load", "cognitive load reduction", ["cognitive", "load", "chunking"]),
        ("habit.formation", "habit formation", ["habit", "cue", "reward"]),
        ("persuasion.ethics", "ethical persuasion", ["persuasion", "dark-pattern"]),
        ("onboarding.psych", "onboarding psychology", ["activation", "aha"]),
        ("feedback.timing", "feedback timing", ["feedback", "timing", "reinforcement"]),
    ],
    "executive": [
        ("decision.memo", "executive decision memo", ["memo", "decision", "options"]),
        ("risk.board", "board risk briefing", ["board", "risk", "brief"]),
        ("okr.cascade", "OKR cascade", ["okr", "objective", "kr"]),
        ("stakeholder.map", "stakeholder mapping", ["stakeholder", "influence"]),
        ("crisis.comms", "crisis communications", ["crisis", "comms", "press"]),
        ("budget.tradeoff", "budget tradeoffs", ["budget", "capex", "opex"]),
        ("hire.plan", "hiring plan", ["hiring", "headcount", "role"]),
        ("governance", "governance cadence", ["governance", "cadence", "review"]),
    ],
    "claude-code": [
        ("impl.plan", "implementation planning", ["implement", "plan", "steps"]),
        ("refactor.safe", "safe refactor tactics", ["refactor", "extract", "rename"]),
        ("debug.bisect", "bisect debugging", ["bisect", "debug", "regress"]),
        ("types.first", "types-first coding", ["typescript", "types", "mypy"]),
        ("test.driven", "TDD workflow", ["tdd", "red-green", "test"]),
        ("pr.hygiene", "PR hygiene", ["pr", "diff", "review"]),
        ("perf.hotpath", "hot-path optimization", ["hotpath", "profile", "optimize"]),
        ("dead.code", "dead code removal", ["dead", "unused", "purge"]),
    ],
    "codex": [
        ("review.diff", "diff review rigor", ["review", "diff", "nit"]),
        ("fix.patch", "surgical fix patches", ["fix", "patch", "minimal"]),
        ("lint.debt", "lint debt triage", ["lint", "ruff", "eslint"]),
        ("types.gaps", "typing gap fills", ["typing", "any", "stub"]),
        ("test.gaps", "test coverage gaps", ["coverage", "gap", "assert"]),
        ("sec.review", "security-minded review", ["security", "review", "sanitize"]),
        ("api.break", "API break detection", ["breaking", "compat", "semver"]),
        ("docs.sync", "docs-code sync", ["docs", "stale", "sync"]),
    ],
}


def _iter_specs() -> Iterable[NicheSpec]:
    for domain, slices in NICHE_SLICES.items():
        for slug, focus, kws in slices:
            nid = f"{domain.replace('-', '_')}.{slug}"
            # schema allows underscores in segments
            system = (
                f"You are the AXIOM niche specialist `{nid}` in domain `{domain}`. "
                f"Focus: {focus}. Prefer Scout packets (SCOUT/*) over re-searching. "
                "Stay narrowly on-task and verify claims."
            )
            yield NicheSpec(
                id=nid,
                domain=domain,
                keywords=tuple(dict.fromkeys(kws + [domain, focus.split()[0]])),
                system=system,
                toolsets=("filesystem", "codebase", "web"),
                scout_queries=(
                    f"{focus}",
                    f"repo: {focus}",
                    f"docs: {focus}",
                ),
                model_lane="muse-local",
                max_iterations=25,
                description=focus,
            )


def seed_all(*, force: bool = False) -> tuple[int, int]:
    """Write niche YAMLs. Returns (written, skipped)."""
    written = skipped = 0
    root = niches_dir()
    for spec in _iter_specs():
        path = root / f"{spec.id}.yaml"
        if path.exists() and not force:
            skipped += 1
            continue
        write_niche(spec)
        update_runtime_registry(spec, forged=False)
        written += 1
    return written, skipped


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Seed niche AXIOM YAML specs")
    ap.add_argument("--force", action="store_true", help="Overwrite existing specs")
    args = ap.parse_args(argv)
    w, s = seed_all(force=args.force)
    print(f"seeded niches: written={w} skipped={s} dir={niches_dir()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
