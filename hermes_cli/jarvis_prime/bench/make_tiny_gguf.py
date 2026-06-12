"""Build a tiny random-weight llama-architecture GGUF for MECHANICAL testing.

The model produces garbage text by construction (random weights, ~tiny dims) —
it exists solely so llama.cpp server mechanics (grammar plumb-through, slot
prompt-cache reuse, draft-model flag acceptance, llama-bench) can be exercised
on hardware where no real GGUF is available. Never use it for quality numbers.

Requires the ``gguf`` pip package (dev-only). Usage:
    python -m hermes_cli.jarvis_prime.bench.make_tiny_gguf /tmp/tiny.gguf
"""

from __future__ import annotations

import sys
from pathlib import Path

VOCAB_SIZE = 256  # byte-level: tokens are the 256 raw bytes + specials
HIDDEN = 64
LAYERS = 2
HEADS = 4
KV_HEADS = 4
FFN = 128
CTX = 2048


def build(out_path: Path, *, seed: int = 0) -> Path:
    import numpy as np
    from gguf import GGUFWriter

    rng = np.random.default_rng(seed)
    n_vocab = VOCAB_SIZE + 3  # +bos +eos +unk

    writer = GGUFWriter(str(out_path), "llama")
    writer.add_name("muse-tiny-mechanical")
    writer.add_context_length(CTX)
    writer.add_embedding_length(HIDDEN)
    writer.add_block_count(LAYERS)
    writer.add_feed_forward_length(FFN)
    writer.add_head_count(HEADS)
    writer.add_head_count_kv(KV_HEADS)
    writer.add_rope_dimension_count(HIDDEN // HEADS)
    writer.add_layer_norm_rms_eps(1e-5)
    writer.add_file_type(0)  # all-F32

    # Byte-level vocab: SPM-style byte tokens so any UTF-8 prompt tokenizes.
    tokens = ["<unk>", "<s>", "</s>"] + [f"<0x{b:02X}>" for b in range(VOCAB_SIZE)]
    scores = [0.0] * len(tokens)
    toktypes = [2, 3, 3] + [6] * VOCAB_SIZE  # UNKNOWN, CONTROL, then BYTE
    writer.add_tokenizer_model("llama")
    writer.add_token_list(tokens)
    writer.add_token_scores(scores)
    writer.add_token_types(toktypes)
    writer.add_unk_token_id(0)
    writer.add_bos_token_id(1)
    writer.add_eos_token_id(2)

    def t(name: str, shape: tuple[int, ...]) -> None:
        writer.add_tensor(name, rng.standard_normal(shape, dtype=np.float32) * 0.02)

    t("token_embd.weight", (n_vocab, HIDDEN))
    t("output_norm.weight", (HIDDEN,))
    t("output.weight", (n_vocab, HIDDEN))
    for i in range(LAYERS):
        p = f"blk.{i}."
        t(p + "attn_norm.weight", (HIDDEN,))
        t(p + "attn_q.weight", (HIDDEN, HIDDEN))
        t(p + "attn_k.weight", (HIDDEN, HIDDEN))
        t(p + "attn_v.weight", (HIDDEN, HIDDEN))
        t(p + "attn_output.weight", (HIDDEN, HIDDEN))
        t(p + "ffn_norm.weight", (HIDDEN,))
        t(p + "ffn_gate.weight", (FFN, HIDDEN))
        t(p + "ffn_down.weight", (HIDDEN, FFN))
        t(p + "ffn_up.weight", (FFN, HIDDEN))

    writer.write_header_to_file()
    writer.write_kv_data_to_file()
    writer.write_tensors_to_file()
    writer.close()
    return out_path


if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("/tmp/muse-tiny.gguf")
    path = build(target)
    print(f"wrote {path} ({path.stat().st_size / 1e6:.1f} MB)")
