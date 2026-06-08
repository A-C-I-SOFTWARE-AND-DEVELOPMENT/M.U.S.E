# Secure tunnel options for the Claude Code Windows bridge

The bridge needs exactly one thing from the network layer: **a single
directory both sides can read and write, reachable only by hosts you
authenticated.** Anything that provides that — and only that — is a
valid transport. This doc compares the realistic options and calls
out the security properties each one ships with.

> All options below are **client-to-client over a private overlay**.
> None of them require opening a port on the public internet.

## Comparison matrix

| Option                 | Auth model               | Default exposure | Crypto    | NAT traversal | Cost | Recommended for                |
|------------------------|--------------------------|------------------|-----------|---------------|------|---------------------------------|
| **Tailscale**          | Identity (SSO + ACL)     | Tailnet only     | WireGuard | DERP relay    | Free for personal use | Default. M.U.S.E. mobile + Windows desktop. |
| **WireGuard (manual)** | Static peer keys         | Mesh only        | WireGuard | Manual port forward or relay needed | Free | Hardened static setup with no SaaS. |
| **SSH reverse tunnel** | SSH keys / certs         | Loopback on the SSH server | SSH (AES-GCM / ChaCha20) | Reverse — no inbound on Windows needed | Free | A small VPS as the rendezvous point. |
| **Cloudflare Tunnel**  | Cloudflare Access (SSO + token) | Authenticated edge only | TLS via Cloudflare | Outbound from Windows only | Free for small use | Replacing a VPN when one side cannot run Tailscale. |
| **Local network only** | LAN + (ideally) WPA3     | LAN only          | None unless you add it | None needed | Free | Both machines on the same trusted LAN, with audited Wi-Fi. |
| **Manual handoff**     | Human eyes               | None              | N/A       | N/A           | Free | Air-gapped or "I'm next to the desktop" workflows. |

Throughout the rest of this document the term *shared directory*
means the directory you mount on both sides as
`<workspace_root>` in the M.U.S.E. endpoint config.

---

## Tailscale (recommended default)

