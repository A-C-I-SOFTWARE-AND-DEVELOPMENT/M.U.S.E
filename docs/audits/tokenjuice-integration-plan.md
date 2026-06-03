# TokenJuice Integration Plan (Hermes)

Clean-room Python port of TokenJuice-style terminal-output compaction, wired into
the Hermes tool loop. Behavior mirrors the MIT upstream `vincentkoc/tokenjuice`;
rule JSON is the MIT vendored set. No GPL code is copied.

## Package: `tools/tokenjuice/`

| Module | Responsibility |
|---|---|
| `types.py` | Dataclasses for the rule schema + `ToolExecutionInput`, `ReduceOptions`, `CompactionStats`. |
| `rules/*.json` | 96 MIT rule files (git, cargo, npm, docker, kubectl, gh, tsc, …). |
| `loader.py` | Three-layer overlay: builtin → user (`~/.config/tokenjuice/rules/`) → project (`.tokenjuice/rules/`). Lazy-cached. |
| `classify.py` | Pick the most specific matching rule; `generic/fallback` last. |
| `text.py` | `strip_ansi`, `dedupe_adjacent`, `trim_empty_edges`, `pretty_print_json`, width-safe head/tail. |
| `reduce.py` | The reduction pipeline. |
| `integration.py` | `compact_tool_output(...)` entry point; pass-through-safe + fail-open. |
| `scrub.py` | `scrub_credentials(text)` — secret redaction (runs before compaction). |
| `raw_log.py` | Append-only pre-scrub raw output log for debuggability. |
| `config.py` | `CompactionConfig` + loader from `cli-config.yaml`. |

## Rule schema (from upstream `JsonRule`)

```jsonc
{
  "id": "git/status", "family": "git-status", "priority": 0,
  "match": { "argv0": ["git"], "argvIncludes": [["status"]],
             "toolNames": ["exec"], "commandIncludes": ["tsc"],
             "argvIncludesAny": [...], "commandIncludesAny": [...] },
  "transforms": { "stripAnsi": true, "dedupeAdjacent": true,
                  "trimEmptyEdges": true, "prettyPrintJson": false },
  "filters": { "skipPatterns": ["^On branch "], "keepPatterns": ["error TS\\d+"] },
  "summarize": { "head": 10, "tail": 4 },
  "counters": [ { "name": "modified file", "pattern": "^...", "flags": "i" } ],
  "failure": { "preserveOnFailure": true, "head": 12, "tail": 12 },
  "onEmpty": "…", "matchOutput": [ {"pattern":"…","message":"…"} ],
  "counterSource": "postKeep"
}
```

## Reduction pipeline (`reduce.py`)

1. `strip_ansi` (if set).
2. Split lines; `trim_empty_edges`; `dedupe_adjacent`.
3. **filters**: drop `skipPatterns`; if `keepPatterns` present, keep only matches.
4. **counters**: count lines matching each counter (source = pre/post keep per
   `counterSource`, default `postKeep`).
5. **summarize**: if remaining lines > head+tail, keep `head` + `… N lines …` +
   `tail`. On failure (`exit_code != 0`) and `preserveOnFailure`, use the larger
   `failure.head`/`failure.tail`.
6. Append counter summary line (`(3 modified file, 1 new file)`).
7. `onEmpty` message if everything filtered out; `matchOutput` canned messages.
8. `pretty_print_json` when the whole payload parses as JSON.

## Entry point & safety (`integration.py`)

```python
def compact_tool_output(tool_name, arguments, output, exit_code, config)
    -> tuple[str, CompactionStats]
```

- **Pass-through**: `len(output) < min_input_chars` (512) → return original.
- **Ratio gate**: keep compacted only if `compacted/original <= 1 -
  min_ratio_improvement` (0.05) *and* compacted is shorter; else original.
- **Clamp**: final inline output truncated to `max_inline_chars` (1200) with a
  `…[clamped]` marker.
- **Fail-open**: any exception → log + return the (scrubbed) original.
- **argv/command** derived from `arguments` (`command` string split, or `argv`
  array, or `args` list) — mirrors the Rust `extract_command_argv`.

## Ordering in the tool loop (`agent/tool_executor.py`)

For string results in **both** paths, before `maybe_persist_tool_result`:

```
1. raw_log.record(session, tool_use_id, name, args, RAW, exit_code)  # pre-scrub
2. scrubbed  = scrub_credentials(RAW)
3. compacted, stats = compact_tool_output(name, args, scrubbed, exit_code, cfg)
4. log "[tokenjuice] tool=… rule=… N→M (ratio=…)"
5. function_result = compacted   # → existing persist → append → budget
```

Multimodal dicts and `skip_tools` bypass. `config.enabled == False` → no-op.

## Config (`cli-config.yaml` → `tool_output.compaction`)

```yaml
tool_output:
  compaction:
    enabled: true
    min_input_chars: 512
    min_ratio_improvement: 0.05
    max_inline_chars: 1200
    preserve_raw: true
    compact_failures: true
    failure_head_lines: 80
    failure_tail_lines: 120
    builtin_rules: true
    user_rules: true
    project_rules: true
    skip_tools: [read_file, view, cat, sed, jq, head, tail]
    debug: false
```
