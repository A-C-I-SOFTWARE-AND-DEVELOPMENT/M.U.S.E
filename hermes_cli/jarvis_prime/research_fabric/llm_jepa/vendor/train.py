#!/usr/bin/env python
"""LLM-JEPA fine-tune harness (clean-room implementation of arXiv 2509.14252).

This is the only "mutable" surface of the engine, and it is mutated ONLY inside
disposable workspaces (never in the muse tree). It trains a small causal LM two
ways on the same (text, code) pairs and reports downstream accuracy for each so
the muse benchmark gate can compare them:

  * baseline: standard next-token loss on ``text -> code``.
  * jepa:     next-token loss PLUS the LLM-JEPA term

        L = L_LLM + lambda * d(Pred(Enc(text)), Enc(code))

    where Enc(x) is the last-token last-layer hidden state, Pred is a
    tied-weights predictor invoked by appending ``[PRED]`` tokens, d is cosine
    distance, and the JEPA term is dropped on a fraction of steps
    (loss-dropout) to recover most of the ~2x compute overhead.

Emits two summary lines the driver greps for::

    baseline_accuracy: <float in [0,1]>
    jepa_accuracy: <float in [0,1]>

torch / transformers / peft are imported lazily inside ``main`` so importing
this file (e.g. for static checks) never pulls a GPU stack. Requires owner
hardware; invoked via ``uv run train.py`` inside a seeded workspace.
"""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="LLM-JEPA fine-tune harness")
    ap.add_argument("--pairs", default="pairs.jsonl", help="two-view JSONL")
    ap.add_argument("--model", default="Qwen/Qwen2.5-0.5B")
    ap.add_argument("--lora-rank", type=int, default=512)
    ap.add_argument("--jepa-lambda", type=float, default=0.5)
    ap.add_argument("--jepa-dropout", type=float, default=0.75)
    ap.add_argument("--epochs", type=int, default=1)
    ap.add_argument("--eval-holdout", type=float, default=0.2)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--max-new-tokens", type=int, default=64)
    return ap.parse_args()


def load_pairs(path: str) -> list[dict]:
    rows: list[dict] = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        if rec.get("text") and rec.get("code"):
            rows.append(rec)
    return rows


def split(rows: list[dict], holdout: float, seed: int) -> tuple[list[dict], list[dict]]:
    rng = random.Random(seed)
    shuffled = rows[:]
    rng.shuffle(shuffled)
    n_eval = max(1, int(len(shuffled) * holdout)) if shuffled else 0
    return shuffled[n_eval:], shuffled[:n_eval]


def main() -> int:
    args = parse_args()

    # Heavy imports are deferred so static tooling never needs the GPU stack.
    import torch  # noqa: F401
    from peft import LoraConfig, get_peft_model
    from transformers import AutoModelForCausalLM, AutoTokenizer

    torch.manual_seed(args.seed)
    random.seed(args.seed)

    rows = load_pairs(args.pairs)
    if not rows:
        print("baseline_accuracy: 0.0")
        print("jepa_accuracy: 0.0")
        return 0

    train_rows, eval_rows = split(rows, args.eval_holdout, args.seed)

    tok = AutoTokenizer.from_pretrained(args.model)
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token
    # A dedicated predictor token drives the tied-weights JEPA predictor.
    tok.add_special_tokens({"additional_special_tokens": ["[PRED]"]})
    pred_id = tok.convert_tokens_to_ids("[PRED]")

    def build_model():
        model = AutoModelForCausalLM.from_pretrained(args.model)
        model.resize_token_embeddings(len(tok))
        lora = LoraConfig(r=args.lora_rank, lora_alpha=args.lora_rank, task_type="CAUSAL_LM")
        return get_peft_model(model, lora)

    def encode(model, text: str) -> "torch.Tensor":
        """Enc(x): last-token last-layer hidden state, [PRED]-conditioned."""
        ids = tok(text + "[PRED]", return_tensors="pt").input_ids
        out = model(ids, output_hidden_states=True)
        return out.hidden_states[-1][0, -1, :]

    def jepa_term(model, text: str, code: str) -> "torch.Tensor":
        enc_text = encode(model, text)
        enc_code = encode(model, code)
        # Pred is the tied model itself (predictor = tied weights, per the paper).
        cos = torch.nn.functional.cosine_similarity(enc_text, enc_code, dim=0)
        return 1.0 - cos  # cosine DISTANCE

    def lm_loss(model, text: str, code: str) -> "torch.Tensor":
        prompt = f"{text}\n{code}"
        enc = tok(prompt, return_tensors="pt")
        labels = enc.input_ids.clone()
        return model(**enc, labels=labels).loss

    def train(use_jepa: bool):
        model = build_model()
        model.train()
        opt = torch.optim.AdamW(
            [p for p in model.parameters() if p.requires_grad], lr=1e-4
        )
        for _ in range(args.epochs):
            for row in train_rows:
                opt.zero_grad()
                loss = lm_loss(model, row["text"], row["code"])  # L_LLM
                if use_jepa and random.random() >= args.jepa_dropout:
                    loss = loss + args.jepa_lambda * jepa_term(
                        model, row["text"], row["code"]
                    )
                loss.backward()
                opt.step()
        model.eval()
        return model

    def accuracy(model) -> float:
        if not eval_rows:
            return 0.0
        hits = 0
        for row in eval_rows:
            ids = tok(row["text"] + "\n", return_tensors="pt").input_ids
            gen = model.generate(ids, max_new_tokens=args.max_new_tokens)
            text = tok.decode(gen[0][ids.shape[1]:], skip_special_tokens=True)
            # Token-overlap match: fraction of gold code tokens produced.
            gold = set(row["code"].split())
            got = set(text.split())
            if gold and len(gold & got) / len(gold) >= 0.5:
                hits += 1
        return hits / len(eval_rows)

    baseline_model = train(use_jepa=False)
    baseline_acc = accuracy(baseline_model)
    del baseline_model

    jepa_model = train(use_jepa=True)
    jepa_acc = accuracy(jepa_model)

    print(f"baseline_accuracy: {baseline_acc}")
    print(f"jepa_accuracy: {jepa_acc}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
