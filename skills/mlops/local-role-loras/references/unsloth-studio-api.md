# Unsloth Studio API (this host)

Base: `http://127.0.0.1:8888`
Auth: `Authorization: Bearer $UNSLOTH_API_KEY`
HF: header `X-Unsloth-HF-Token` from `HF_TOKEN` in `%HERMES_HOME%\.env`

## Download

```
POST /api/hub/download
{
  "repo_id": "unsloth/Qwen3.8-27B-GGUF",
  "gguf_variant": "UD-Q3_K_XL",
  "transport_mode": "http",
  "use_xet": false
}
```

List variants: `GET /api/hub/gguf-variants?repo_id=unsloth/Qwen3.8-27B-GGUF`
Status: `GET /api/hub/download-status?repo_id=...&gguf_variant=UD-Q3_K_XL`
Active: `GET /api/hub/active-downloads`

Cancel:

```
POST /api/hub/download/cancel
{ "repo_id": "unsloth/Qwen3.8-27B-GGUF", "gguf_variant": "Q4_K_S", "generation": 1 }
```

`generation` comes from the start response / active-downloads row. Scope the
cancel to that run.

## Progress lie

`GET /api/hub/download-progress` can report `downloaded_bytes: 0` and
`expected_bytes: 13575` while the real file grows as
`~/.cache/huggingface/hub/models--unsloth--Qwen3.8-27B-GGUF/blobs/*.incomplete`.
Trust the blob `st_size`, not the progress JSON.

Worker pid/transport: `~/.unsloth/studio/cache/hub-state/workers/*.json`

## Scan folders

```
POST /api/hub/scan-folders
{ "path": "C:\\Users\\Echer\\models\\agents" }
```

GET lists registered folders. After hardlink, Studio lists named models off
one GGUF.

## Do not

- `use_xet: true` — stalls at 0 B here.
- Variant `Q4_K_S` — not Unsloth Dynamic.
- `GET /api/models/check-vision/unsloth/Qwen3.5-4B-unsloth-bnb-4bit` — repo
  404, then ~60s subprocess timeout. Skip missing bnb-4bit names.