Tailscale ([tailscale.com](https://tailscale.com)) is a managed
WireGuard mesh: every device authenticates to your Tailscale account
via SSO, then sees the other devices on a stable
`100.x.y.z` / `<hostname>.<tailnet>.ts.net` address. The Windows
desktop becomes reachable from the Android phone without any port
forwarding, and the link is end-to-end encrypted with WireGuard.

**Set up the shared directory:**

* **Tailscale + Syncthing.** Run Syncthing on both machines, bind it
  to the Tailscale interface only (`-gui-address=100.64.0.x:8384`),
  and share a single folder. This is the simplest cross-platform
  option and tolerates intermittent connectivity.
* **Tailscale + SMB.** Share a Windows folder over SMB, set the
  Windows firewall to allow inbound 445 from the Tailscale subnet
  only, and mount it from the M.U.S.E. host. Higher throughput than
  Syncthing for large diffs but less forgiving when the link drops.
* **Tailscale Drive / Taildrop.** Both ship with Tailscale and need
  no extra config; suitable for occasional handoffs.

**Security checks:**

* Enable **MagicDNS** so the endpoint config can reference
  `jeremiah-desktop.<tailnet>.ts.net` instead of an IP that may
  change.
* Add an **ACL rule** restricting access to the shared folder
  service to the specific Tailscale users you trust:
  ```jsonc
  {
    "acls": [
      { "action": "accept",
        "src":    ["autogroup:owner"],
        "dst":    ["jeremiah-desktop:445", "jeremiah-desktop:8384"] }
    ]
  }
  ```
* Turn on **Tailscale SSH** if you also want to run the worker
  daemon over SSH — it gives you certificate auth and recorded
  sessions for free.

## WireGuard (manual)

Plain WireGuard, without the SaaS layer. Each side has a key pair;
you exchange the public keys out-of-band and write matching
`[Peer]` blocks. End-to-end-encrypted, no third-party service in the
trust chain.

**Trade-offs vs. Tailscale:**

* No identity layer — auth is "you hold the private key". Rotate
  the keys when a device is lost.
* You manage the relay / port forward yourself. The simplest design
  is a small VPS running WireGuard as a hub; both ends dial out to
  it.

**Set up the shared directory:** as with Tailscale, layer Syncthing
or SMB on top. Bind the service to the `wg0` interface so it is
unreachable from anything outside the WireGuard mesh.

## SSH reverse tunnel

If both sides can reach a small VPS (Hetzner / Fly / a Pi at home
with a static address), use SSH reverse tunneling to expose the
Windows shared folder over loopback on the VPS, then have the
M.U.S.E. host SSH into the VPS to read it.

Sketch:

```bash
# On the Windows side, exposing an SMB share over a reverse tunnel
ssh -N -R 4445:localhost:445 hermes-bridge@vps.example
```

```bash
# On the M.U.S.E. side, mounting from the VPS
sshfs hermes-bridge@vps.example:/path/to/share /mnt/jeremiah \
  -o reconnect,ServerAliveInterval=15,ServerAliveCountMax=3
```

**Security notes:**

* Lock the VPS SSH server down to certificate-based auth, disable
  password login, and restrict the bridge user to forwarding only
  (`Match User hermes-bridge`, then
  `PermitTTY no`, `ForceCommand /usr/sbin/nologin`,
  `AllowTcpForwarding yes`, `PermitOpen localhost:4445`).
* Use `autossh` so the reverse tunnel re-establishes after the
  Windows desktop sleeps.
* The shared folder must bind to loopback on the Windows side —
  never expose SMB on the LAN as a side effect.

## Cloudflare Tunnel

Cloudflare Tunnel (`cloudflared`) gives the Windows machine an
outbound-only tunnel to Cloudflare's edge. Pair it with **Cloudflare
Access** so the only callers who can hit the tunneled hostname are
the ones holding a valid Access token (typically a passkey-bound SSO
session).

**Why use it:** the Windows desktop dials out — there is nothing
listening on the home LAN — and Cloudflare's edge handles
authentication. Useful when one side cannot run a Tailscale client
(work-managed Windows, a strict firewall).

**What to expose:** the simplest pattern is a WebDAV server on the
Windows side, tunneled out, mounted from the M.U.S.E. host via
`davfs2` / `rclone mount`. The shared directory rides on top of the
mount.

**Security notes:**

* Configure Cloudflare Access with **per-user JWT enforcement**.
  The tunnel without Access in front is just an unauthenticated
  public hostname.
* Pin the Access service token rotation reminder somewhere visible —
  tokens stored on Termux are easy to forget about.

## Local network only

Both machines on the same trusted LAN (a home network with WPA3,
no guest devices, no untrusted IoT). Share a folder with SMB and
mount it directly. No tunneling layer needed.

**Use this only when:**

* the LAN itself is trustworthy (you control the Wi-Fi credentials,
  the router admin password is not default, guest devices are on a
  separate SSID),
* the threat model does not include lateral movement from another
  device on the same network,
* and you accept that traffic on the LAN is unencrypted unless you
  also enable SMB encryption (`Set-SmbServerConfiguration
  -EncryptData $true`).

## Manual handoff fallback

The original M.U.S.E. Local Orchestrator flow ([see
`docs/hermes-local-orchestrator.md`](../hermes-local-orchestrator.md))
already supports a "copy the prompt to the clipboard, walk over to the
desktop, paste it into Claude Code, copy the output back" workflow.
Use that whenever:

* the tunnel is down and you need to ship work,
* you don't trust the network you're on,
* or you simply want a human-in-the-loop checkpoint.

The bridge supports this implicitly: with no tunnel configured, the
adapter's `detect()` returns `available=False` with a note, and the
orchestrator falls back to the existing local-orchestrator handoff.

---

## Decision tree

```
Both machines on a trusted home LAN?
├── Yes →  Local SMB share is enough for evening tinkering. Add
│          Tailscale anyway so it works when you're not home.
└── No  →  Can the Windows machine run a Tailscale client?
           ├── Yes →  Tailscale + Syncthing (or Tailscale Drive).
           └── No  →  Cloudflare Tunnel + Cloudflare Access,
                      OR an SSH reverse tunnel via a small VPS.
```

When in doubt, default to **Tailscale + Syncthing**. It is the most
forgiving option — the link survives sleep/wake, both ends dial out,
identity is bound to your SSO, and Syncthing tolerates the worker
daemon writing artifacts out of order without truncation issues.

## Mapping a transport to the endpoint config

The M.U.S.E. config does not care which transport you picked — it only
needs to know the local path of the shared directory. Both of these
configs talk to the same Windows worker; only the mount point differs:

```yaml
# Tailscale + Syncthing
endpoint:
  name: jeremiah-windows
  transport: file_drop
  workspace_root: ~/SyncthingShare/hermes-remote
```

```yaml
# SSH reverse tunnel + sshfs
endpoint:
  name: jeremiah-windows
  transport: file_drop
  workspace_root: /mnt/jeremiah-bridge/hermes-remote
```

The `transport: file_drop` value is the only one currently
implemented. `http`, `websocket`, and `ssh` are accepted as endpoint
config values but refused at dispatch time so a documentation slip
fails loudly rather than silently downgrading the security model.

## What this bridge intentionally does NOT do

* Open a port on `0.0.0.0`.
* Implement its own TLS or token verification (the tunnel does that).
* Trust a status reply just because it landed in the workspace —
  every payload is validated against the per-job token and the
  endpoint device allowlist.
* Carry secrets without an explicit two-of-two opt-in
  (`endpoint.permit_env_transfer=True` AND
  `allow_remote_execute=True` on the call).
* Print credential-shaped substrings into its audit log.
