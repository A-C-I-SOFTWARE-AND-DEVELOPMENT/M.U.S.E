# M.U.S.E. private/local security — in plain English

M.U.S.E. can run entirely on your own machine, without sending a byte to
a cloud provider. That's a great posture for a personal agent. It is
*not* the same thing as "no security needed". This doc explains, in
plain English, why security still matters when the repo is private,
the model is local, and the user is "just me".

## Why bother securing a private repo?

Five reasons that hold even when nothing leaves your laptop.

1. **Your laptop is on the internet.** Browser tabs, email clients,
   the apps you installed last week — any one of them can read files
   the user account can read. A `.env` with your `OPENAI_API_KEY` or
   `SUPABASE_SERVICE_ROLE_KEY` in it is a juicy target for any rogue
   process that ever runs as you. M.U.S.E. does not stop that — but it
   stops *M.U.S.E. itself* from making the leak worse, and it makes the
   smaller things (logs, screenshots, paste buffers) safer.

2. **You're going to share something eventually.** A bug report. A
   screenshot. A "look at this weird trace" Slack message. The
   redactor is for the moment you forget the trace had a token in it.

3. **The agent is connected to high-impact systems.** M.U.S.E. can
   ``git push``, deploy to Vercel, run Supabase migrations, open a
   public tunnel. None of those care that your repo is private. A
   confused model with one bad command on the loose can cost you a
   production database. The approval policy is a brake the agent
   cannot remove on its own.

4. **The LLM is an untrusted input source.** Even your local model.
   The model can be steered by anything in its context — a web page
   it fetched, an inbound email, the contents of a PR comment, the
   contents of a file you asked it to summarise. Treat its output
   like input from a stranger.

5. **You will forget what you committed.** Git history is forever.
   A secret pushed to a private repo and rotated five minutes later
   still exists in the reflog and on every fork. The scanner exists
   so that "forever" gets a chance to be caught at the diff stage.

## What M.U.S.E. treats as a real boundary

The only security boundary against an adversarial LLM is the
operating system. See [`SECURITY.md`](../../SECURITY.md) §2.2.

That means:

- The approval policy reduces *accident* blast radius.
- The secret scanner reduces *accident* leak surface.
- Neither contains a determined attacker who has compromised the
  model.

For real containment, run M.U.S.E. inside a sandbox (Docker, OpenShell,
firejail). The private/local mode plays nicely with all of them.

## What "private/local" mode actually changes

When you flip M.U.S.E. into private/local mode (see
[`docs/orchestration/private-local-mode.md`](../orchestration/private-local-mode.md)):

| Concern                  | Change                                                                                                                            |
|--------------------------|-----------------------------------------------------------------------------------------------------------------------------------|
| LLM provider             | All cloud providers disabled. Only `llama.cpp`, `vLLM`, `Ollama`, or an on-prem Nous Portal accepted.                              |
| Network reach            | Outbound limited to loopback by default. LAN access optional.                                                                     |
| Gateway adapters         | Telegram / Discord / Slack / WhatsApp / Signal / Email disabled. Android cockpit reaches M.U.S.E. over LAN or loopback only.        |
| Memory backends          | Honcho Cloud, Mem0 Cloud, Supermemory disabled. Local SQLite only.                                                                |
| Telemetry                | No external metrics endpoints.                                                                                                    |
| Terminal backends        | Modal / Daytona / Vercel Sandbox disabled. `local`, `docker`, `singularity` remain.                                               |

What does *not* change:

- The agent can still run shell commands, write files, and call
  tools — that's the point.
- The agent can still hold credentials in memory. That's why the
  redactor and the approval policy still matter.

## Concrete things to do today

1. **Put your `.env` somewhere git can't reach it.** M.U.S.E. reads
   `~/.hermes/.env` by default — that path is outside any repo. Don't
   put a `.env` *inside* the repo "just for now".
2. **Set `HERMES_AUTONOMY=assisted` when you start.** Move to
   `autonomous` once you've watched a few hours of behavior. Don't
   start at `yolo`. YOLO is for narrow tasks with cheap rollback.
3. **Keep an eye on `~/.hermes/approval.log`.** Every decision the
   policy made is in there, redacted. `tail -f` it during a long
   run.
4. **Rotate secrets you suspect leaked.** Don't try to scrub git
   history — rotate. The leaked one is in someone's reflog already.
5. **Run `git diff --cached | hermes` before pushing.** The CLI hook
   runs `secrets_policy.scan_diff` on the staged diff. If it flags
   something, M.U.S.E. refuses to push and tells you which line.

## Where this all lives

| Module                                  | Role                                                |
|-----------------------------------------|-----------------------------------------------------|
| `hermes_cli/secrets_policy.py`          | What a secret looks like, where one might live, how to redact it. |
| `hermes_cli/approval_policy.py`         | Which proposed actions are safe to run unattended, which need a prompt, which are off the table. |
| `~/.hermes/.env`                        | The one credential file M.U.S.E. reads by default.   |
| `~/.hermes/approval.log`                | Append-only audit of every approval decision.       |
| `docs/security/secrets-management.md`   | The operator-facing how-to.                         |
| `docs/security/autonomous-agent-safety.md` | The "what could go wrong" companion.            |
| `skills/security-architect/SKILL.md`    | The skill M.U.S.E. loads when you ask it to *think* about security. |

## Further reading

- [`SECURITY.md`](../../SECURITY.md) — the trust model and reporting policy.
- [`docs/orchestration/private-local-mode.md`](../orchestration/private-local-mode.md)
  — how to take M.U.S.E. off the network.
- [NVIDIA OpenShell](https://github.com/NVIDIA/OpenShell) — declarative
  sandbox policy for the whole agent process.
