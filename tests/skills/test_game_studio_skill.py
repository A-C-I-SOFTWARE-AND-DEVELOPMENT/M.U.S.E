"""
Smoke tests for the game-studio skill.

We can't run a full game build in CI (it needs an engine + GPU), so these tests
verify the skill's static contract:
  - SKILL.md frontmatter conforms to the hardline format
  - the agent roster files exist and parse
  - the helper scripts are valid Python
  - the routing-table roles all resolve to an agents/<role>.md file
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest
import yaml

SKILL_DIR = Path(__file__).resolve().parents[2] / "skills" / "creative" / "game-studio"

# The canonical roster. Each must have an agents/<role>.md and be referenced by
# the SKILL.md routing table.
ROSTER = [
    "studio-director",
    "game-designer",
    "level-designer",
    "gameplay-engineer",
    "graphics-tech-artist",
    "3d-asset-artist",
    "audio-designer",
    "qa-playtest",
    "build-release-engineer",
]


@pytest.fixture(scope="module")
def skill_src() -> str:
    return (SKILL_DIR / "SKILL.md").read_text()


@pytest.fixture(scope="module")
def frontmatter(skill_src) -> dict:
    m = re.search(r"^---\n(.*?)\n---", skill_src, re.DOTALL)
    assert m, "SKILL.md missing YAML frontmatter"
    return yaml.safe_load(m.group(1))


def test_skill_dir_exists() -> None:
    assert SKILL_DIR.is_dir(), f"missing skill dir: {SKILL_DIR}"


def test_skill_md_present() -> None:
    assert (SKILL_DIR / "SKILL.md").is_file()


def test_description_under_60_chars(frontmatter) -> None:
    desc = frontmatter["description"]
    assert len(desc) <= 60, f"description is {len(desc)} chars (hardline ≤60): {desc!r}"


def test_name_matches_dir(frontmatter) -> None:
    assert frontmatter["name"] == "game-studio"


def test_platforms_valid(frontmatter) -> None:
    plats = set(frontmatter["platforms"])
    assert plats >= {"linux", "macos", "windows"}


def test_author_credits_human_first(frontmatter) -> None:
    author = frontmatter["author"]
    # Hardline: human contributor first, "Hermes Agent" second.
    assert "Hermes Agent" in author
    assert author.split("+")[0].strip() and not author.strip().startswith("Hermes Agent")


def test_license_mit(frontmatter) -> None:
    assert frontmatter["license"] == "MIT"


def test_activation_phrases_present(frontmatter) -> None:
    phrases = frontmatter["metadata"]["hermes"]["activation_phrases"]
    assert isinstance(phrases, list) and len(phrases) >= 5
    joined = " | ".join(phrases).lower()
    assert "make a game" in joined
    assert "vertical slice" in joined


def test_roster_agent_files_exist() -> None:
    for role in ROSTER:
        f = SKILL_DIR / "agents" / f"{role}.md"
        assert f.is_file(), f"missing agent file for role {role!r}: {f}"


def test_roster_agents_have_frontmatter() -> None:
    for role in ROSTER:
        src = (SKILL_DIR / "agents" / f"{role}.md").read_text()
        m = re.search(r"^---\n(.*?)\n---", src, re.DOTALL)
        assert m, f"{role}.md missing frontmatter"
        fm = yaml.safe_load(m.group(1))
        assert fm["name"] == role
        assert "authority_level" in fm
        assert "activation_trigger" in fm


def test_routing_table_references_every_role(skill_src) -> None:
    for role in ROSTER:
        assert f"`{role}`" in skill_src, f"SKILL.md routing/body never references {role!r}"


def test_scripts_parse_as_python() -> None:
    for script in ("export_godot_slice.py", "verify_slice.py", "run_pipeline.py"):
        path = SKILL_DIR / "scripts" / script
        assert path.is_file(), f"missing script: {path}"
        ast.parse(path.read_text(), filename=str(path))


def test_workflow_present() -> None:
    wf = SKILL_DIR / "workflows" / "game-production-pipeline.md"
    assert wf.is_file()
    body = wf.read_text()
    # Owner gates must be called out in the pipeline.
    assert "owner" in body.lower()
    assert "MUSE_GAME_ALLOW_SPAWN" in (SKILL_DIR / "SKILL.md").read_text()
