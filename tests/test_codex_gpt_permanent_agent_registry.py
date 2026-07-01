from codex.gpt.permanent_agent_registry import (
    load_registry_entries,
    load_unique_roles,
    registry_summary,
)


def test_permanent_registry_loads_all_aos_agent_roles():
    entries = load_registry_entries()
    unique = load_unique_roles(entries)
    summary = registry_summary(entries)

    assert summary["unique_top_level_agents"] >= 233
    assert summary["unique_sub_agents"] >= 108
    assert summary["unique_roles_total"] >= 341

    slugs = {entry.slug for entry in unique}
    assert "aos-council-director" in slugs
    assert "codex-dispatch-governor" in slugs
    assert "claude-code-worker" in slugs
    assert "principal-code-reviewer" in slugs


def test_registry_entries_preserve_source_paths():
    entries = load_unique_roles()
    by_slug = {entry.slug: entry for entry in entries}

    council = by_slug["aos-council-director"]
    assert council.kind == "top_level_agent"
    assert council.source_registry.endswith("AOS_AGENT_REGISTRY_COMPLETE.md")

    worker = by_slug["codex-worker"]
    assert worker.kind == "sub_agent"
    assert worker.source_registry.endswith("AOS_SUBAGENT_REGISTRY_COMPLETE.md")
    assert worker.source_file.endswith("codex-worker.md")
