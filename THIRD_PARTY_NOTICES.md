# Third-party notices

Components in this repository that originate outside it, with their licenses and
the terms under which they are included. Add a section here in the same commit
that vendors any third-party material.

## TokenJuice rule set (Vincent Koc)

- **Project:** TokenJuice — terminal-output compaction rules
- **Source:** https://github.com/vincentkoc/tokenjuice
- **License:** MIT License — Copyright (c) 2026 Vincent Koc

**How Hermes uses it.** The JSON rule files under
`tools/tokenjuice/rules/*.json` are vendored **verbatim** from the upstream
`vincentkoc/tokenjuice` project (the generic, non-proprietary rule set). They
are MIT-licensed *data*. The Python reducer in `tools/tokenjuice/` is a
**clean-room reimplementation** of TokenJuice behavior written from the public
upstream specification — **no** source code from any TokenJuice port (including
GPL-licensed ports) is copied. Only the MIT rule JSON is reused, with the
attribution preserved here and in `tools/tokenjuice/rules/NOTICE.md`.

### MIT License (TokenJuice)

```
MIT License

Copyright (c) 2026 Vincent Koc

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

---
