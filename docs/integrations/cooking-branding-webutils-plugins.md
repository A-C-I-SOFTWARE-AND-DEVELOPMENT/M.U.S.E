# Cooking + branding + utilities plugins (cooking, branding, webutils)

Three native M.U.S.E. plugins that add recipes/food, design/branding, and small
web utilities over free public APIs. They follow the
[public-API plugin](public-apis-plugins.md) pattern and reuse the shared,
host-pinned, redacting HTTP helper at
[`tools/http_client.py`](../../tools/http_client.py).

## What's added

| Plugin | Tools | Source | Key |
|---|---|---|---|
| `cooking` | `recipe_search`, `recipe_lookup`, `cocktail_search`, `food_product` | TheMealDB · TheCocktailDB · Open Food Facts | **No** |
| `branding` | `color_info`, `color_scheme`, `placeholder_image` | TheColorAPI · Lorem Picsum | **No** |
| `branding` | `stock_photo_search` | Unsplash | Optional (`UNSPLASH_ACCESS_KEY`) |
| `branding` | `google_fonts` | Google Fonts | Optional (`GOOGLE_FONTS_API_KEY`) |
| `webutils` | `qr_code`, `ip_info`, `public_ip`, `sunrise_sunset` | goQR · ipapi.co · ipify · SunriseSunset.io | **No** |

`placeholder_image` and `qr_code` **build a URL locally and make no network
request** — they return a ready-to-embed image URL, never binary data.

## Enable

Standalone plugins are opt-in. In `~/.hermes/config.yaml`:

```yaml
cooking:
  enabled: true
branding:
  enabled: true
webutils:
  enabled: true
```

Then `muse plugins enable cooking branding webutils` (or `/reload-skills`).

## Optional keys (branding)

`color_info`, `color_scheme`, and `placeholder_image` work with zero setup.
Two branding tools are key-gated and **hidden from the model until their key is
set** in `~/.hermes/.env`:

```bash
# ~/.hermes/.env
UNSPLASH_ACCESS_KEY=your_unsplash_access_key   # enables stock_photo_search
GOOGLE_FONTS_API_KEY=your_google_fonts_key     # enables google_fonts
```

Both keys are read at call time, passed to the HTTP helper's redaction list
(Unsplash via an `Authorization: Client-ID` header; Google Fonts via its
required query param), and never returned to the model or logged.

## What the live calls do

- `recipe_search`/`recipe_lookup` → `www.themealdb.com` (public test key `1`);
  `cocktail_search` → `www.thecocktaildb.com`; `food_product` →
  `world.openfoodfacts.org` (`status: 0` → `not_found`).
- `color_info`/`color_scheme` → `www.thecolorapi.com`; `placeholder_image`
  builds a `picsum.photos` URL.
- `stock_photo_search` → `api.unsplash.com`; `google_fonts` →
  `www.googleapis.com/webfonts/v1`.
- `qr_code` builds an `api.qrserver.com` URL; `ip_info` → `ipapi.co`;
  `public_ip` → `api.ipify.org`; `sunrise_sunset` → `api.sunrisesunset.io`.

All are best-effort public services. On timeout/error the tools return a
structured `{"success": false, "error": ...}` envelope rather than raising.
Hosts are pinned (allowlist re-checked on every redirect hop) and errors are
secret-redacted.
