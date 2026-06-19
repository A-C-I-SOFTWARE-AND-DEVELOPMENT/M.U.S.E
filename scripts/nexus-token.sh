#!/data/data/com.termux/files/usr/bin/env bash
# Mint a fresh Nexus Bearer token, write raw to ~/nexus_token.txt
set -euo pipefail

GATEWAY="${NEXUS_GATEWAY:-http://127.0.0.1:8765}"
OUT="${HOME}/nexus_token.txt"

# Retry pair/start in case of rate limit
for i in 1 2 3 4 5 6; do
  RESP="$(curl -fsS -X POST "$GATEWAY/v1/cockpit/pair/start" \
            -H 'Content-Type: application/json' \
            -d '{"device_name":"nexus-android"}' 2>&1 || true)"
  if echo "$RESP" | grep -q '"pairing_code"'; then
    break
  fi
  echo "pair/start: rate-limited or unavailable (attempt $i/6) -> sleep 15s"
  sleep 15
done

CODE="$(echo "$RESP" | python3 -c 'import json,sys; print(json.load(sys.stdin)["pairing_code"])')"
echo "Pairing code: $CODE"

CONFIRM="$(curl -fsS -X POST "$GATEWAY/v1/cockpit/pair/confirm" \
             -H 'Content-Type: application/json' \
             -d "{\"pairing_code\":\"$CODE\"}")"

TOKEN="$(echo "$CONFIRM" | python3 -c 'import json,sys; print(json.load(sys.stdin)["token"])')"
DEVICE="$(echo "$CONFIRM" | python3 -c 'import json,sys; print(json.load(sys.stdin)["device_id"])')"

umask 077
printf '%s\n' "$TOKEN" > "$OUT"
chmod 600 "$OUT"

echo
echo "device_id: $DEVICE"
echo "token written to: $OUT"
echo "show with:    cat $OUT"
echo "use in app:   paste the entire file contents into the Bearer Token field"
