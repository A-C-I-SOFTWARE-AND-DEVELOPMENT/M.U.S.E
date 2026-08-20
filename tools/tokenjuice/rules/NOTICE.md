# Rule files — third-party attribution

The `*.json` rule files in this directory are vendored verbatim from the
upstream **[vincentkoc/tokenjuice](https://github.com/vincentkoc/tokenjuice)**
project and are licensed under the **MIT License** (Copyright (c) 2026 Vincent
Koc), independent of any other license in this repository.

Filename convention: upstream ids contain `/` (e.g. `git/status`); here the `/`
is replaced with `__` in the filename (`git__status.json`). The `id` field
inside each file is unchanged and is what the loader/classifier matches on.

The Python reducer in this package is a **clean-room reimplementation** of
TokenJuice behavior; it does not copy code from any GPL-licensed port. See the
repository root `THIRD_PARTY_NOTICES.md` for the full MIT license text.
