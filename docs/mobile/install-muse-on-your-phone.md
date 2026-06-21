# Install MUSE on your phone

*A plain-English walk-through. No coding background needed — if you can copy and
paste, you can do this.*

This guide installs **MUSE** so it runs **entirely on your own Android phone**.
Nothing to sign up for, no server to rent, no computer required. Everything
lives on your phone.

---

## Before you start

- An **Android** phone (this on-phone setup is Android-only for now).
- About **10 minutes** and a **Wi-Fi** connection.
- That's it.

> Using an iPhone? There's no tested on-phone path for iOS yet — for now MUSE
> on a phone means Android.

---

## Step 1 — Install Termux (a free terminal app)

MUSE runs inside a free app called **Termux**, which gives your phone a little
text console.

**Important:** install it from one of these two places, **not** the Google Play
Store (the Play Store version is old and won't work):

- **F-Droid:** https://f-droid.org/packages/com.termux/
- **Or the official releases page:** https://github.com/termux/termux-app/releases

Download and install Termux like any other app. If your phone asks whether to
allow installing it, say yes. Then open Termux — you'll see a black screen with
a blinking cursor. That's where the next step goes.

---

## Step 2 — Paste one command

Tap into Termux and paste this single line, then press **Enter**:

```bash
curl -fsSL https://raw.githubusercontent.com/A-C-I-SOFTWARE-AND-DEVELOPMENT/M.U.S.E/main/scripts/install.sh | bash
```

> **Tip:** to paste in Termux, touch and hold on the screen, then tap **Paste**.

This downloads MUSE and everything it needs and sets it up for you. It can take
a few minutes and prints a lot of text — that's normal. Leave it running until
it finishes and you get your cursor back. It's safe to let it run.

---

## Step 3 — Start MUSE and pick its brain

Once the install finishes, start MUSE by typing:

```bash
muse
```

The first time, you'll want to choose which AI model MUSE uses (its "brain").
Run:

```bash
muse model
```

and pick one from the list.

> MUSE needs a key from an AI provider to think (this is the one thing that
> isn't free). If you get stuck on this part, run the guided setup wizard — it
> walks you through it step by step:
>
> ```bash
> muse setup
> ```

---

## Step 4 — Say hello

With MUSE running, just type a message — for example:

> Hi! Tell me what you can do.

If you get a reply, you're done. 🎉 MUSE is now living on your phone.

---

## Optional: prefer tapping to typing? Add the app

If you'd rather use a normal tap-and-scroll app instead of the text console,
there's a companion **MUSE cockpit** app that connects to the copy of MUSE you
just installed.

1. **Download the app** on your phone:
   [jarvis-prime-android.apk](https://github.com/A-C-I-SOFTWARE-AND-DEVELOPMENT/M.U.S.E/releases/download/android-latest/jarvis-prime-android.apk).
   Tap the downloaded file to install it, and allow installs from this source if
   Android asks. (Android may warn it's from an "unknown developer" — that's
   expected for a sideloaded app.) Requires **Android 8.0 or newer**.
2. **Turn on the connection** in Termux:

   ```bash
   muse cockpit serve
   ```

   This prints a short **pairing token**. Leave this running.
3. **Pair the app:** open the MUSE app, go to its pairing screen, and enter:
   - Address: `http://127.0.0.1:8765`
   - Token: the one Termux just printed (run `muse cockpit token` to show it
     again).

The app now talks to the MUSE running on your own phone.

---

## If something goes wrong

- **The install command failed or stopped partway?** Just paste the same
  command from Step 2 again — it's safe to re-run.
- **MUSE acts up or won't start?** Run a quick self-check:

  ```bash
  muse doctor
  ```

  It tells you what's missing.
- **Still stuck?** Send me a screenshot plus:
  - your Android version (Settings → About phone),
  - the output of `muse doctor`.

---

## One honest heads-up

A couple of fancier features — **voice** and **automatic web browsing** — aren't
part of the tested on-phone setup yet, so don't be surprised if those aren't
available. Everything else works as a phone-native MUSE.

---

*Want the deeper, more technical version (remote servers, message platforms,
boot-on-startup)? See [`docs/mobile/mobile-app-guide.md`](mobile-app-guide.md)
and [`../../website/docs/getting-started/termux.md`](../../website/docs/getting-started/termux.md).*
