# Archive Policy

Use this directory for historical drafts, planning notes, obsolete prompts, and superseded implementation ideas that should not remain in the active setup path.

## Archive instead of delete when

- The file explains why a decision was made.
- The file contains useful historical context.
- The file contains product direction that may become useful later.
- The file is outdated but not obviously junk.

## Delete instead of archive when

- The file is generated junk with no operational value.
- The file is duplicated exactly elsewhere.
- The file contains no decision, context, or reusable material.

## Secret handling

Do not archive real secrets. If a file contains a committed token, API key, OAuth credential, password, signing key, or private key:

1. Remove the secret value.
2. Document the affected variable or file name without exposing the value.
3. Rotate the credential in the provider dashboard.
4. Consider history cleanup if the exposed value is real.

## Naming convention

Use a date prefix when moving material here:

```text
YYYY-MM-DD-original-file-name.md
```

Add a short note at the top of each archived file explaining why it was archived and what replaced it.
