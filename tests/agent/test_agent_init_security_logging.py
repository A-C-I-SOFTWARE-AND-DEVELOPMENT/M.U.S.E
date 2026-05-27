from pathlib import Path


def test_ephemeral_prompt_banner_uses_length_only_primitive():
    """Keep CodeQL from tracking prompt text into the startup banner."""
    src = (
        Path(__file__).resolve().parent.parent.parent
        / "agent"
        / "agent_init.py"
    ).read_text(encoding="utf-8")
    block = src.split("# Show ephemeral system prompt status", 1)[1].split(
        "# Show prompt caching status",
        1,
    )[0]

    assert "safe_log_summary(agent.ephemeral_system_prompt)" not in block
    assert "len(agent.ephemeral_system_prompt)" in block
    assert "Ephemeral system prompt:" in block
