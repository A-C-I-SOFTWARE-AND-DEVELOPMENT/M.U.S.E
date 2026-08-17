"""
show_snapshot.py — Dump the population from a darwinian-evolver snapshot pickle.

Usage:
    python show_snapshot.py PATH/TO/iteration_N.pkl [--field prompt_template]

The script is intentionally Organism-agnostic: it walks `org.__dict__` and prints
all str fields. By default it shows `prompt_template` if present; pass --field to
target a different attribute (e.g. `regex_pattern`, `sql_query`, `code_block`).

Security (Work Packet §9.1)
---------------------------
A snapshot is a pickle, and unpickling executes code the producer embedded.
This script now routes both loads — the outer file and the inner
``population_snapshot`` blob — through ``tools/security/safe_pickle.py``, which
verifies a recorded SHA-256 before a single opcode is unpickled and refuses on
mismatch. That does not make untrusted pickle safe; nothing does. Its contract
is *only load what we already vouched for*.

How that changes the ``--i-trust-this-file`` gate: the acknowledgement is now
required only while the snapshot is **unpinned**, i.e. exactly when the trust
decision is actually being made. Acknowledging records the pin. Every later run
verifies those exact bytes and needs no flag; a snapshot that has been swapped
underneath you is refused outright rather than re-asking a question you already
answered "yes" to. Set ``MUSE_PICKLE_PINS_STRICT=1`` to disable first-use
recording entirely and refuse anything unpinned.
"""
from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

# NOTE: this module deliberately no longer imports `pickle`. Both former
# `pickle.loads` call sites now go through tools/security/safe_pickle.py, so
# there is no un-gated deserialisation path left in this file at all.


# ---------------------------------------------------------------------------
# Locate tools/security/safe_pickle.py (Work Packet §9.1)
# ---------------------------------------------------------------------------
# This script is run directly from the skill directory, so the repository root
# is usually not on sys.path. Walk up to find the helper. If it is missing we
# fail closed rather than falling back to a bare pickle.loads().

