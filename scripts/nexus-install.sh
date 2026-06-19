#!/data/data/com.termux/files/usr/bin/env bash
# nexus-install.sh — idempotent Nexus APK installer for Termux on Android.
#
# Strategy:
#   1. Locate the newest nexus-android*.apk in /sdcard/Download/ or ~/storage/downloads/.
#   2. Best-effort scrape package id + versionName from the binary AndroidManifest.xml.
#   3. Copy to $HOME/nexus.apk to escape Samsung's file-context sandbox
#      (pm install on /sdcard fails with SELinux file-context errors on OneUI).
#   4. Hand off to termux-open --chooser, which surfaces the system installer.
#
# Exit codes:
#   0  success (installer dialog launched)
#   2  no APK found
#   3  termux-open missing
#   4  copy failed

set -euo pipefail

SEARCH_DIRS=(
  "/sdcard/Download"
  "${HOME}/storage/downloads"
)

# --- 1. Locate newest matching APK -------------------------------------------
# Use null-delimited find to survive filenames with spaces and parens like
# "nexus-android (5).apk".
newest_apk=""
newest_mtime=0

for dir in "${SEARCH_DIRS[@]}"; do
  [ -d "$dir" ] || continue
  while IFS= read -r -d '' candidate; do
    # %T@ = mtime as epoch float; sort by it.
    mtime=$(stat -c '%Y' "$candidate" 2>/dev/null || echo 0)
    if [ "$mtime" -gt "$newest_mtime" ]; then
      newest_mtime="$mtime"
      newest_apk="$candidate"
    fi
  done < <(find "$dir" -maxdepth 1 -type f -iname 'nexus-android*.apk' -print0 2>/dev/null)
done

if [ -z "$newest_apk" ]; then
  cat >&2 <<EOF
error: no nexus-android*.apk found in any of:
  ${SEARCH_DIRS[*]}

Download the APK first (CI release asset) and place it in /sdcard/Download/.
EOF
  exit 2
fi

apk_size=$(stat -c '%s' "$newest_apk" 2>/dev/null || echo "?")
printf 'apk:   %s\n' "$newest_apk"
printf 'size:  %s bytes\n' "$apk_size"

# --- 2. Best-effort AXML scrape ----------------------------------------------
# AndroidManifest.xml inside an APK is binary AXML. Strings are stored as
# UTF-16LE. We extract every printable UTF-16LE run, then grep for a
# package-shaped token and a versionName-shaped token. This is approximate
# but reliable enough for an install-confirmation print.
if command -v python3 >/dev/null 2>&1; then
  python3 - "$newest_apk" <<'PY' || true
import re, sys, zipfile

apk_path = sys.argv[1]
try:
    with zipfile.ZipFile(apk_path) as zf:
        with zf.open("AndroidManifest.xml") as f:
            blob = f.read()
except Exception as exc:
    print(f"pkg:   (axml read failed: {exc})")
    sys.exit(0)

# Scan for UTF-16LE printable runs: byte pairs (c, 0x00) where c is printable.
strings = []
i = 0
n = len(blob)
cur = []
while i + 1 < n:
    lo, hi = blob[i], blob[i + 1]
    if hi == 0x00 and 0x20 <= lo <= 0x7e:
        cur.append(chr(lo))
        i += 2
    else:
        if len(cur) >= 3:
            strings.append("".join(cur))
        cur = []
        i += 1
if len(cur) >= 3:
    strings.append("".join(cur))

pkg_re = re.compile(r"^[a-z][a-z0-9_.]*\.[a-z0-9_]+$")
# versionName is typically a dotted/dashed alnum token; pick the value that
# appears in the strings table right after the literal "versionName" key.
pkg_id = next((s for s in strings if pkg_re.match(s) and "android" not in s.split(".")[0]), None)
if pkg_id is None:
    pkg_id = next((s for s in strings if pkg_re.match(s)), None)

version = None
for idx, s in enumerate(strings):
    if s == "versionName":
        # Heuristic: the next few strings include the actual value.
        for cand in strings[idx + 1: idx + 8]:
            if re.match(r"^[0-9][0-9A-Za-z._\-]*$", cand):
                version = cand
                break
        if version:
            break

print(f"pkg:   {pkg_id or '(unknown)'}")
print(f"ver:   {version or '(unknown)'}")
PY
else
  echo "pkg:   (python3 not available — skipping AXML scrape)"
fi

# --- 3. Copy to $HOME to escape Samsung file-context sandbox -----------------
dest="${HOME}/nexus.apk"
if ! cp -f "$newest_apk" "$dest"; then
  echo "error: failed to copy APK to $dest" >&2
  exit 4
fi
printf 'staged: %s\n' "$dest"

# --- 4. Hand off to system installer -----------------------------------------
if ! command -v termux-open >/dev/null 2>&1; then
  cat >&2 <<EOF

error: termux-open is not installed.

Fix:
  pkg install termux-tools

Fallback (manual):
  Open Samsung "My Files" → Internal storage → Download →
  tap nexus-android*.apk and confirm Install.
EOF
  exit 3
fi

termux-open --chooser --content-type application/vnd.android.package-archive "$dest"

cat <<EOF

Nexus APK handed to the system package installer.

Next:
  1. Tap "Install" on the Android dialog that just appeared.
     (If a "Package installer" / "Files" chooser shows first, pick
      "Package installer".)
  2. When the install completes, open the Nexus app once so it can
     create its data directory and request needed permissions.
  3. Back in Termux, run:
       scripts/nexus-connect.sh

Done.
EOF
