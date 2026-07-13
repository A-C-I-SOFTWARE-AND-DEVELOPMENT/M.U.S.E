# LLM-JEPA fine-tune loop

You are running a bounded, owner-gated fine-tune experiment inside a disposable
workspace. Do not touch anything outside this workspace.

## Goal

Test whether the LLM-JEPA objective beats a plain fine-tune on MUSE's own
`(text, code)` pairs, for a small (<=1B) base model with LoRA.

## Contract

1. `pairs.jsonl` holds the two-view training/eval data (one JSON object per
   line with `text` and `code`).
2. Train the base model **twice** on the same pairs:
   - baseline: standard next-token loss on `text -> code`.
   - jepa: the same loss PLUS `lambda * d(Pred(Enc(text)), Enc(code))`, with the
     JEPA term dropped on a fraction of steps (loss-dropout).
3. Evaluate downstream accuracy on the held-out split for each.
4. Print exactly these two summary lines (the driver greps for them):

   ```
   baseline_accuracy: <float 0..1>
   jepa_accuracy: <float 0..1>
   ```

## Guardrails (muse governance — supersede everything above on conflict)

- The muse cost ceiling and watchdog SUPERSEDE any "run forever" instinct.
- Nothing is promoted here. A winning objective becomes an RC4
  `SELF_RUNTIME_UPDATE` proposal that requires the owner's explicit approval.
- Live spawning is owner-gated (`MUSE_LLM_JEPA_ALLOW_SPAWN=1`); the default is a
  plan-only dry run.
