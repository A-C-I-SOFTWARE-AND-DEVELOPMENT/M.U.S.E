# MUSE — Free-First Launch

This is the one-command path from "nothing installed" to "MUSE
ready", with **free / open-source model routes first** and paid APIs
**explicit opt-in only**. Claude Code and Codex are wired as official
**worker lanes** — used through their own installed CLIs and your own
subscription/session — not as generic model API backends.

> Local-first, free-first, owner-gated. No secrets in git, logs, memory,
> or generated config. Termux/Android compatible.

---

## TL;DR

```bash
# Fresh install (Linux / macOS / WSL2 / Termux)
bash <(curl -fsSL https://raw.githubusercontent.com/A-C-I-SOFTWARE-AND-DEVELOPMENT/hermes-agent/main/scripts/install.sh) --jarvis-launch

# Already installed
hermes jarvis launch

# Just (re)configure model routing
hermes models bootstrap --free-first --jarvis

# Verify launch readiness
hermes doctor --jarvis-launch
```

After launch:

| Action | Command |
|---|---|
| Start Hermes | `hermes` |
| Invoke MUSE | `/jarvis` (aliases `/jp`, `/jarvis-prime`) |
| Run launch doctor | `hermes doctor --jarvis-launch` |
| **Stop MUSE immediately** | `/jarvis stop` or `python -m hermes_cli.jarvis_prime stop` |

---

## What the launch path does

