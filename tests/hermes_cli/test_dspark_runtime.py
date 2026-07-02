"""Tests for the DSpark speculative-decoding runtime and draft catalog."""

import json

from hermes_cli.local_models.dspark import (
    DSPARK_CHECKPOINTS,
    OFFICIAL_DRAFTS,
    build_dspark_plan,
    resolve_checkpoint,
    resolve_draft,
)
from hermes_cli.local_models.server_adapters import SUPPORTED_RUNTIMES, get_adapter


# =============================================================================
# Draft catalog resolution
# =============================================================================


class TestResolveDraft:
    def test_hf_id(self):
        draft = resolve_draft("Qwen/Qwen3-8B")
        assert draft is not None
        assert draft.draft_hf == "deepseek-ai/dspark_qwen3_8b_block7"

    def test_ollama_ref(self):
        draft = resolve_draft("qwen3:8b")
        assert draft is not None
        assert draft.family == "qwen3-8b"

    def test_gguf_path(self):
        draft = resolve_draft("/models/qwen3-8b-instruct-Q4_K_M.gguf")
        assert draft is not None
        assert draft.family == "qwen3-8b"

    def test_hyphenated_generation(self):
        """"gemma-4-12b" and "gemma4-12b" both match the gemma4-12b family."""
        draft = resolve_draft("google/gemma-4-12B-it")
        assert draft is not None
        assert draft.draft_hf == "deepseek-ai/dspark_gemma4_12b_block7"

    def test_size_must_match_exactly(self):
        assert resolve_draft("qwen3-80b") is None

    def test_unknown_model(self):
        assert resolve_draft("mistralai/Mistral-7B-Instruct") is None

    def test_all_official_drafts_resolve_their_target(self):
        for draft in OFFICIAL_DRAFTS:
            assert resolve_draft(draft.target_hf) == draft


class TestResolveCheckpoint:
    def test_v4_flash(self):
        assert (
            resolve_checkpoint("deepseek-ai/DeepSeek-V4-Flash")
            == "deepseek-ai/DeepSeek-V4-Flash-DSpark"
        )

    def test_v4_pro(self):
        assert (
            resolve_checkpoint("deepseek-v4-pro")
            == "deepseek-ai/DeepSeek-V4-Pro-DSpark"
        )

    def test_requires_deepseek_in_ref(self):
        assert resolve_checkpoint("someone/v4-flash-clone") is None

    def test_non_v4_deepseek(self):
        assert resolve_checkpoint("deepseek-chat") is None

    def test_catalog_values_are_dspark_checkpoints(self):
        for checkpoint in DSPARK_CHECKPOINTS.values():
            assert checkpoint.endswith("-DSpark")


# =============================================================================
# Launch plans
# =============================================================================


class TestLlamaCppPlan:
    def test_gguf_infers_llamacpp_with_spec_flags(self):
        plan = build_dspark_plan("/models/qwen3-8b-instruct-Q4_K_M.gguf")
        assert plan.runtime == "dspark"
        assert "--spec-draft-model" in plan.command
        idx = plan.command.index("--spec-draft-model")
        assert plan.command[idx + 1] == "ankk98/dspark-qwen3-8b-block7-Q4_K_M-GGUF"
        assert plan.command[0] == "llama-server"

    def test_pull_command_downloads_draft_repo(self):
        plan = build_dspark_plan("/models/qwen3-8b-instruct-Q4_K_M.gguf")
        assert plan.pull_command == (
            "huggingface-cli", "download", "ankk98/dspark-qwen3-8b-block7-Q4_K_M-GGUF",
        )

    def test_explicit_local_draft_path_no_pull(self):
        plan = build_dspark_plan(
            "/models/qwen3-8b.gguf",
            runtime="llama.cpp",
            draft="/models/dspark-draft.gguf",
        )
        idx = plan.command.index("--spec-draft-model")
        assert plan.command[idx + 1] == "/models/dspark-draft.gguf"
        assert plan.pull_command == ()

    def test_no_gguf_draft_known_gives_empty_command(self):
        plan = build_dspark_plan("/models/qwen3-14b.gguf")  # no GGUF conversion yet
        assert plan.command == ()
        assert "qwen3-8b" in plan.notes  # points at the families that do have one


class TestVllmPlan:
    def test_speculators_draft_preferred(self):
        plan = build_dspark_plan("Qwen/Qwen3-8B", runtime="vllm")
        assert plan.command[:3] == ("vllm", "serve", "Qwen/Qwen3-8B")
        assert "--speculative-config" in plan.command
        idx = plan.command.index("--speculative-config")
        spec = json.loads(plan.command[idx + 1])
        assert spec["model"] == "mgoin/Qwen3-8B-speculator.dspark"
        assert spec["num_speculative_tokens"] == 5

    def test_raw_deepspec_draft_when_no_speculators_conversion(self):
        plan = build_dspark_plan("Qwen/Qwen3-14B", runtime="vllm")
        idx = plan.command.index("--speculative-config")
        spec = json.loads(plan.command[idx + 1])
        assert spec["model"] == "deepseek-ai/dspark_qwen3_14b_block7"

    def test_v4_checkpoint_served_directly(self):
        plan = build_dspark_plan("deepseek-v4-flash", runtime="vllm")
        assert plan.command[:3] == (
            "vllm", "serve", "deepseek-ai/DeepSeek-V4-Flash-DSpark",
        )
        assert "--speculative-config" not in plan.command

    def test_unknown_model_gives_empty_command(self):
        plan = build_dspark_plan("mistralai/Mistral-7B-Instruct", runtime="vllm")
        assert plan.command == ()
        assert "DeepSpec" in plan.notes


class TestRuntimeSelection:
    def test_bad_runtime_raises(self):
        import pytest
        with pytest.raises(KeyError):
            build_dspark_plan("Qwen/Qwen3-8B", runtime="sglang")


# =============================================================================
# ServerAdapter registration
# =============================================================================


class TestDsparkAdapter:
    def test_registered_runtime(self):
        assert "dspark" in SUPPORTED_RUNTIMES

    def test_get_adapter(self):
        adapter = get_adapter("dspark")
        assert adapter.runtime == "dspark"

    def test_is_installed_does_not_raise(self):
        # True/False depends on the host; the call itself must be safe.
        assert get_adapter("dspark").is_installed() in (True, False)

    def test_launch_plan_delegates_to_builder(self):
        plan = get_adapter("dspark").launch_plan("Qwen/Qwen3-8B", port=9999)
        assert plan.runtime == "dspark"
