#!/usr/bin/env bash
# Assemble the muse Cockpit into a static output directory for Vercel.
#
# The public Vercel deployment serves the cockpit (the imported "Singularity"
# Claude Design — gateway/cockpit/static/cockpit.dc.html) wearing its segregated
# nav, with its chat composer wired to the repo-root Edge function /api/chat
# (a real assistant when a provider key is set on the server; an honest
# "pair a gateway" message when no /api is present). The dc-runtime + vendored
# React render the design offline; the 3D Atlas and three.js are vendored too.
#
# Output layout (served from the Vercel project root):
#   <out>/index.html         <- the cockpit page (cockpit.dc.html)
#   <out>/vendor/*           <- React UMD, dc-runtime, three.js (shared w/ atlas)
#   <out>/atlas/*            <- the 3D Systems Atlas (uses ../vendor/three)
#
# The Edge API functions live at the repo-root /api and are discovered by Vercel
# independently of this output directory.
set -euo pipefail

OUT="${1:-cockpit-dist}"
SRC="gateway/cockpit/static"

rm -rf "$OUT"
mkdir -p "$OUT/vendor" "$OUT/atlas"

# The cockpit page itself.
cp "$SRC/cockpit.dc.html" "$OUT/index.html"

# Installable-PWA assets: web app manifest, app icon, and the service worker, so
# the in-app "Install app" button can add the cockpit to the device home screen
# (a manifest + a same-origin service worker are the browser install criteria).
# The SW only caches the static shell — never /api or gateway calls.
cp "$SRC/manifest.webmanifest" "$OUT/manifest.webmanifest"
cp "$SRC/icon.svg"             "$OUT/icon.svg"
# PNG icon set: apple-touch-icon (iOS ignores SVG) + manifest any/maskable.
cp "$SRC/icon-180.png"          "$OUT/icon-180.png"
cp "$SRC/icon-192.png"          "$OUT/icon-192.png"
cp "$SRC/icon-512.png"          "$OUT/icon-512.png"
cp "$SRC/icon-maskable-512.png" "$OUT/icon-maskable-512.png"
cp "$SRC/sw.js"                "$OUT/sw.js"

# Vendored runtime: React (UMD) + dc-runtime, plus three.js shared with the atlas.
cp "$SRC/vendor/react.production.min.js"      "$OUT/vendor/"
cp "$SRC/vendor/react-dom.production.min.js"  "$OUT/vendor/"
cp "$SRC/vendor/dc-runtime.js"                "$OUT/vendor/"
cp "$SRC/vendor/three.module.min.js"          "$OUT/vendor/"
cp "$SRC/vendor/three.core.min.js"            "$OUT/vendor/"

# The 3D Systems Atlas (imports ../vendor/three.module.min.js — no duplication).
cp "$SRC/atlas/index.html"            "$OUT/atlas/"
cp "$SRC/atlas/style.css"             "$OUT/atlas/"
cp "$SRC/atlas/app.js"                "$OUT/atlas/"
cp "$SRC/atlas/architecture_data.js"  "$OUT/atlas/"

# Build-time GitHub releases snapshot (best-effort; the page has a baked
# fallback, so a network failure here never fails the build).
if command -v node >/dev/null 2>&1; then
  node scripts/deploy/gen_releases_json.mjs "$OUT" || true
else
  echo "node not found — skipping releases.json (page uses baked fallback)"
fi

# Allow indexing of the public site (commercial SEO baseline) + sitemap.
printf 'User-agent: *\nAllow: /\nSitemap: https://musehq.io/sitemap.xml\n' > "$OUT/robots.txt"

# Static SEO / social assets, copied if present (sitemap + Open Graph image).
if [ -f "$SRC/sitemap.xml" ]; then cp "$SRC/sitemap.xml" "$OUT/sitemap.xml"; fi
if [ -f "$SRC/og.png" ]; then cp "$SRC/og.png" "$OUT/og.png"; fi

# Commercial baseline: legal pages (linked from the page footer + account panel).
if [ -f "$SRC/terms.html" ]; then cp "$SRC/terms.html" "$OUT/terms.html"; fi
if [ -f "$SRC/privacy.html" ]; then cp "$SRC/privacy.html" "$OUT/privacy.html"; fi

echo "muse Cockpit assembled into $OUT/"
ls -R "$OUT"
