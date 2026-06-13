"""Tests for the default edit providers (catalog, LLM wrapper, chain)."""

from __future__ import annotations

import ast
from pathlib import Path

from hermes_cli.jarvis_prime.research_fabric.autoresearch.engine import (
    EditContext,
    ExperimentConfig,
    ExperimentResult,
    VENDOR_DIR,
)
from hermes_cli.jarvis_prime.research_fabric.autoresearch.ideas import (
    DEFAULT_IDEAS,
    CatalogEditProvider,
    ChainEditProvider,
    LlmEditProvider,
    default_edit_provider,
    set_constant,
)

HPARAM_BLOCK = """\
# header
ASPECT_RATIO = 64       # model_dim = depth * ASPECT_RATIO
WINDOW_PATTERN = "SSSL" # sliding window pattern
MATRIX_LR = 0.04        # learning rate for matrix parameters (Muon)
DEPTH = 8               # number of transformer layers
x = MATRIX_LR + 1
"""


def _ctx(tmp_path: Path, train_py: str, history: tuple = ()) -> EditContext:
    (tmp_path / "train.py").write_text(train_py, encoding="utf-8")
    return EditContext(
        workspace=str(tmp_path),
        history=history,
        best_bpb=1.0,
        config=ExperimentConfig(tag="t"),
    )


def _result(index: int, description: str, status: str = "discard") -> ExperimentResult:
    return ExperimentResult(
        index=index, commit=f"c{index:06d}", description=description,
        val_bpb=1.0, peak_vram_mb=9000.0, mfu_percent_raw=None,
        mfu_percent_honest=None, training_seconds=None, total_seconds=None,
        total_tokens_m=None, num_steps=None, num_params_m=None, depth=None,
        status=status,
    )


def test_set_constant_preserves_comment_and_rejects_noop() -> None:
    out = set_constant(HPARAM_BLOCK, "MATRIX_LR", "0.06")
    assert out is not None
    assert "MATRIX_LR = 0.06        # learning rate for matrix parameters (Muon)" in out
    assert "x = MATRIX_LR + 1" in out  # only the assignment line changes
    assert set_constant(HPARAM_BLOCK, "MATRIX_LR", "0.04") is None  # no-op
    assert set_constant(HPARAM_BLOCK, "NO_SUCH_KNOB", "1") is None


def test_catalog_applies_to_the_real_vendored_train_py(tmp_path: Path) -> None:
    vendored = (VENDOR_DIR / "train.py").read_text(encoding="utf-8")
    provider = CatalogEditProvider()
    ctx = _ctx(tmp_path, vendored)
    edit = provider(ctx)
    assert edit is not None
    assert edit.description == DEFAULT_IDEAS[0].description
    assert edit.train_py != vendored
    ast.parse(edit.train_py)  # emitted code always parses
    assert "MATRIX_LR = 0.06" in edit.train_py


def test_catalog_never_repeats_and_eventually_exhausts(tmp_path: Path) -> None:
    vendored = (VENDOR_DIR / "train.py").read_text(encoding="utf-8")
    provider = CatalogEditProvider()
    history: list[ExperimentResult] = []
    seen: list[str] = []
    for i in range(len(DEFAULT_IDEAS) + 2):
        ctx = _ctx(tmp_path, vendored, history=tuple(history))
        edit = provider(ctx)
        if edit is None:
            break
        assert edit.description not in seen
        seen.append(edit.description)
        history.append(_result(i, edit.description))
    assert edit is None  # exhausted, loop would stop edit_provider_exhausted
    assert len(seen) == len(DEFAULT_IDEAS)


def test_catalog_skips_ideas_whose_knobs_were_renamed(tmp_path: Path) -> None:
    # A previous kept edit removed MATRIX_LR entirely; those ideas are skipped.
    source = HPARAM_BLOCK.replace("MATRIX_LR = 0.04", "FUSED_LR = 0.04").replace(
        "x = MATRIX_LR + 1", "x = FUSED_LR + 1"
    )
    edit = CatalogEditProvider()(_ctx(tmp_path, source))
    assert edit is not None
    assert "matrix LR" not in edit.description  # skipped both MATRIX_LR ideas
    assert "WINDOW_PATTERN" in "".join(k for k, _ in DEFAULT_IDEAS[3].knobs)


def test_llm_provider_validates_hard(tmp_path: Path) -> None:
    good_body = 'from prepare import MAX_SEQ_LEN\nDEPTH = 4\n'
    replies = iter(
        [
            "no code at all",
            "desc\n```python\ndef broken(:\n```",  # doesn't parse
            "desc\n```python\nDEPTH = 4\n```",  # drops the harness import
            f"try depth 4\n```python\n{good_body}```",
        ]
    )
    provider = LlmEditProvider(lambda prompt: next(replies), max_ideas=10)
    ctx = _ctx(tmp_path, "from prepare import MAX_SEQ_LEN\nDEPTH = 8\n")
    assert provider(ctx) is None  # no fence
    assert provider(ctx) is None  # syntax error
    assert provider(ctx) is None  # harness import dropped
    edit = provider(ctx)
    assert edit is not None
    assert edit.description == "llm: try depth 4"
    assert edit.train_py == good_body


def test_llm_provider_is_bounded(tmp_path: Path) -> None:
    calls: list[int] = []

    def runner(prompt: str) -> str:
        calls.append(1)
        return "nothing useful"

    provider = LlmEditProvider(runner, max_ideas=2)
    ctx = _ctx(tmp_path, "from prepare import X\n")
    assert provider(ctx) is None and provider(ctx) is None
    assert provider(ctx) is None  # budget exhausted: runner not called again
    assert len(calls) == 2


def test_default_provider_chains_catalog_then_llm(tmp_path: Path) -> None:
    vendored = (VENDOR_DIR / "train.py").read_text(encoding="utf-8")
    llm_calls: list[str] = []

    def runner(prompt: str) -> str:
        llm_calls.append(prompt)
        return (
            "llm wins after catalog\n```python\nfrom prepare import MAX_SEQ_LEN\nZ = 1\n```"
        )

    provider = default_edit_provider(runner)
    # Catalog has ideas: LLM is not consulted.
    edit = provider(_ctx(tmp_path, vendored))
    assert edit is not None and not edit.description.startswith("llm:")
    assert llm_calls == []
    # Catalog exhausted (every idea already in history): LLM takes over.
    history = tuple(_result(i, idea.description) for i, idea in enumerate(DEFAULT_IDEAS))
    edit = provider(_ctx(tmp_path, vendored, history=history))
    assert edit is not None and edit.description.startswith("llm:")
    assert len(llm_calls) == 1


def test_chain_returns_none_when_everything_is_exhausted(tmp_path: Path) -> None:
    provider = ChainEditProvider([lambda ctx: None, lambda ctx: None])
    assert provider(_ctx(tmp_path, "x = 1\n")) is None
