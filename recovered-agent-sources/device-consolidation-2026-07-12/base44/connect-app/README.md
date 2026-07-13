# ACI Hermes Command Cockpit — Base44 App

This folder is the missing `base44-hermes-connect-app/` companion app referenced by `.github/workflows/sync-aci-to-base44.yml`.

It is **not** the Hermes backend. Hermes remains canonical in the repo root.

## Purpose

Base44 should provide the owner/operator cockpit for:

- JARVIS Prime status
- owner brief
- work packets
- gate results
- model routing
- memory review queue
- integration status
- Slack / Termux / GitHub command bridge visibility

## Backend boundary

This app should connect to a Hermes API bridge. Until that bridge exists, it runs in demo/local mode with seeded data.

## Commands

```bash
npm install
npm run dev
npm run build
```

## Canonical source commit used in audit

`b8308c86faf59deb5ec668bbb2e3b84560b92ab8`
