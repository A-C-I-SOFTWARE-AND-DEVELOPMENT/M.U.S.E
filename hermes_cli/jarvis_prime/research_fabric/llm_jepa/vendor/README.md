# LLM-JEPA fine-tune harness (vendored, clean-room)

Clean-room implementation of the LLM-JEPA training objective
(Huang, LeCun & Balestriero, arXiv 2509.14252): a JEPA auxiliary term added to
the standard next-token loss, treating `(text, code)` as two views of the same
knowledge.

This directory is treated as **inert, do-not-edit data** (see `../VENDOR.md`):
it is never imported by muse code or tests, and it is copied into a disposable
`$HERMES_HOME/llm_jepa/workspaces/<tag>/` before being run. All muse-side
control (planning, gating, promotion) lives in the sibling modules
`../engine.py` and `../views.py` and in `hermes_cli/workers/llm_jepa.py`.

## Run (owner hardware only)

```bash
cd <workspace>            # a seeded copy of this directory
uv sync                   # resolves torch from the cu128 index
uv run train.py --pairs pairs.jsonl --model Qwen/Qwen2.5-0.5B --lora-rank 512
```

Prints `baseline_accuracy:` and `jepa_accuracy:` summary lines that the muse
driver parses and disposes of through the benchmark gate.
