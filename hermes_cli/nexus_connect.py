"""
nexus_connect — one-command Nexus pairing helper.

Walks the loopback cockpit gateway through the device-pairing flow:

    1. GET  /v1/health                  (sanity check)
    2. POST /v1/cockpit/pair/start      (obtain pairing_code)
    3. POST /v1/cockpit/pair/confirm    (poll until owner approves)

On success the per-device token's last 6 characters are echoed in a
success banner; on expiry the command exits non-zero with a clear
message.

This module deliberately uses only the Python standard library —
the Termux/Android target has no extra deps available without
friction. The owner gate phrase "Yes, with authorization." is
hardcoded into the confirm payload on purpose: this flow is
loopback-only and is not a deploy.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request


DEFAULT_BASE_URL = "http://127.0.0.1:8765"
DEFAULT_DEVICE_NAME = "nexus-android"
OWNER_GATE_PHRASE = "Yes, with authorization."
POLL_INTERVAL_SECONDS = 5


# ---------------------------------------------------------------------------
# tiny stdlib HTTP helpers
# ---------------------------------------------------------------------------

def _http_get(url: str, timeout: float = 5.0):
    """GET url, return (status_code, parsed_json_or_none)."""
    req = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            try:
                data = json.loads(body) if body else None
            except json.JSONDecodeError:
                data = None
            return resp.getcode(), data
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace") if e.fp else ""
        try:
            data = json.loads(body) if body else None
        except json.JSONDecodeError:
            data = None
        return e.code, data


def _http_post_json(url: str, payload: dict, timeout: float = 5.0):
    """POST JSON, return (status_code, parsed_json_or_none)."""
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            try:
                parsed = json.loads(body) if body else None
            except json.JSONDecodeError:
                parsed = None
            return resp.getcode(), parsed
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace") if e.fp else ""
        try:
            parsed = json.loads(body) if body else None
        except json.JSONDecodeError:
            parsed = None
        return e.code, parsed


# ---------------------------------------------------------------------------
# banner / output helpers
# ---------------------------------------------------------------------------

def _print_code_banner(code: str, expires_in: int) -> None:
    code_str = str(code).strip()
    # Inflate the code for visibility — surround with padding and a box.
    display = "  " + "  ".join(list(code_str)) + "  "
    width = max(len(display), 44) + 4
    bar = "+" + ("-" * (width - 2)) + "+"
    title = " NEXUS PAIRING CODE "
    title_line = "+" + title.center(width - 2, "-") + "+"
    blank = "|" + (" " * (width - 2)) + "|"
    code_line = "|" + display.center(width - 2) + "|"
    hint = f"  expires in {expires_in}s — approve on the cockpit device  "
    hint_line = "|" + hint.center(width - 2) + "|"

    print()
    print(title_line)
    print(blank)
    print(code_line)
    print(blank)
    print(hint_line)
    print(bar)
    print()
    sys.stdout.flush()


def _print_success_banner(token_suffix: str) -> None:
    msg = f" PAIRED — token ...{token_suffix} "
    width = max(len(msg) + 4, 44)
    bar = "+" + ("=" * (width - 2)) + "+"
    line = "|" + msg.center(width - 2) + "|"
    print()
    print(bar)
    print(line)
    print(bar)
    print()
    sys.stdout.flush()


# ---------------------------------------------------------------------------
# main flow
# ---------------------------------------------------------------------------

def _check_health(base_url: str) -> None:
    url = f"{base_url}/v1/health"
    try:
        status, data = _http_get(url, timeout=4.0)
    except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as e:
        print(
            f"ERROR: cockpit gateway is not reachable at {base_url}\n"
            f"       (GET /v1/health failed: {e})\n"
            f"       Start it before running `nexus connect`.",
            file=sys.stderr,
        )
        sys.exit(2)

    if status != 200 or not isinstance(data, dict) or not data.get("ok"):
        print(
            f"ERROR: gateway health check failed at {base_url}/v1/health "
            f"(status={status}, body={data!r})",
            file=sys.stderr,
        )
        sys.exit(2)


def _start_pairing(base_url: str, device_name: str):
    url = f"{base_url}/v1/cockpit/pair/start"
    try:
        status, data = _http_post_json(
            url, {"device_name": device_name}, timeout=5.0
        )
    except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as e:
        print(f"ERROR: failed to POST {url}: {e}", file=sys.stderr)
        sys.exit(2)

    if status != 200 or not isinstance(data, dict):
        print(
            f"ERROR: pair/start failed (status={status}, body={data!r})",
            file=sys.stderr,
        )
        sys.exit(2)

    code = data.get("pairing_code")
    expires_in = data.get("expires_in")
    if not code or not isinstance(expires_in, (int, float)):
        print(
            f"ERROR: pair/start response missing pairing_code/expires_in: {data!r}",
            file=sys.stderr,
        )
        sys.exit(2)
    return str(code), int(expires_in)


def _poll_confirm(base_url: str, code: str, expires_in: int) -> str:
    """Poll /pair/confirm every POLL_INTERVAL_SECONDS until paired or expired.

    Returns the issued token string on success. Exits non-zero on expiry.
    """
    url = f"{base_url}/v1/cockpit/pair/confirm"
    payload = {"pairing_code": code, "authorization": OWNER_GATE_PHRASE}

    deadline = time.monotonic() + max(1, expires_in)
    attempt = 0
    while True:
        attempt += 1
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            print(
                f"\nERROR: pairing code {code} expired after ~{expires_in}s "
                f"without owner approval. Re-run `nexus connect` to try again.",
                file=sys.stderr,
            )
            sys.exit(3)

        try:
            status, data = _http_post_json(url, payload, timeout=5.0)
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as e:
            print(f"  [warn] poll #{attempt}: transient error: {e}", file=sys.stderr)
            status, data = 0, None

        if status == 200 and isinstance(data, dict) and data.get("token"):
            return str(data["token"])

        # Anything else is "not yet" — sleep and try again, unless the
        # server explicitly returned 4xx that is NOT the "pending" case.
        # Cockpit returns 202 / 4xx-ish while awaiting; treat non-200 as pending.
        print(
            f"  ...awaiting owner approval (attempt {attempt}, "
            f"~{int(max(0, remaining))}s left)",
            flush=True,
        )

        # Sleep but don't overshoot the deadline.
        sleep_for = min(POLL_INTERVAL_SECONDS, max(0.1, deadline - time.monotonic()))
        if sleep_for <= 0:
            continue
        time.sleep(sleep_for)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="nexus-connect",
        description=(
            "Pair this device with the local cockpit gateway via the "
            "loopback /v1/cockpit/pair flow."
        ),
    )
    parser.add_argument(
        "--base-url",
        default=DEFAULT_BASE_URL,
        help=f"Cockpit gateway base URL (default: {DEFAULT_BASE_URL})",
    )
    parser.add_argument(
        "--device-name",
        default=DEFAULT_DEVICE_NAME,
        help=f"Device name to register (default: {DEFAULT_DEVICE_NAME})",
    )
    args = parser.parse_args(argv)

    base_url = args.base_url.rstrip("/")

    print(f"[nexus-connect] checking gateway at {base_url} ...")
    _check_health(base_url)
    print("[nexus-connect] gateway is healthy.")

    print(f"[nexus-connect] requesting pairing code for device '{args.device_name}' ...")
    code, expires_in = _start_pairing(base_url, args.device_name)
    _print_code_banner(code, expires_in)

    print(f"[nexus-connect] polling /pair/confirm every {POLL_INTERVAL_SECONDS}s ...")
    token = _poll_confirm(base_url, code, expires_in)

    suffix = token[-6:] if len(token) >= 6 else token
    _print_success_banner(suffix)
    return 0


if __name__ == "__main__":
    sys.exit(main())
