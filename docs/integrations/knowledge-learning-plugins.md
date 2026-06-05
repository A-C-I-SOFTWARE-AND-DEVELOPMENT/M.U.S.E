# Knowledge + learning plugins (knowledge, learning)

Two native Hermes plugins that give the agent general-knowledge and learning
lookups over free public APIs. They follow the
[public-API plugin](public-apis-plugins.md) pattern and reuse the shared,
host-pinned, redacting HTTP helper at
[`tools/http_client.py`](../../tools/http_client.py).

## What's added

| Plugin | Tools | Source | Key |
|---|---|---|---|
| `knowledge` | `wikipedia_summary`, `wikipedia_search`, `dictionary_define`, `country_info` | Wikimedia · Free Dictionary · REST Countries | **No** |
| `learning` | `books_search` | Open Library | **No** |
| `learning` | `gutenberg_search` | Project Gutenberg (Gutendex) | **No** |
| `learning` | `quote_random` | ZenQuotes | **No** |
| `learning` | `wolfram_answer` | Wolfram\|Alpha Short Answers | Optional (`WOLFRAM_APP_ID`) |

Every tool is read-only. `gutenberg_search` returns direct download links to
public-domain texts; `books_search` returns Open Library work keys.

## Enable

Standalone plugins are opt-in. In `~/.hermes/config.yaml`:

```yaml
knowledge:
  enabled: true
learning:
  enabled: true
```

Then `hermes plugins enable knowledge learning` (or `/reload-skills`).

## The one optional key: Wolfram|Alpha

`books_search`, `gutenberg_search`, and `quote_random` work with zero setup.
`wolfram_answer` answers factual/computational questions (math, unit
conversions, science, dates) via Wolfram|Alpha's Short Answers API, which needs
a free App ID. **Until the key is set, `wolfram_answer` is hidden from the
model** (its `check_fn` requires both `learning.enabled` and `WOLFRAM_APP_ID`).
Get an App ID at <https://developer.wolframalpha.com> and add it to
`~/.hermes/.env`:

```bash
# ~/.hermes/.env
WOLFRAM_APP_ID=your_app_id_here
```

The App ID is read at call time, passed to the HTTP helper's redaction list,
and never returned to the model or logged.

## What the live calls do

- `wikipedia_summary` → `en.wikipedia.org/api/rest_v1/page/summary/{title}`;
  `wikipedia_search` → `en.wikipedia.org/w/api.php` (action API).
- `dictionary_define` → `api.dictionaryapi.dev` (returns `not_found` on 404).
- `country_info` → `restcountries.com/v3.1/name/{name}`.
- `books_search` → `openlibrary.org/search.json`; `gutenberg_search` →
  `gutendex.com/books`; `quote_random` → `zenquotes.io/api/random`.
- `wolfram_answer` → `api.wolframalpha.com/v1/result` (plain-text answer;
  `not_found` when Wolfram has no short answer).

All are best-effort public services; on timeout/error the tools return a
structured `{"success": false, "error": ...}` envelope rather than raising.
Hosts are pinned (allowlist re-checked on every redirect hop) and any error is
secret-redacted.
