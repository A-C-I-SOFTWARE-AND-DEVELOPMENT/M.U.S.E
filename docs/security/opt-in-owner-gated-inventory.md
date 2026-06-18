# Opt-in / owner-gated toggle inventory

MUSE ships **default-safe**: every capability that spends money, touches the
network destructively, spawns a heavy process, relaxes a safety guard, or
changes default runtime behaviour is **off until you opt in**. This page is the
plain-English index of those toggles. The machine-readable source of truth is
[`docs/architecture/muse-toggle-registry.yaml`](../architecture/muse-toggle-registry.yaml),
loaded and resolved by
[`hermes_cli/jarvis_prime/toggles.py`](../../hermes_cli/jarvis_prime/toggles.py).

> **One inspectable surface.** Don't memorise this list — ask MUSE:
>
> ```bash
> python -m hermes_cli.jarvis_prime toggles list            # the whole catalog
> python -m hermes_cli.jarvis_prime toggles list --group B1 # just owner-gated
> python -m hermes_cli.jarvis_prime toggles status          # on/off vs your env
> python -m hermes_cli.jarvis_prime toggles status --enabled
> python -m hermes_cli.jarvis_prime toggles show HERMES_OFFLINE
> python -m hermes_cli.jarvis_prime toggles doctor          # prove each is wired
> ```
>
> `toggles doctor` is the "leave nothing unfinished" guarantee: it fails unless
> every toggle's declared `read_sites` exist **and** mention the env var, so the
> registry can never advertise a toggle the code doesn't actually honour. The
> same check runs in CI via `tests/jarvis_prime/test_toggles.py`.

## Two kinds of gate

1. **Owner-gated action classes** — the action *types* MUSE defers on until you
   reply exactly `Yes, with authorization.`: spend, deploy, publish, OAuth,
   main-branch merge, package publish, credential change, regulated claims. The
   canonical set lives in
   [`hermes_cli/jarvis_prime/owner_auth.py`](../../hermes_cli/jarvis_prime/owner_auth.py)
   (`OWNER_GATED_ACTIONS`) and is enforced by the eight verification gates.
2. **Opt-in env toggles** — concrete environment variables that unlock gated or
   non-default behaviour. These are the registry below.

## Group legend

| Group | Meaning |
|---|---|
| **B1** | Opt-in **and** owner-gated (the intersection). Default-off; behaviour change. |
| **B2** | Spawn / self-improvement gates — nothing runs without the flag. |
| **B3** | Cognition / retrieval opt-ins — supplement, never replace, the defaults. |
| **B4** | Approval / safety toggles. |
| **B5** | Runtime / deployment toggles. |

## B1 — opt-in and owner-gated

| Env | Default | What it unlocks | Wired in |
|---|---|---|---|
| `MUSE_SYSTEM_CONTRACT` | off | Live-inject the pre-prompt System Contract (SC1..SC12) | `agent/system_prompt.py` |
| `HERMES_COCKPIT_SECRET_IMPORT` | off | Cockpit import of `~/.hermes/.env` keys (loopback-only) | `gateway/cockpit/server.py` |
| `HERMES_JARVIS_ENABLE_PAID` | off | Paid-API model routing (`paid_api_explicit_only`) | `hermes_cli/jarvis_prime/task_router.py` |
| `HERMES_PUBLISH_LIVE` | off | The live-publish gate — no push to a remote without it | `hermes_cli/github_publisher.py` |
| `HERMES_RELEASE_GATE_STRICT` | off | Release gate hard-fails on absent tooling | `hermes_cli/release_gate.py` |
| `HERMES_CAPABILITY_GATE` | off | Capability-band wall on top of the 8 gates | `hermes_cli/jarvis_prime/capability_wall.py` |
| `HERMES_ORCHESTRATOR_DISPATCH` | off | Un-403 the orchestrator dispatch route | `hermes_cli/orchestrator_api.py` |
| `HERMES_CODEX_WORKER_EXECUTE` | off | Codex worker executes instead of plan-only | `hermes_cli/workers/codex.py` |
| `HERMES_COCKPIT_AUTONOMY_LOCKED` | off | Lock cockpit autonomy at runtime | `gateway/cockpit/handlers_autonomy.py` |

## B2 — spawn / self-improvement gates

