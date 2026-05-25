# Rule: Secrets

- Never print secret values, tokens, keys, or `.env` contents to the
  transcript.
- Reference secrets by environment variable name only
  (e.g. `SUPABASE_SERVICE_ROLE_KEY`), never by value.
- If `.env.example` accidentally contains a real value, redact it before
  pasting and tell the owner to rotate.
- New required secrets are documented in `.env.example` by name only, with
  a one-line description.
- Never commit `.env`, key files, or credential JSON.
- Never include a real secret in a commit message, PR body, or comment.
