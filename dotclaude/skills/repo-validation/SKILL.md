---
name: repo-validation
description: Discover and run the repo's actual validation commands — install, typecheck, lint, test, build, secret scan, store-readiness — and report results with evidence. Use as the validation step of any implementation, or standalone to answer "is this branch clean?".
---

# Repo Validation

## Use when

- After any code change, before claiming done.
- Standalone, to answer "is this branch clean right now?".
- Before opening a PR.

## Procedure

1. **Discover** — read `package.json` `scripts`, Makefile, `pyproject.toml`
   `[tool]` sections, `.github/workflows/`, `noxfile.py`, `tox.ini`,
   `Justfile`. List the commands you actually find. Do not invent.
2. **Order** — install → typecheck → lint → test (unit) → test
   (integration, if present) → build (production) → secret scan (if
   present) → store readiness (if mobile).
3. **Run** each discovered command. Capture exit code and last ~20 lines
   of output. Stop on the first RED gate only if subsequent gates depend
   on it (e.g. build depends on install); otherwise continue and report
   all RED gates at once.
4. **Report** with evidence per gate.

## Output

```
## Repo / branch
## Commands discovered
- install: <command>
- typecheck: <command>
- lint: <command>
- test (unit): <command>
- test (integration): <command or "not present">
- build: <command>
- secret scan: <command or "not present">
- store readiness: <command or "not present">

## Results
| Gate | Result | Evidence |
| --- | --- | --- |
| install | GREEN | <last lines> |
| typecheck | RED | <error excerpt> |
...

## Blockers
## Verdict: ALL GREEN | RED GATES PRESENT
```

## Hard rules

- Never invent a command. If the conventional command is absent, mark the
  gate N-A with reason.
- Never claim GREEN without captured output.
- Never modify the lockfile by hand; if `npm ci` fails because of lockfile
  drift, report it and stop.