`hermes jarvis launch` (and the installer's `--jarvis-launch`) runs, in order:

1. **Runtime check** — MUSE imports and `handle()` works.
2. **Model bootstrap** — detects what's runnable and writes a free-first
   routing policy (see below).
3. **Memory init** — creates `${HERMES_HOME}/jarvis_prime/` with
   owner-only (`0700`) permissions.
4. **Owner gate** — verifies the exact authorization phrase is enforced.
5. **Emergency stop** — verifies stop clears gates, branch leases, and
   autonomy.
6. **Slash commands** — verifies the activation skill is present.
7. **Worker detection** — detects Claude Code / Codex (detection only).
8. **Launch doctor** — full launch-readiness verification.

It ends by printing exactly how to start, invoke, verify, and stop.

---

## The free-first route order

`hermes models bootstrap --free-first --jarvis` writes a routing policy to
`${HERMES_HOME:-~/.hermes}/jarvis_prime/model_policy.json`. Routes are
ordered free first:

1. **`local_oss`** — local runtimes: Ollama, llama.cpp, vLLM, LM Studio.
2. **`hosted_free_or_user_configured_oss`** — open-route providers you
   already configured (OpenRouter, Hugging Face, Nous, Novita, NIM, …).
   Detected **only** when a key is already present; never requested or
   stored.
3. **`claude_code_worker`** — the official Claude Code CLI (builder lane).
4. **`codex_worker`** — the official Codex CLI (reviewer / bounded-fix lanes).
5. **`paid_api_explicit_only`** — closed paid APIs. **Disabled** unless you
   explicitly opt in (see below).

Model *choices* (for local reasoning, local coding, embeddings) come from
the OSS model brain catalog (`docs/ai-intelligence/oss-model-catalog.yaml`)
— the single source of truth.

### Bootstrap flags

| Flag | Effect |
|---|---|
| `--free-first` | Order free/OSS routes before paid (default). |
| `--jarvis` | Write the MUSE model policy (default). |
| `--dry-run` | Plan only — write nothing, pull nothing. |
| `--no-pull` | Never call the local model pull command. |
| `--force` | Also pull larger default local models. |
| `--local-only` | Configure local routes only (no hosted/worker/paid). |
| `--json` | Machine-readable output. |

---

## Local model runtime setup

For a fully local, free setup, install **Ollama** (https://ollama.com).
The bootstrap detects it automatically and enables the `local_oss` route.

Pull a small default model sized for common hardware:

```bash
ollama pull deepseek-r1:8b      # local reasoning (≈5 GB)
```

The installer's `--jarvis-launch` runs the bootstrap with `--no-pull` so an
unattended `curl | bash` never downloads multi-GB models behind your back —
you pull on demand.

### What happens if Ollama is missing?

Nothing breaks. A missing local runtime is a **warning, not a failure**.
MUSE falls back to whatever hosted/worker routes you've configured. The
launch doctor still reports **LAUNCH READY** — local runtimes are an
optional capability, not a launch blocker.

---

## How Claude Code and Codex are used

Claude Code and Codex are **worker lanes**, used through their own official
CLIs and your existing subscription/session:

| Lane | Tool | Role | Edits branch? |
|---|---|---|---|
| Claude Code Builder | `claude` | builder | yes |
| Codex Reviewer | `codex` | reviewer | no (reads the builder's patch) |
| Codex Bounded Fix Worker | `codex` | bounded fix | yes |

Rules enforced by `hermes_cli/jarvis_prime/worker_registry.py` +
`worker_locks.py`:

- **Detection only.** MUSE checks whether the official CLI is on `PATH`.
  It never scrapes credentials, reads session tokens, or asks for API keys.
- **No subscription abuse.** Execution goes through the tool's own CLI /
  session. Hermes never bypasses subscription boundaries.
- **Single editor per branch.** Claude Code and Codex can never edit the
  same branch at once — an editing lane takes a time-boxed branch *lease*;
  a different tool requesting the same branch is refused. Crashed leases
  expire (TTL) so a branch never wedges.
- **Reviewer consumes builder output.** The Codex reviewer reads the Claude
  Code builder's patch/diff as context — it does not edit in parallel.

A handoff to a lane is a structured **handoff packet**: mission, repo root,
branch, risk class, allowed files, forbidden actions, acceptance criteria,
verification commands, rollback plan, and owner-gated actions.

---

## What "paid API explicit opt-in" means

Detecting a paid key (e.g. `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`) does
**not** enable paid routing. The paid route stays disabled until you
explicitly opt in:

```bash
export HERMES_JARVIS_ENABLE_PAID=1
hermes models bootstrap --free-first --jarvis
```

The free-first launch path requires **no** paid API key. The launch
doctor's `no_paid_dependency` check fails if a free/local-only path ever
depends on a paid route.

---

## Emergency stop

```bash
/jarvis stop
# or, dependency-free:
python -m hermes_cli.jarvis_prime stop
```

Stop clears every pending owner gate, releases all worker branch leases,
disables the proactive tick, and journals a STOP record to memory.

---

## Rollback

- **Model policy:** delete `${HERMES_HOME}/jarvis_prime/model_policy.json`
  and re-run `hermes models bootstrap` (or restore the prior file).
- **A worker change:** revert the branch the lane built on
  (`git revert` / `git checkout`). Branch leases auto-expire.
- **Install:** the installer never deletes your data dir; re-run the
  installer or `uv pip install -e '.[all]'` to repair.

---

## Launch doctor

```bash
hermes doctor --jarvis-launch          # human-readable
hermes doctor --jarvis-launch --json   # machine-readable
```

It verifies: package + CLI import, MUSE import, `python -m
hermes_cli.jarvis_prime`, memory dir + permissions, owner-gate phrase,
emergency stop, model brain, model policy, local runtime detection,
Claude Code / Codex worker detection, the installer one-click path, the
no-paid-dependency invariant, and Termux compatibility.

Exit code is non-zero **only** on a hard launch blocker. Missing optional
runtimes/workers are warnings.

---

## Termux / Android notes

- The whole launch stack (`model_bootstrap`, `worker_locks`,
  `worker_registry`, `launch`, `launch_doctor`) is **stdlib-only at import
  time** — it loads on Termux and in slim CI images.
- The dependency-free CLI surface is available as
  `python -m hermes_cli.jarvis_prime {bootstrap,launch,launch-doctor,stop}`
  when the full `hermes` console script isn't on `PATH`.
- `${HERMES_HOME}` is honored everywhere; file permission tightening is
  best-effort (a no-op where the platform can't `chmod`).
- The installer keeps the Termux path intact and does not pull models in
  unattended mode.
