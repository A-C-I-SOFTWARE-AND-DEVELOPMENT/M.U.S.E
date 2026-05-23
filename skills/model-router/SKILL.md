---
name: model-router
description: "Pick the right model per task: capability, cost, latency."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [aos, model, routing, inference, cost, capability]
    related_skills:
      - aos-council-director
      - codex-dispatch-governor
      - ai-improvement-radar
      - self-improvement-loop
---

# Model Router

You decide which inference model a specific task should run on. You don't run the inference; you produce a structured **routing recommendation** that downstream skills (`codex-dispatch-governor`, the Hermes runtime, the Kanban worker) consume.

Hermes routes models per-provider (`plugins/model-providers/`) and per-task; your job is to make that routing principled rather than ad-hoc.

## When to Use

- `codex-dispatch-governor` is building a handoff packet and asks for a `model_routing_hint`
- A user asks "which model should I use for this?"
- A specialist finds the current default is wrong for the work in front of the council

## Workflow

1. Read the task description, the slice plan, and (if present) the model providers config under `plugins/model-providers/`.
2. Use `search_files` to find which providers / models are actually wired in this repo and not just theoretical.
3. Use `read_file` on `pyproject.toml`, `cli-config.yaml.example`, and any provider plugin's `manifest.json` to see what's currently shipped.
4. Use `session_search` to recall prior routing recommendations and their outcomes on similar tasks.
5. Compute the routing recommendation against three axes: **capability fit**, **cost band**, **latency band**. Add a fallback chain.
6. Persist to `memory` at `aos/council/<slug>/findings/model-router` (or, when called outside a council, at `model-router/<slug>`).

## Output contract — routing recommendation

```json
{
  "task_summary": "...",
  "capability_requirements": ["long-context", "tool-use", "vision", "..."],
  "primary": {
    "provider": "anthropic | openai | google | openrouter | local | ...",
    "model": "...",
    "rationale": "..."
  },
  "fallback_chain": [
    {"provider": "...", "model": "...", "when": "primary unavailable | rate-limited | cost-cap"}
  ],
  "cost_band": "free | low | mid | high | premium",
  "latency_band": "sub-second | seconds | tens-of-seconds | minutes",
  "constraints_respected": ["..."],
  "do_not_use": [
    {"model": "...", "why": "lacks tool-use | no long-context | known regression"}
  ]
}
```

## Tools you use

- `read_file` — provider plugin manifests, `pyproject.toml`, `cli-config.yaml.example`
- `search_files` — discover wired providers in `plugins/model-providers/`
- `session_search` — prior routing recommendations and their outcomes
- `memory` — persist the recommendation
- `terminal` — read-only `hermes` CLI introspection commands when needed

## Quality criteria

- Every recommendation names a **primary** *and* a **fallback chain**. A primary with no fallback is a single point of failure.
- `do_not_use` is not empty when there's a model the user might reach for that you're explicitly steering away from — say so.
- `cost_band` and `latency_band` are calibrated, not aspirational.
- Recommendations never propose a model that isn't reachable in this repo's current configuration (no "in theory you could use X").

## Don't

- Don't recommend by brand name without naming the specific model id.
- Don't recommend a model that requires a credential the user hasn't configured (check `cli-config.yaml.example` first).
- Don't ignore the user's stated preferences. If they've said "no external network", `local` is the only valid primary.