def _load_safe_pickle_module():
    """Import tools.security.safe_pickle, by path if necessary. Fails closed."""
    try:
        from tools.security import safe_pickle as _mod  # noqa: PLC0415

        return _mod
    except ImportError:
        pass

    import importlib.util  # noqa: PLC0415

    directory = Path(__file__).resolve().parent
    for candidate_root in [directory, *directory.parents]:
        candidate = candidate_root / "tools" / "security" / "safe_pickle.py"
        if candidate.is_file():
            spec = importlib.util.spec_from_file_location(
                "muse_tools_security_safe_pickle", str(candidate)
            )
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            return module
    raise ImportError(
        "tools/security/safe_pickle.py not found. Refusing to fall back to an "
        "unverified pickle.loads() of a snapshot (Work Packet §9.1)."
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("snapshot", type=Path)
    ap.add_argument(
        "--field",
        default=None,
        help="Organism attribute to display. Defaults to the first str field found.",
    )
    ap.add_argument("--top", type=int, default=None, help="Show only top N by score.")
    ap.add_argument(
        "--i-trust-this-file",
        action="store_true",
        help=(
            "Acknowledgement that the snapshot is from a trusted source, required "
            "the first time a given snapshot is read. Unpickling executes arbitrary "
            "code embedded in the file (RCE) and must NEVER be run on snapshots "
            "received from untrusted parties. Acknowledging records the file's "
            "SHA-256; later runs verify that pin and need no flag, while a changed "
            "or swapped snapshot is refused."
        ),
    )
    ap.add_argument(
        "--pins",
        type=Path,
        default=None,
        help=(
            "Pin file location. Defaults to a per-user store under ~/.hermes/security/ "
            "— deliberately NOT beside the snapshot, because a pin that travels with "
            "the file it vouches for vouches for nothing."
        ),
    )
    args = ap.parse_args()

    if not args.snapshot.exists():
        sys.exit(f"snapshot not found: {args.snapshot}")

    # Work Packet §9.1: hash-pin both loads. Nothing is unpickled until the
    # recorded SHA-256 matches.
    safe_pickle = _load_safe_pickle_module()

    # The pin store must live somewhere the supplier of the snapshot cannot
    # write. Defaulting it beside the snapshot -- as this script briefly did --
    # is self-defeating: an attacker ships `evolved.pkl` and
    # `.muse-pickle-pins.json` in the same tarball, the pin matches the payload
    # it travelled with, `already_pinned` is True, and the acknowledgement gate
    # is skipped entirely. That was demonstrated: the bundle executed
    # `os.system` with no flag and no warning, where the unpinned code refused.
    #
    # So the default store is per-user, outside any snapshot directory.
    default_pins = Path.home() / ".hermes" / "security" / safe_pickle.PIN_FILE_NAME
    pin_path = args.pins or default_pins
    store = safe_pickle.PinStore(pin_path)
    outer_key = args.snapshot.name
    inner_key = f"{outer_key}#population_snapshot"
    already_pinned = store.get(outer_key) is not None and store.get(inner_key) is not None

    # A pin that lives inside the snapshot's own directory tree is supplier-
    # controlled and cannot establish trust, however it got there. Treat it as
    # no pin at all for gating purposes -- it may still be verified for
    # tamper-detection, but it can never waive the acknowledgement.
    try:
        snapshot_dir = args.snapshot.resolve().parent
        pin_is_supplier_controlled = (
            pin_path.resolve() == snapshot_dir / pin_path.name
            or snapshot_dir in pin_path.resolve().parents
        )
    except OSError:
        pin_is_supplier_controlled = True
    if pin_is_supplier_controlled and already_pinned:
        print(
            f"WARNING: ignoring the pin in {pin_path} for trust purposes — it sits "
            f"inside the snapshot's own directory, so whoever supplied the snapshot "
            f"could have supplied the pin. Re-run with --i-trust-this-file (or point "
            f"--pins at a store you control) to proceed.",
            file=sys.stderr,
        )
        already_pinned = False

    # Keys are file NAMES, so two different snapshots called `evolved.pkl` from
    # different directories would collide in a shared store. Disambiguate by the
    # resolved parent so a pin can never be satisfied by an unrelated file.
    if not args.pins:
        try:
            scope = hashlib.sha256(str(snapshot_dir).encode("utf-8")).hexdigest()[:12]
            outer_key = f"{scope}/{args.snapshot.name}"
            inner_key = f"{outer_key}#population_snapshot"
            already_pinned = (
                not pin_is_supplier_controlled
                and store.get(outer_key) is not None
                and store.get(inner_key) is not None
            )
        except (OSError, ValueError):
            already_pinned = False

    if not already_pinned and not args.i_trust_this_file:
        sys.exit(
            "refusing to unpickle: this snapshot has no recorded SHA-256 pin, and "
            "pickle.loads is equivalent to executing arbitrary code from the file. "
            "Only proceed if you created/control this file, then re-run with "
            "--i-trust-this-file. That records the pin; subsequent runs verify it "
            "and need no flag.\n"
            f"  file: {args.snapshot}\n"
            f"  pins: {pin_path}"
        )

    if not already_pinned:
        print(
            f"WARNING: unpickling {args.snapshot} — this executes code embedded in the "
            "file. Only safe for snapshots you produced yourself. Its SHA-256 is being "
            f"recorded in {pin_path}; any later change to these bytes will be refused.",
            file=sys.stderr,
        )

    # Note on MUSE_PICKLE_PINS_STRICT: strict mode still *verifies* pinned
    # artifacts, it only forbids recording a new pin. So an already-pinned
    # snapshot keeps working under strict mode; an unpinned one is refused by
    # the helper even if --i-trust-this-file was passed.

    # The outer pickle wraps a dict; the inner pickle contains the actual organism
    # objects, which must be importable under their original dotted path. If you
    # ran a custom driver, make sure its module is on sys.path before calling this.
    try:
        outer = safe_pickle.safe_pickle_load(
            args.snapshot,
            key=outer_key,
            store=store,
            note="darwinian-evolver snapshot, acknowledged with --i-trust-this-file",
        )
        if not isinstance(outer, dict) or "population_snapshot" not in outer:
            sys.exit("not a darwinian-evolver snapshot (no population_snapshot key)")
        inner = safe_pickle.safe_pickle_loads(
            outer["population_snapshot"],
            key=inner_key,
            store=store,
            origin=f"{args.snapshot}::population_snapshot",
            note="inner population blob, pinned in its own right",
        )
    except safe_pickle.PickleIntegrityError as exc:
        sys.exit(f"refusing to unpickle: {exc}")
    pairs = inner["organisms"]  # list of (Organism, EvaluationResult)

    print(f"# organisms: {len(pairs)}\n")
    ranked = sorted(pairs, key=lambda p: getattr(p[1], "score", 0) or 0, reverse=True)
    if args.top:
        ranked = ranked[: args.top]

    for i, (org, res) in enumerate(ranked):
        score = getattr(res, "score", float("nan"))
        print(f"=== rank {i} score={score:.3f} ===")
        # pick field
        field = args.field
        if field is None:
            for k, v in vars(org).items():
                if isinstance(v, str) and not k.startswith("_") and k not in {"id",}:
                    field = k
                    break
        val = getattr(org, field, None) if field else None
        if val is None:
            print(f"  (no string field; org fields: {list(vars(org).keys())})")
        else:
            print(f"  {field} ({len(val)} chars):")
            for ln in val.splitlines()[:30]:
                print(f"    {ln}")
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
