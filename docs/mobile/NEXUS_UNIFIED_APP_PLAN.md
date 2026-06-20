# Nexus Unified App Plan

## Installing Nexus on Termux/Android

Step-by-step for getting the Nexus Android client onto a Termux-equipped
device (tested on Samsung OneUI, where SELinux file-context rules block the
naive `pm install /sdcard/...` path).

### Prerequisites

```
pkg install termux-tools termux-api
```

- `termux-tools` provides `termux-open`, which hands the APK to the Android
  system installer.
- `termux-api` is used later by `scripts/nexus-connect.sh` for the
  device-side handshake.

### Get the APK

<!-- TODO(ci): replace with signed CI release asset URL once the
     nexus-android build job publishes one. For now, download the latest
     nexus-android-*.apk artifact from CI and drop it in /sdcard/Download/. -->

Place the file in either:

- `/sdcard/Download/` (Samsung default; visible in My Files)
- `~/storage/downloads/` (Termux storage symlink — run
  `termux-setup-storage` once if it does not exist)

Filenames with spaces or parens are fine — the installer handles
`nexus-android (5).apk` correctly.

### Run the installer

```
bash scripts/nexus-install.sh
```

The script will:

1. Pick the newest `nexus-android*.apk` across both search directories.
2. Print absolute path, size, and (best-effort) package id + version
   scraped from the binary AndroidManifest.xml.
3. Copy the APK to `$HOME/nexus.apk` (see "Why pm install fails" below).
4. Invoke `termux-open --chooser --content-type
   application/vnd.android.package-archive $HOME/nexus.apk`.

### What the dialog looks like

Android may first show a chooser ("Open with…") — pick **Package
installer**. The standard "Do you want to install this application?" dialog
appears next; tap **Install**. On first install of an unknown source you
may need to grant Termux the "Install unknown apps" permission once.

### Why `pm install` fails on Samsung

OneUI applies SELinux file-context labels to `/sdcard/...` that the system
`pm` binary refuses to read, producing `avc: denied { read } …
scontext=u:r:system_server:s0 tcontext=u:object_r:fuse:s0` errors.

Copying the APK into `$HOME` (a Termux-owned path under
`/data/data/com.termux/files/home/`) sidesteps the label mismatch, and
`termux-open` then delegates to the system installer via an Intent, which
has the right context.

### Fallback: manual install via My Files

If `termux-open` is unavailable or the chooser refuses to show:

1. Open Samsung **My Files** → **Internal storage → Download**.
2. Tap `nexus-android*.apk` and confirm **Install**.

After install, return to Termux and run `scripts/nexus-connect.sh`.
