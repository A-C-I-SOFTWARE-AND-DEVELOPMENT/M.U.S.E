#!/usr/bin/env bash
# Assemble musehq.io into a static output directory for Vercel.
#
# Canonical public face = the Singularity cockpit (cockpit.dc.html) — the full
# Muse Omni operations UI (Connect, jobs, approvals, OMNI providers, atlas,
# studio, observatory). The OpenCode-layout Solid chat shell (web/musehq) is
# a secondary surface under /chat/.
#
# Output layout (served from the Vercel project root):
#   <out>/index.html          <- Singularity cockpit (cockpit.dc.html)
#   <out>/legacy.html         <- same cockpit (bookmark / old-link alias)
#   <out>/chat/               <- OpenCode chat shell (web/musehq/dist)
#   <out>/vendor/*            <- React UMD, dc-runtime, three.js
#   <out>/atlas/*             <- the 3D Systems Atlas
#   <out>/studio.html, observatory.html, terms.html, privacy.html, icons, ...
#
# The Edge API functions live at the repo-root /api and are discovered by Vercel
# independently of this output directory.
set -euo pipefail

OUT="${1:-cockpit-dist}"
SRC="gateway/cockpit/static"
APP="web/musehq"

rm -rf "$OUT"
mkdir -p "$OUT/vendor" "$OUT/atlas" "$OUT/chat"

# ---------------------------------------------------------------------------
# 1. Singularity cockpit is the site root (Muse Omni).
# ---------------------------------------------------------------------------
cp "$SRC/cockpit.dc.html" "$OUT/index.html"
# Keep /legacy.html as an alias so old bookmarks and rail links still work.
cp "$SRC/cockpit.dc.html" "$OUT/legacy.html"

# ---------------------------------------------------------------------------
# 2. Build the OpenCode chat shell into /chat/ (secondary surface).
# ---------------------------------------------------------------------------
echo "Building $APP for /chat/ …"
if [ -f "$APP/package-lock.json" ]; then
  npm --prefix "$APP" ci
else
  npm --prefix "$APP" install
fi
# Vite base must be /chat/ so asset URLs resolve under that prefix on Vercel.
MUSEHQ_BASE=/chat/ npm --prefix "$APP" run build
cp -R "$APP/dist/." "$OUT/chat/"

# ---------------------------------------------------------------------------
# 3. Installable-PWA assets (Singularity cockpit at root).
# ---------------------------------------------------------------------------
cp "$SRC/manifest.webmanifest"  "$OUT/manifest.webmanifest"
cp "$SRC/icon.svg"              "$OUT/icon.svg"
cp "$SRC/icon-180.png"          "$OUT/icon-180.png"
cp "$SRC/icon-192.png"          "$OUT/icon-192.png"
cp "$SRC/icon-512.png"          "$OUT/icon-512.png"
cp "$SRC/icon-maskable-512.png" "$OUT/icon-maskable-512.png"
# Prefer the cockpit service worker at root (not the musehq migration SW).
if [ -f "$SRC/sw.js" ]; then
  cp "$SRC/sw.js" "$OUT/sw.js"
fi

# ---------------------------------------------------------------------------
# 4. Vendored runtime for the cockpit + Atlas (React UMD, dc-runtime, three).
# ---------------------------------------------------------------------------
cp "$SRC/vendor/react.production.min.js"      "$OUT/vendor/"
cp "$SRC/vendor/react-dom.production.min.js"  "$OUT/vendor/"
cp "$SRC/vendor/dc-runtime.js"                "$OUT/vendor/"
cp "$SRC/vendor/three.module.min.js"          "$OUT/vendor/"
cp "$SRC/vendor/three.core.min.js"            "$OUT/vendor/"

# ---------------------------------------------------------------------------
# 5. Cockpit static surfaces (Atlas, Studio, Observatory).
# ---------------------------------------------------------------------------
# Copy the whole atlas/ directory — Studio embeds atlas/muse-atlas.html, so a
# partial copy 404s that iframe.
cp "$SRC/atlas/"* "$OUT/atlas/"

for f in studio.html studio-support.js observatory.html observatory.css observatory.js \
         observatory-demo.html observatory-demo.json tokens.css cockpit.css; do
  if [ -f "$SRC/$f" ]; then cp "$SRC/$f" "$OUT/$f"; fi
done

# Studio references styles/tokens.css + styles/cockpit.css (Observatory + the
# cockpit reference them at root, so keep both locations).
mkdir -p "$OUT/styles"
cp "$SRC/tokens.css"  "$OUT/styles/tokens.css"
cp "$SRC/cockpit.css" "$OUT/styles/cockpit.css"

# ---------------------------------------------------------------------------
# 6. Build-time GitHub releases snapshot (best-effort; baked fallback in page).
# ---------------------------------------------------------------------------
if command -v node >/dev/null 2>&1; then
  node scripts/deploy/gen_releases_json.mjs "$OUT" || true
else
  echo "node not found — skipping releases.json (page uses baked fallback)"
fi

# ---------------------------------------------------------------------------
# 7. SEO / social baseline.
# ---------------------------------------------------------------------------
printf 'User-agent: *\nAllow: /\nSitemap: https://musehq.io/sitemap.xml\n' > "$OUT/robots.txt"
if [ -f "$SRC/sitemap.xml" ]; then cp "$SRC/sitemap.xml" "$OUT/sitemap.xml"; fi
if [ -f "$SRC/og.png" ];      then cp "$SRC/og.png"      "$OUT/og.png"; fi
if [ -f "$SRC/terms.html" ];   then cp "$SRC/terms.html"   "$OUT/terms.html"; fi
if [ -f "$SRC/privacy.html" ]; then cp "$SRC/privacy.html" "$OUT/privacy.html"; fi

echo "musehq.io assembled into $OUT/ (Singularity at /, OpenCode chat at /chat/)"
ls "$OUT"
ls "$OUT/chat" | head -20
