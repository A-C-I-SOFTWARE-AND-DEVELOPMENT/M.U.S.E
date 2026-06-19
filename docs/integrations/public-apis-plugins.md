# Free public-API plugins (weather, finance, news, timeutil)

Four native muse plugins wire a handful of **free public APIs** into the
agent so muse can answer everyday questions — what's the weather,
what's BTC at, what's in the news, what time is it for my team in Tokyo —
without you standing up any infrastructure. Three of the four need **no API
key at all**; only one optional news source needs a key.

These follow the same native-plugin pattern as
[`plugins/github_assistant/`](../github-integration.md): a folder under
`plugins/`, an `enabled` switch in `~/.hermes/config.yaml`, and a thin
read-only client. They all share one redacting, host-pinned, size-capped
HTTP helper at [`tools/http_client.py`](../../tools/http_client.py).

## What each plugin does

| Plugin | Tools | Data source | Key required? |
|---|---|---|---|
| `weather` | `weather_geocode`, `weather_current`, `weather_forecast` | [Open-Meteo](https://open-meteo.com) | **No** |
| `finance` | `crypto_price`, `currency_convert`, `stock_quote` | CoinGecko · Frankfurter (ECB) · Stooq | **No** |
| `news` | `news_top` | [Hacker News](https://github.com/HackerNews/API) | **No** |
| `news` | `news_headlines` | [NewsAPI.org](https://newsapi.org) | Optional (`NEWSAPI_KEY`) |
| `timeutil` | `time_now`, `world_clock`, `public_holidays` | TimeAPI.io · [Nager.Date](https://date.nager.at) | **No** |

Every tool is **read-only** (HTTP GET only — no writes, no owner-gate
needed). Each plugin's client pins its hostnames; the shared HTTP helper
refuses any request to a host outside that allowlist, caps response bodies
(256 KB), retries once on a transient error, and strips secret-shaped
substrings from any error before it reaches the model or the logs.

## Enable them

Standalone plugins are **opt-in** — they ship disabled so they never add
tools or network calls you didn't ask for. Turn on the ones you want in
`~/.hermes/config.yaml`:

```yaml
weather:
  enabled: true
finance:
  enabled: true
news:
  enabled: true
timeutil:
  enabled: true
```

Then make muse load them (same as any bundled standalone plugin):

```bash
muse plugins enable weather finance news timeutil
# or, inside an interactive session, after editing config:
/reload-skills        # picks up newly-enabled plugins
```

When a plugin's `enabled` flag is `false`, its `check_fn` hides every tool
from the model — the agent won't see them at all.

## The one optional key: NewsAPI

`news_top` (Hacker News) works with zero setup. `news_headlines` adds
general-news headlines and search via NewsAPI.org, which needs a free key.
**Until the key is set, `news_headlines` is hidden from the model** (its
`check_fn` requires both `news.enabled` and `NEWSAPI_KEY`). To enable it,
get a key at <https://newsapi.org> and add it to `~/.hermes/.env`:

```bash
# ~/.hermes/.env
NEWSAPI_KEY=your_newsapi_key_here
```

The key is read at call time, sent as the `X-Api-Key` **header** (never in
a URL/query string), passed to the HTTP helper's redaction list, and is
never returned to the model or written to logs.

## What the live calls actually do

Honest description of network behaviour, so nothing here is overstated:

- **weather** — `weather_geocode` hits `geocoding-api.open-meteo.com`;
  `weather_current` / `weather_forecast` hit `api.open-meteo.com`. No auth.
- **finance** — `crypto_price` → `api.coingecko.com/api/v3/simple/price`
  (free public tier, rate-limited by CoinGecko); `currency_convert` →
  `api.frankfurter.app` (ECB reference rates, updated each working day —
  not a live trading feed); `stock_quote` → `stooq.com` CSV, which is
  **delayed** end-of-day/intraday data, not real-time.
- **news** — `news_top` → `hacker-news.firebaseio.com`; `news_headlines`
  → `newsapi.org` (free tier is limited and may be delayed).
- **timeutil** — `time_now` / `world_clock` → `timeapi.io`;
  `public_holidays` → `date.nager.at`.

All are best-effort public services. On timeout or error the tools return a
structured `{"success": false, "error": ...}` envelope rather than raising,
so a flaky upstream never breaks the agent's turn loop.

## Adding more public APIs

To add another free API, copy any of these four plugin folders as a
template — they are deliberately small and identical in shape
(`plugin.yaml` + `__init__.py` + `config.py` + `client.py` + `tools.py`,
with mirrored tests under `tests/plugins/<name>/`). Reuse
`tools.http_client.PublicApiClient` for the redaction / allowlist / cap /
retry plumbing; pin your new host(s) in the client's `ALLOWED_HOSTS`.
