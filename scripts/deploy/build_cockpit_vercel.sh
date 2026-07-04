#!/usr/bin/env bash
# Assemble musehq.io into a static output directory for Vercel.
#
# musehq.io is now the OpenCode-layout cockpit: OpenCode's own chat renderer
# (vendored, MIT, under web/musehq/vendor/opencode) composed into a Solid+Vite
# app (web/musehq) and dressed in the MUSE "Singularity" look. Its composer is
# wired to the repo-root Edge function /api/chat (a real assistant when a
# provider key is set on the server or supplied via BYOK; an honest "pair a
# gateway / add a key" banner otherwise).
#
# The PREVIOUS single-file cockpit (gateway/cockpit/static/cockpit.dc.html) is
# preserved verbatim at /legacy.html so no feature is lost, and every cockpit
# static surface (3D Atlas, Studio, Observatory, legal pages, PWA assets) is
# carried over and linked from the new app's rail.
#
# Output layout (served from the Vercel project root):
#   <out>/index.html          <- the new musehq app (web/musehq/dist)
#   <out>/assets/*            <- the app's hashed JS/CSS bundles
#   <out>/sw.js               <- service-worker migration kill-switch
#   <out>/legacy.html         <- the previous cockpit (cockpit.dc.html)
#   <out>/vendor/*            <- React UMD, dc-runtime, three.js (legacy + atlas)
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
mkdir -p "$OUT/vendor" "$OUT/atlas"

# ---------------------------------------------------------------------------
# 1. Build the new musehq app (OpenCode chat layout + MUSE look).
# ---------------------------------------------------------------------------
echo "Building $APP …"
if [ -f "$APP/package-lock.json" ]; then
  npm --prefix "$APP" ci
else
  npm --prefix "$APP" install
fi
npm --prefix "$APP" run build

# The Vite build (including public/sw.js) becomes the site root.
cp -R "$APP/dist/." "$OUT/"

# ---------------------------------------------------------------------------
# 2. Preserve the previous cockpit verbatim at /legacy.html. Its asset refs
#    (vendor/, atlas/, icon-180.png, manifest.webmanifest) are relative, so it
#    reuses the root-level copies assembled below — no duplication.
# ---------------------------------------------------------------------------
cp "$SRC/cockpit.dc.html" "$OUT/legacy.html"

# ---------------------------------------------------------------------------
# 3. Installable-PWA assets (shared by the new app and legacy cockpit).
#    The new app ships its own service worker (public/sw.js, a migration
#    kill-switch), so we do NOT copy the old $SRC/sw.js.
# ---------------------------------------------------------------------------
cp "$SRC/manifest.webmanifest"  "$OUT/manifest.webmanifest"
cp "$SRC/icon.svg"              "$OUT/icon.svg"
cp "$SRC/icon-180.png"          "$OUT/icon-180.png"
cp "$SRC/icon-192.png"          "$OUT/icon-192.png"
cp "$SRC/icon-512.png"          "$OUT/icon-512.png"
cp "$SRC/icon-maskable-512.png" "$OUT/icon-maskable-512.png"

# ---------------------------------------------------------------------------
# 4. Vendored runtime for the legacy cockpit + Atlas (React UMD, dc-runtime, three).
# ---------------------------------------------------------------------------
cp "$SRC/vendor/react.production.min.js"      "$OUT/vendor/"
cp "$SRC/vendor/react-dom.production.min.js"  "$OUT/vendor/"
cp "$SRC/vendor/dc-runtime.js"                "$OUT/vendor/"
cp "$SRC/vendor/three.module.min.js"          "$OUT/vendor/"
cp "$SRC/vendor/three.core.min.js"            "$OUT/vendor/"

# ---------------------------------------------------------------------------
# 5. Cockpit static surfaces the new app links to (Atlas, Studio, Observatory).
# ---------------------------------------------------------------------------
# Copy the whole atlas/ directory — Studio embeds atlas/muse-atlas.html, so a
# partial copy 404s that iframe.
cp "$SRC/atlas/"* "$OUT/atlas/"

for f in studio.html studio-support.js observatory.html observatory.css observatory.js \
         observatory-demo.html observatory-demo.json tokens.css cockpit.css; do
  if [ -f "$SRC/$f" ]; then cp "$SRC/$f" "$OUT/$f"; fi
done

# Studio references styles/tokens.css + styles/cockpit.css (Observatory + the
# legacy cockpit reference them at root, so keep both locations).
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

echo "musehq.io assembled into $OUT/ (new app at /, legacy cockpit at /legacy.html)"
ls "$OUT"
