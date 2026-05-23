"""Hermes worker adapters.

A *worker* is a thin, file-based handoff bridge between Hermes and an
external coding/review tool the user is already logged into (Claude
Code, Codex, etc.). Each adapter is responsible for:

  * detecting whether the upstream tool is locally installed,
  * preparing a self-contained prompt + status file on disk, and
  * collecting whatever artifacts the tool writes back.

Adapters never scrape an upstream tool's subscription UI, automate
hidden login flows, or speak to provider APIs directly. The default
mode is always "handoff required" — the user (or an officially
sanctioned local CLI) drives the upstream tool, and Hermes only reads
the files left behind.

Concrete adapters live next to this file (e.g. ``claude_code``). The
package exposes nothing at the top level so each adapter stays
independently importable without side-effects.
"""
