# Studio train + GGUF completeness (measured 2026-08-15)

## GGUF is inference-only

`POST http://127.0.0.1:8888/api/train/start` with `model_format: "gguf"`
returns `400 {"detail":{"code":"training_model_gguf_not_trainable",
"message":"GGUF models are inference-only and cannot be trained."}}`.

Tried on local `qwythos` Q4_K_M. Same for Qwen3.8-27B UD-Q3_K_XL.

Train `unsloth/Qwen3-8B-bnb-4bit` (safetensors) with
`device_map={'': 0}`. Keep the 27B GGUF as the shared inference base.

## Dataset check-format

- Upload: `POST /api/hub/datasets/upload` multipart `file`.
- Check: `POST /api/hub/datasets/check-format` requires `dataset_name`
  (stored filename or absolute `stored_path`). `{path: ...}` alone → 422.
- ShareGPT `messages` JSONL detects as `chatml` here. Use
  `format_type: "chatml"` and point `local_datasets` at the stored_path.

## Completeness (not `ls` size)

`st_size` after multi-range / `truncate()` can be the highest offset
written. GGUF magic at byte 0 is not enough. Sample ≥8 evenly spaced
4 KiB blocks; any all-zero block means holes — delete and
sequential-resume to a `.part` file, then rename.

Studio `state=running` with 0-byte blobs for >15s is a stall. Cancel.
Trust blob growth, not the active-downloads row.
