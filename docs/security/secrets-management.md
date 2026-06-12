# Secrets management

A short, practical guide to where M.U.S.E. reads secrets from, what
counts as a secret, and how to keep them out of places they don't
belong. The code-side reference is
[`hermes_cli/secrets_policy.py`](../../hermes_cli/secrets_policy.py).

## Where M.U.S.E. reads secrets from

In priority order (first match wins):

1. **`~/.hermes/.env`** — the canonical operator-owned file. It is
   gitignored. The plugin layer loads it; the agent never sees the
   raw values.
2. **`$HERMES_HOME/.env`** — same file, different path, when you've
   pointed M.U.S.E. at a custom home directory.
3. **Process environment** — anything already in `os.environ` when
   M.U.S.E. started. This is how CI, Docker, and OS-keychain helpers
   inject values.
4. **OS keychain** when available:
   - macOS Keychain via `/usr/bin/security`
   - Linux libsecret (GNOME Keyring, KWallet bridge)
   - Windows Credential Manager (DPAPI) — used by the Windows remote worker
5. **Android secure storage** — Android EncryptedSharedPreferences,
   accessed indirectly through the M.U.S.E. Android app.
6. **`config.yaml` `${VAR}` references** — these are *names*, not
   values. The resolver looks them up against one of the sources
   above.

The agent process is never handed the raw values. Plugins request a
secret by **name**; the loader returns the value (or `None`); the
LLM sees a sentinel like `<redacted:OPENAI_API_KEY>`.

## What counts as a secret

The detector in `secrets_policy.py` flags four things:

| Category         | Example                                                |
|------------------|--------------------------------------------------------|
| Env name pattern | `OPENAI_API_KEY`, `*_TOKEN`, `*_PRIVATE_KEY`           |
| Known prefix     | `sk-`, `sk-ant-`, `ghp_`, `ghs_`, `xoxb-`, `AKIA…`     |
| High entropy     | ≥ 32 chars, mixed character classes                    |
| PEM block        | `-----BEGIN ... PRIVATE KEY-----` ... `-----END ...`   |

The detector is conservative on purpose. False positives in a
redactor are recoverable. A single leaked API key is not.

## Rules — what M.U.S.E. will and won't do

1. **Never commit `.env`.** The repo `.gitignore` covers `.env`,
   `.env.*`, and `~/.hermes/.env`. The pre-commit hook runs
   `secrets_policy.scan_diff` on the staged diff and refuses to
   commit when a secret is found.
2. **Never print a raw secret in logs.** All log lines pass through
   `redact()`. Loggers receive `<redacted:KIND>` instead of the
   value. If you see a raw secret in a log, that's a bug — report
   it.
3. **Redact before sending anywhere.** When the orchestrator
   serialises a job artifact, worker output, or job ledger entry,
   it routes through `redact_env_dict()` for env-shaped maps and
   `redact()` for free text.
4. **Require approval before remote secret transfer.** Sending a
   credential to a remote worker is `Action.REMOTE_SECRET_TRANSFER`
   — see [`autonomous-agent-safety.md`](autonomous-agent-safety.md).
   The default policy denies it without an explicit target, and
   prompts for confirmation even with one.
5. **Refuse to commit on detection.** `assert_not_committable()` is
   called by the publisher path; it raises `SecretLeakError` and
   the publish aborts.

## What the scan covers

The scanner runs on five surfaces:

| Surface                          | Why it matters                                                |
|----------------------------------|---------------------------------------------------------------|
| Staged git diff                  | Catches the moment before a commit lands.                     |
| Unstaged git diff                | Catches it before you `git add -p`.                           |
| Job artifacts                    | Worker output files written under `~/.hermes/jobs/<id>/`.     |
| Logs                             | Stdout / stderr captured during a run.                        |
| Worker outputs                   | Any string returned from a worker before it joins the ledger. |

The scanner returns `Finding` objects — kind, location, line,
excerpt. The excerpt is already redacted; it is safe to surface in a
chat reply or a ledger entry.

## How to add a secret you've just created

1. Put it in `~/.hermes/.env`:
   ```bash
   echo "NEW_PROVIDER_API_KEY=…" >> ~/.hermes/.env
   chmod 600 ~/.hermes/.env
   ```
2. (Optional but recommended) Also put it in your OS keychain — that
   way, if the file ever leaks, the keychain copy is independent.
3. Restart M.U.S.E. or run `/reload-skills` to pick the value up.
4. Test that it loaded with: `muse doctor` (the line "credentials
   loaded" lists names, never values).

## How to know what's loaded right now

```text
muse doctor
```

The doctor output lists every credential **name** the running process
sees, alongside whether the value passed the ASCII sanity check
(see `hermes_cli/env_loader.py`). It never prints a value.

## How to rotate a secret you suspect leaked

1. Rotate at the provider first. The leaked value is gone the moment
   the new one exists.
2. Update `~/.hermes/.env` with the new value.
3. Restart M.U.S.E..
4. `grep` your local git reflog and any backups for the old value so
   you know how exposed it was. Don't try to rewrite history on a
   public mirror — assume it's archived.

## Where the policy doesn't help

- **The agent's own RAM.** Anything resident in the M.U.S.E. Python
  process can be dumped with a debugger. There's no defence at this
  layer; OS-level isolation is the only answer.
- **A compromised local model.** If the model has been pre-poisoned
  to exfiltrate secrets via tool-use, the redactor won't stop it
  because the model already saw the raw value. Don't load models
  from untrusted sources.
- **A typo'd env name.** `OPENAI_AKI_KEY` is not flagged as a
  credential by name; the value might still be flagged by entropy,
  but please type carefully.

## Related

- [`muse-private-local-security.md`](muse-private-local-security.md)
  — the high-level "why".
- [`autonomous-agent-safety.md`](autonomous-agent-safety.md) — the
  approval-policy companion.
- [`SECURITY.md`](../../SECURITY.md) — the trust model.