| Env | Default | What it unlocks |
|---|---|---|
| `MUSE_AUTORESEARCH_ALLOW_SPAWN` | off | Any live autoresearch training spawn |
| `MUSE_UE5_ALLOW_SPAWN` | off | Spawn a live UE5 render process |
| `MUSE_PS_ALLOW_SPAWN` | off | Spawn a Pixel Streaming render node |
| `HERMES_JARVIS_GEMMA_AUTO_RUNNER` | off | Local Gemma auto-runner (llama-server) |

## B3 — cognition / retrieval opt-ins

| Env | Default | What it unlocks |
|---|---|---|
| `MUSE_SECOND_BRAIN` | off | Fuse the Second Brain into retrieval |
| `MUSE_OBSERVATORY` | off | Observatory telemetry |
| `MUSE_TEMPLATES` | off | Templates fast-path during benchmarking |
| `MUSE_TEMPLATES_SERVER` | off | Endpoint URL for the templates fast-path server |

## B4 — approval / safety toggles

| Env | Default | What it does |
|---|---|---|
| `HERMES_YOLO_MODE` | off | Auto-approve actions (cannot bypass the hardline blocklist) |
| `HERMES_ACCEPT_HOOKS` | off | Auto-accept shell hooks |
| `HERMES_EXEC_ASK` | off | Force exec confirmation (set by the gateway) |
| `HERMES_ALLOW_ROOT_GATEWAY` | off | Permit running the gateway as root |
| `HERMES_ALLOW_PRIVATE_URLS` | off | Allow fetching private / loopback URLs |
| `HERMES_ENABLE_PROJECT_PLUGINS` | off | Auto-load repo-local `./.hermes/plugins/` |
| `HERMES_DISABLE_FILE_STATE_GUARD` | off | Disable the "file changed since you read it" guard |
| `HERMES_REDACT_SECRETS` | **on** | Redact secrets in transcripts/tool IO (set falsey to disable) |

## B5 — runtime / deployment toggles

| Env | Default | What it does |
|---|---|---|
| `HERMES_OFFLINE` | off | Router excludes cloud workers, forces local-first |
| `HERMES_GATEWAY_FORCE_STARTUP` | off | Windows: install Startup-folder item, skip Scheduled Task |
| `HERMES_DASHBOARD` | off | Launch the web dashboard side-process |
| `HERMES_DASHBOARD_TUI` | off | Expose the in-browser Chat tab |
| `HERMES_TUI` | off | Prefer the React/Ink TUI over the classic CLI |
| `HERMES_TUI_RESUME` | off | Auto-re-attach to the most recent TUI session |
| `HERMES_BOOTSTRAP_MODELS` | off | First-boot: wire every reachable model route (once) |
| `HERMES_TERMUX_GATEWAY` | off | Start the gateway alongside the Termux API |
| `HERMES_TERMUX_NO_WAKELOCK` | off | Skip the Android wake-lock |
| `HERMES_CRON_MAX_PARALLEL` | off | Cap concurrent cron jobs (1 = legacy serial) |
| `HERMES_GATEWAY_DETACHED` | off | Marker: gateway launched detached by a wrapper |
| `HERMES_DEV` | off | Dev mode: bypass container routing |
| `HERMES_IGNORE_USER_CONFIG` | off | Ignore `~/.hermes/config.yaml` this run |
| `HERMES_IGNORE_RULES` | off | Skip repo rule files |
| `HERMES_NO_CONSOLIDATE` | off | Forks: skip the update consolidation merge |
| `HERMES_SKIP_NODE_BOOTSTRAP` | off | Disable the Node.js auto-install on launch |
| `MUSE_NO_SECRET_IMPORT` | off | Termux nexus: don't auto-import secrets into the cockpit |

## Resolving a toggle from code

Prefer the registry resolver over a fresh `os.getenv(...)` parse so every read
shares one truthy convention (`1`, `true`, `yes`, `on`) and one declared default:

```python
from hermes_cli.jarvis_prime import toggles

if toggles.is_enabled("HERMES_OFFLINE"):
    ...  # local-first only
```

Adding a new toggle: add a row to
[`muse-toggle-registry.yaml`](../architecture/muse-toggle-registry.yaml) with a
real `read_sites` entry, then run `toggles doctor` (and the test suite) — it will
fail until the wiring exists. That is how MUSE keeps "documented" and "wired" the
same thing.
