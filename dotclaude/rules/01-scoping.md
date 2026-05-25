# Rule: Scoping

Touch only what the task requires.

- No drive-by refactors.
- No "while I was in here" rewrites.
- No speculative abstractions for hypothetical future requirements.
- No new dependencies unless the task requires it — and justify when added.
- No backwards-compatibility shims for code that is being deleted.

If you notice a real adjacent problem, name it in the closing message as a
separate follow-up. Do not silently bundle it into the current change.
