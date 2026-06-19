# muse Local worker

The muse Local worker is the **always-available** adapter that
inspects the local repository, surfaces evidence, and prepares the
ground every other worker stands on. It ships as
[`hermes_cli/workers/hermes_local.py`](../../../hermes_cli/workers/hermes_local.py)
and runs anywhere muse runs — Linux, macOS, Windows, Termux — with
zero external dependencies beyond the standard library and a working
``git`` (used read-only and gracefully skipped when absent).

## When to use it

muse Local is the first worker every orchestrated job invokes. It:

- Discovers the repo's languages, runtimes, and package managers.
- Infers (but **never runs**) validation commands from
  ``pyproject.toml``, ``package.json``, ``Makefile``, README, AGENTS.md,
  Gradle files, and lockfiles.
- Captures the current git branch and porcelain status.
- Lists scripts under ``scripts/`` / ``bin/`` / ``tools/`` plus
  shell-style top-level scripts.
- Flags risky files at the repo root (``.env``, ``*.pem``,
  credential JSONs).
- Surfaces doc entrypoints (``README``, ``AGENTS.md``,
  ``CONTRIBUTING.md``, …).

Other workers (Codex, Aider, Goose, Claude Code, the ChatGPT handoff)
read its output to ground their prompts. Without muse Local the
downstream workers either lack repo context or duplicate the work.

## What it never does

- Execute discovered test/build/lint commands.
- Mutate the repository — output files land under ``shared-context/``
  and ``workers/hermes-local/`` only.
- Touch the network.
- Install dependencies.
- Read files outside ``root``.

The discovery primitives are unit-tested to confirm
``subprocess.run`` is not called from the inference path.

## Workspace layout

```
output_base/
├── shared-context/
│   ├── repo-map.md      # top-level file map + entrypoints
│   ├── evidence.md      # languages/runtimes/PMs/risky files/docs/scripts
│   ├── test-map.md      # inferred validation commands per source file
│   └── git-state.md     # branch + `git status --porcelain`
└── workers/
    └── hermes-local/
        ├── output.md    # human-readable run summary
        └── status.json  # machine-readable status (always written)
```

When ``output_base`` is omitted, the worker writes under ``root``.
Pass an explicit ``output_base`` to keep generated artifacts out of
the working tree.

## Lifecycle

```
HermesLocalWorker(root, output_base).run()
  │
  ├─ ensure shared-context/ + workers/hermes-local/
  ├─ top_level_map()           ➜ shared-context/repo-map.md
  ├─ detect_languages()        ─┐
  ├─ detect_package_managers() ─┼─➜ shared-context/evidence.md
  ├─ find_risky_files()        ─┤
  ├─ find_docs_entrypoints()   ─┤
  ├─ find_scripts()            ─┘
  ├─ detect_test_commands()    ➜ shared-context/test-map.md
  ├─ inspect_git_state()       ➜ shared-context/git-state.md
  └─ write_worker_output(...)  ➜ workers/hermes-local/output.md
        + write_status(...)    ➜ workers/hermes-local/status.json
```

Every step is best-effort. If one of the discovery helpers raises,
the error is captured in ``WorkerStatus.errors`` and ``ok=False`` is
recorded — ``status.json`` is still written so the dashboard can show
the failure without re-running the worker.

## Validation command inference

muse Local infers commands from the following sources:

| Source            | Examples it extracts                                                          |
| ----------------- | ----------------------------------------------------------------------------- |
| ``pyproject.toml``| ``pytest``, ``python -m pytest -q``, ``ty check``, ``ruff check .``, ``mypy .``|
| ``package.json``  | ``npm run test``, ``npm run lint``, ``npm run typecheck``, ``npm run build``  |
| ``pnpm-lock.yaml``| ``pnpm test`` (PM-of-record fallback)                                         |
| ``yarn.lock``     | ``yarn test`` (PM-of-record fallback)                                         |
| ``Makefile``      | ``make test``, ``make lint``, ``make check``, ``make ci``, …                  |
| Gradle files      | ``./gradlew test``, ``./gradlew check``                                       |
| ``README.md`` /   | Commands inside fenced ``bash``/``sh``/``shell``/``console`` blocks that      |
| ``AGENTS.md`` /   | start with ``pytest``, ``npm test``, ``pnpm test``, ``cargo test``, ``go      |
| ``CONTRIBUTING``  | test``, ``ruff check``, ``mypy``, ``ty check`` …                              |

Duplicate ``(source, label, command)`` triples are collapsed so the
downstream worker sees one entry per real command.

## Python API

```python
from pathlib import Path
from hermes_cli.workers.hermes_local import HermesLocalWorker

worker = HermesLocalWorker(
    root=Path("/repo"),
    output_base=Path("/run/job-42"),   # optional; defaults to root
)
status = worker.run()
print(status.ok, status.artifacts)
```

The constructor resolves both paths to absolute form. ``run()``
returns a :class:`WorkerStatus` dataclass with:

- ``worker`` — always ``"hermes-local"``,
- ``available`` — always ``True`` (the worker has no dependencies),
- ``ok`` — ``False`` only if an internal step raised,
- ``started_at`` / ``finished_at`` — ISO-8601 UTC timestamps,
- ``errors`` — list of captured failures,
- ``artifacts`` — list of POSIX-style paths the worker wrote.

## Score stub

muse Local is an evidence worker, not a judgement worker — it does
not score the repo. Callers that want to slot it into the same
scoring pipeline as the other adapters should treat a successful run
as ``value=0.0, confidence=1.0`` (we know the evidence, no judgement
made) and an unsuccessful run as ``value=0.0, confidence=0.0``.

## Failure modes

| Symptom                                | Cause                                                                 |
| -------------------------------------- | --------------------------------------------------------------------- |
| ``ok=False`` + traceback in ``errors``  | Discovery helper raised; ``status.json`` still written.               |
| ``is_git_repo=False`` in git-state      | ``.git/`` missing — worker reports honestly, never invents a branch.  |
| Empty ``test-map.md``                   | None of the inferred sources matched; downstream worker can fall back.|
| ``find_risky_files()`` returns entries  | The repo root contains ``.env`` / ``*.pem`` / similar — flag, don't act.|

## Limits

- Inference is regex-based; very unusual project layouts may emit
  fewer commands than a human reviewer would. Add explicit hints in
  ``AGENTS.md`` to surface them.
- ``top_level_map`` is capped at 200 entries by default to keep the
  artifact readable; pass ``limit=...`` to widen the window.
- The worker never recurses past the top level for the map — deep
  directory trees are intentionally out of scope; later phases handle
  symbol-level evidence.
