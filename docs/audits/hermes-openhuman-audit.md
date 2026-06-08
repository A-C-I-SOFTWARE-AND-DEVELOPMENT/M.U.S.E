# Hermes / MUSE ⇄ OpenHuman Audit

> Audit performed against the live local checkouts at `/home/user/hermes-agent`
> (this repo) and `/home/user/openhuman` (reference only). Date: 2026-06-03.
> Scope: tool-output handling, credential safety, context-budget machinery, and
> the surfaces relevant to porting OpenHuman's **TokenJuice** terminal-output
> compaction into Hermes.

## 1. Why this audit exists

OpenHuman ships a **TokenJuice** engine that compacts verbose tool output
(git/cargo/npm/docker/tsc logs, …) with JSON-rule-based reducers *before* that
output enters the LLM context window. Hermes has no equivalent first-pass
reducer — it relies entirely on size-threshold persistence/truncation. The goal
is to bring TokenJuice-style compaction to Hermes **without** weakening any
existing guardrail, and using OpenHuman only as a behavioral reference (its Rust
code is GPL-3.0 — see §6).

## 2. Hermes tool-execution path (the integration target)

Both tool-execution loops live in **`agent/tool_executor.py`**:

| Path | Function | persist | append msg | budget |
|---|---|---|---|---|
| Concurrent | `execute_tool_calls_concurrent` | `maybe_persist_tool_result` @ **:421** | `make_tool_result_message` @ **:446** | `enforce_turn_budget` @ **:457** |
| Sequential | `execute_tool_calls_sequential` | persist @ **:843** | append @ **:861** | budget @ **:896** |

The per-tool worker `_run_tool` (`:197`) calls `agent._invoke_tool(...)`
(→ `model_tools.invoke_tool`) and yields a `function_result` string (or a
`_multimodal` dict). After execution each result flows:

```
function_result
  → _append_guardrail_observation        (guardrail trail)
  → _record_file_mutation_result         (turn-end verifier)
  → maybe_persist_tool_result            (L2: spill >threshold raw to sandbox)
  → _tool_result_content_for_active_model(multimodal/vision handling)
  → make_tool_result_message → messages.append
  → enforce_turn_budget                  (L3: aggregate 200K cap)
```

Both paths guard string-only handling with `if not
_is_multimodal_tool_result(function_result)`. **This is the exact seam** where
TokenJuice belongs: immediately before `maybe_persist_tool_result`, so the
existing persistence/budget layers still run as a fallback on whatever
TokenJuice returns.

## 3. Existing raw-preservation & budget machinery (must NOT be replaced)

`tools/tool_result_storage.py` + `tools/budget_config.py`:

- **L2 — `maybe_persist_tool_result`**: if a result exceeds the tool's threshold
  (`DEFAULT_RESULT_SIZE_CHARS = 100_000`, some tools pinned), the full raw output
  is written to the sandbox and the in-context content is replaced with a
  `<persisted-output>` preview (`DEFAULT_PREVIEW_SIZE_CHARS = 1_500`) + a path the
  model can re-read. **Raw is preserved.**
- **L3 — `enforce_turn_budget`**: after all tools in a turn, if the aggregate
  exceeds `DEFAULT_TURN_BUDGET_CHARS = 200_000`, the largest non-persisted
  results are spilled until under budget.

TokenJuice is a **first-pass reducer** that sits *ahead* of these. It reduces
the common-case noise (so most outputs never hit the threshold) while L2/L3
remain the safety net for anything still large.

## 4. SECURITY GAP found: tool output is not secret-scrubbed

There is **no credential/secret scrubbing of tool _output_** before it reaches
the model. The only sanitizers are:

- `model_tools.py:525 _sanitize_tool_error` — **errors only**; strips role tags,
  code fences, CDATA, and length-caps. Does not redact secrets.
- `tools/schema_sanitizer.sanitize_tool_schemas` — tool *schemas*, not output.
- `agent/memory_manager.py` `StreamingContextScrubber` / `sanitize_context` —
  scrubs *memory/context injection*, not live tool output.

A tool that prints an API key, `Authorization: Bearer …`, or a private key sends
it verbatim into history and to the provider. Closing this is a prerequisite for
"scrub before compaction" (brief constraint #6) and a real standalone fix. The
new `tools/tokenjuice/scrub.py::scrub_credentials` runs in both tool paths.

## 5. Guardrails that must remain intact

`_guardrail_block_result` / `_append_guardrail_observation` (pre/post tool
guardrails), `maybe_persist_tool_result`, `enforce_turn_budget`,
`agent/iteration_budget.py` (turn budget), `agent/file_safety.py`,
`agent/message_sanitization.py`, the `/steer` drain, and the multimodal/vision
handling in `_tool_result_content_for_active_model`. TokenJuice is inserted
*between* execution and persistence and changes none of these contracts.

## 6. License audit (gating)

| Artifact | License | Action |
|---|---|---|
| `hermes-agent/LICENSE`, `pyproject.toml` | **MIT** (© 2025 Nous Research) | host |
| `openhuman/LICENSE` | **GPL-3.0** | ❌ never copy code |
| `openhuman/.../tokenjuice/*.rs` | GPL-3.0 (derived) | ❌ reference only |
| `openhuman/.../tokenjuice/vendor/rules/*.json` | **MIT** (© 2026 Vincent Koc, `vincentkoc/tokenjuice`) | ✅ reuse w/ attribution |

The 96 vendored JSON rule files are verbatim from the MIT upstream
`vincentkoc/tokenjuice` and carry their own MIT license (documented in
`openhuman/.../tokenjuice/vendor/README.md`). They are **data**, MIT-licensed,
and reusable in an MIT project. The reducer itself is **clean-room
reimplemented** in Python from the public upstream behavior — no GPL Rust is
copied. Attribution added to `THIRD_PARTY_NOTICES.md`.

## 7. Naming / collision notes

- `hermes_cli/jarvis_prime/tokenjuice.py` already exists — it is a **context
  compiler** (`TokenJuiceCompiler`, packs mission/memory/research into a
  token-bounded prompt packet). Unrelated to output compaction. New code lives in
  a separate package `tools/tokenjuice/` to avoid confusion.
- Config: authoritative loader `hermes_cli/config.py::load_config`;
  `cli-config.yaml` parsed via `yaml.safe_load` (`cli.py:412`). New section:
  `tool_output.compaction.*`.

## 8. Answers to the brief's audit questions

- **Where should compaction happen?** `agent/tool_executor.py`, before
  `maybe_persist_tool_result` in both paths.
- **Where is credential scrubbing?** Nowhere for output today — added here.
- **Where is raw output preserved?** L2 sandbox persistence (existing) + a new
  pre-scrub append-only raw log (`tools/tokenjuice/raw_log.py`).
- **Which outputs must never be compacted?** Multimodal results; file-inspection
  tools (`read_file`/`cat`/`sed`/`jq`/…) via `skip_tools`; anything < 512 chars.
- **What recovers full output?** The `<persisted-output>` path (model-readable)
  and the raw log (human/debug only).
- **Duplicated paths?** Sequential and concurrent executors duplicate the
  persist→append→budget sequence; the new helper is called identically in both.
- **What breaks if output is replaced by a compacted version?** Nothing in the
  persistence/budget contract — they operate on whatever string is returned.
  Pass-through safety + fail-open guarantee a never-worse result.
