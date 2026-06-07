"""Tests for the OpenAI GPT/Codex dual-entity router."""

from __future__ import annotations

import pytest

from agent.openai_entity_router import (
    DEFAULT_CHAT_MODEL,
    DEFAULT_CODEX_MODEL,
    classify_intent,
    is_codex_model,
    is_gpt_chat_model,
    resolve_entity_models,
    select_turn_model,
    split_model_ids,
)


@pytest.mark.parametrize(
    "model,expected",
    [
        ("gpt-5.3-codex", True),
        ("gpt-5.1-codex-max", True),
        ("gpt-5.3-codex-spark", True),
        ("gpt-5.5", False),
        ("gpt-5.4-mini", False),
        ("", False),
        (None, False),
    ],
)
def test_is_codex_model(model, expected):
    assert is_codex_model(model) is expected


@pytest.mark.parametrize(
    "model,expected",
    [
        ("gpt-5.5", True),
        ("gpt-5.4", True),
        ("gpt-5.3-codex", False),
        ("claude-opus-4-6", False),
        ("", False),
    ],
)
def test_is_gpt_chat_model(model, expected):
    assert is_gpt_chat_model(model) is expected


def test_split_model_ids_partitions_and_preserves_order():
    models = ["gpt-5.5", "gpt-5.3-codex", "gpt-5.4", "gpt-5.2-codex", "claude-x"]
    chat, codex = split_model_ids(models)
    assert chat == ["gpt-5.5", "gpt-5.4"]
    assert codex == ["gpt-5.3-codex", "gpt-5.2-codex"]


@pytest.mark.parametrize(
    "text",
    [
        "fix the bug in run_agent.py",
        "refactor this function",
        "write a python script to parse logs",
        "```\nprint('hi')\n```",
        "can you debug this stack trace",
        "open a PR and commit the change",
    ],
)
def test_classify_intent_code(text):
    assert classify_intent(text) == "code"


@pytest.mark.parametrize(
    "text",
    ["hi", "hey there", "thanks!", "who are you", "good morning"],
)
def test_classify_intent_chat(text):
    assert classify_intent(text) == "chat"


@pytest.mark.parametrize(
    "text",
    ["what's the weather like", "tell me a joke about cats", ""],
)
def test_classify_intent_ambiguous(text):
    assert classify_intent(text) == "ambiguous"


def test_select_turn_model_code_routes_to_codex():
    model, entity = select_turn_model(
        user_text="fix the failing test",
        chat_model="gpt-5.5",
        codex_model="gpt-5.3-codex",
    )
    assert (model, entity) == ("gpt-5.3-codex", "code")


def test_select_turn_model_chat_routes_to_gpt():
    model, entity = select_turn_model(
        user_text="hello",
        chat_model="gpt-5.5",
        codex_model="gpt-5.3-codex",
    )
    assert (model, entity) == ("gpt-5.5", "chat")


def test_select_turn_model_ambiguous_is_sticky():
    # Mid-coding, an ambiguous follow-up stays on Codex.
    model, entity = select_turn_model(
        user_text="now improve it a bit",
        chat_model="gpt-5.5",
        codex_model="gpt-5.3-codex",
        previous_entity="code",
    )
    assert entity == "code"
    # With no prior context, ambiguous defaults to chat.
    model, entity = select_turn_model(
        user_text="now improve it a bit",
        chat_model="gpt-5.5",
        codex_model="gpt-5.3-codex",
        previous_entity=None,
    )
    assert entity == "chat"


def test_resolve_entity_models_from_gpt_default():
    chat, codex = resolve_entity_models(
        default_model="gpt-5.4",
        available_models=["gpt-5.5", "gpt-5.4", "gpt-5.3-codex"],
    )
    assert chat == "gpt-5.4"
    assert codex == "gpt-5.3-codex"


def test_resolve_entity_models_from_codex_default():
    chat, codex = resolve_entity_models(
        default_model="gpt-5.3-codex",
        available_models=["gpt-5.5", "gpt-5.3-codex"],
    )
    assert chat == "gpt-5.5"
    assert codex == "gpt-5.3-codex"


def test_resolve_entity_models_explicit_overrides_win():
    chat, codex = resolve_entity_models(
        default_model="gpt-5.4",
        chat_model="gpt-5.5",
        codex_model="gpt-5.1-codex-max",
        available_models=["gpt-5.4", "gpt-5.3-codex"],
    )
    assert chat == "gpt-5.5"
    assert codex == "gpt-5.1-codex-max"


def test_resolve_entity_models_falls_back_to_defaults():
    chat, codex = resolve_entity_models(default_model="", available_models=[])
    assert chat == DEFAULT_CHAT_MODEL
    assert codex == DEFAULT_CODEX_MODEL
