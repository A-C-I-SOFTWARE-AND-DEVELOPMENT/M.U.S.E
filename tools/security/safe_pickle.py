"""Hash-pinned pickle loading — Work Packet §9.1.

What this is, and what it is emphatically not
---------------------------------------------
**Untrusted pickle cannot be made safe.** ``pickle.load`` is equivalent to
executing whatever code the producer of the byte stream chose to embed, and no
wrapper, allow-list or "restricted unpickler" changes that in general. This
module does not attempt it.

The contract implemented here is narrower and actually enforceable:

    **Only load what we already vouched for.**

An artifact is *vouched for* when its SHA-256 has been recorded in a pin file
that lives alongside it and is under the same review discipline as the rest of
the repository. Every load re-hashes the bytes **before** they reach the
unpickler and refuses on mismatch. That closes the specific §9.1 exposure —
a pickle directory that is later repopulated from a downloaded artifact, or a
snapshot file that is swapped underneath a developer — without pretending to
solve deserialisation of hostile input.

Concretely, the three properties this gives you:

1. **Verify-before-execute.** The digest is computed over the raw bytes and
   compared while the unpickler has not yet seen a single opcode. On mismatch
   nothing is unpickled, so a swapped artifact cannot execute.
2. **Record-on-first-use, loudly.** The first time an artifact is seen with no
   recorded pin, the digest is written to the pin file and a conspicuous
   warning is emitted on stderr and through :mod:`warnings`. The point is that
   trust is *established at a visible moment* rather than assumed forever.
   Set ``HERMES_PICKLE_PINS_STRICT=1`` (or pass ``allow_record_on_first_use=
   False``) in any environment where even that is too generous — then an
   unpinned artifact is refused outright.
3. **Refuse thereafter.** Once a pin exists it is authoritative. A changed
   artifact raises :class:`PickleIntegrityError`; it is never re-recorded
   silently. Re-pinning is a deliberate act (``hermes-pin --repin`` below, or
   deleting the entry), which is what makes the pin file a review artifact.

What it does *not* protect against: an attacker who can write both the artifact
and the pin file. That is the same trust boundary as the repository itself, and
it is stated here so nobody mistakes this for a sandbox.

Pin file format
---------------
JSON, versioned, one file per artifact directory (default
``.hermes-pickle-pins.json``)::

    {
      "version": 1,
      "_comment": "SHA-256 pins for pickle artifacts in this directory ...",
      "pins": {
        "tokenizer.pkl": {
          "sha256": "…64 hex chars…",
          "size_bytes": 262144,
          "recorded_at": "2026-08-16T12:00:00Z",
          "recorded_by": "record-on-first-use",
          "note": "autoresearch BPE tokenizer"
        }
      }
    }

Keys are caller-chosen strings. For a file the default key is its basename; a
nested blob inside an outer pickle uses an explicit key such as
``"iteration_7.pkl#population_snapshot"`` so the inner payload is pinned in its
own right rather than inheriting the outer file's trust.

CLI
---
::

    python -m tools.security.safe_pickle --show   <artifact>
    python -m tools.security.safe_pickle --pin    <artifact> [--note TEXT]
    python -m tools.security.safe_pickle --repin  <artifact> [--note TEXT]
    python -m tools.security.safe_pickle --verify <artifact>
    python -m tools.security.safe_pickle --selftest

``--pin`` only records a digest; it never unpickles, so it is safe to run
against a file you have not decided to trust yet.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import io
import json
import os
import pickle
import sys
import tempfile
import warnings
from pathlib import Path
from typing import Any, BinaryIO, Dict, Optional

__all__ = [
    "PIN_FILE_NAME",
    "PIN_FILE_VERSION",
    "PickleIntegrityError",
    "UnpinnedPickleWarning",
    "PinStore",
    "sha256_bytes",
    "sha256_file",
    "safe_pickle_load",
    "safe_pickle_loads",
]

PIN_FILE_NAME = ".hermes-pickle-pins.json"
PIN_FILE_VERSION = 1

_STRICT_ENV = "HERMES_PICKLE_PINS_STRICT"
_READ_CHUNK = 1024 * 1024

_PIN_FILE_COMMENT = (
    "SHA-256 pins for pickle artifacts in this directory. Verified before "
    "unpickling; a mismatch refuses the load (Work Packet 9.1). Untrusted "
    "pickle is not made safe by this file -- the contract is 'only load what "
    "we already vouched for'. Re-pinning is deliberate: delete the entry or "
    "run 'python -m tools.security.safe_pickle --repin <artifact>'."
)


class PickleIntegrityError(RuntimeError):
    """Raised instead of unpickling when an artifact is not the pinned one.

    Also raised when an artifact has no pin and recording is disabled (strict
    mode). In every case the bytes have **not** been handed to the unpickler.
    """


class UnpinnedPickleWarning(UserWarning):
    """Emitted when a pin is recorded on first use rather than verified."""


# ---------------------------------------------------------------------------
# Digests
# ---------------------------------------------------------------------------


def sha256_bytes(data: bytes) -> str:
    """SHA-256 of an in-memory payload, lowercase hex."""
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: os.PathLike[str] | str) -> str:
    """SHA-256 of a file, streamed so a large artifact is not held in memory."""
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        while True:
            chunk = handle.read(_READ_CHUNK)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def _utc_now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )


def _strict_by_default() -> bool:
    return os.environ.get(_STRICT_ENV, "").strip().lower() in {"1", "true", "yes", "on"}


# ---------------------------------------------------------------------------
# Pin store
# ---------------------------------------------------------------------------


class PinStore:
    """A versioned JSON file recording the SHA-256 of vouched-for artifacts.

    The store is re-read on every access rather than cached, so two processes
    (or a human editing the file between runs) see each other's pins. Writes go
    through a temp file plus :func:`os.replace`, so a crash mid-write cannot
    leave a truncated pin file that would look like "no pin recorded".
    """

    def __init__(self, path: os.PathLike[str] | str) -> None:
        self.path = Path(path)

    # -- reading ---------------------------------------------------------
    def _read(self) -> Dict[str, Any]:
        if not self.path.exists():
            return {"version": PIN_FILE_VERSION, "_comment": _PIN_FILE_COMMENT, "pins": {}}
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise PickleIntegrityError(
                f"pin file is unreadable, refusing to load anything against it: "
                f"{self.path} ({exc})"
            ) from exc
        if not isinstance(raw, dict) or not isinstance(raw.get("pins"), dict):
            raise PickleIntegrityError(
                f"pin file has the wrong shape (expected an object with a 'pins' "
                f"object): {self.path}"
            )
        version = raw.get("version")
        if version != PIN_FILE_VERSION:
            raise PickleIntegrityError(
                f"pin file version {version!r} is not supported by this build "
                f"(expected {PIN_FILE_VERSION}): {self.path}"
            )
        return raw

    def get(self, key: str) -> Optional[Dict[str, Any]]:
        """Return the recorded pin entry for ``key``, or ``None``."""
        return self._read()["pins"].get(key)

    def entries(self) -> Dict[str, Any]:
        """Return every recorded pin entry (a copy)."""
        return dict(self._read()["pins"])

    # -- writing ---------------------------------------------------------
    def record(
        self,
        key: str,
        digest: str,
        *,
        size_bytes: int,
        note: str = "",
        recorded_by: str = "record-on-first-use",
        overwrite: bool = False,
    ) -> Dict[str, Any]:
        """Record ``digest`` for ``key``.

        Refuses to replace a differing existing pin unless ``overwrite`` is
        set — silent re-pinning would defeat the entire mechanism.
        """
        doc = self._read()
        existing = doc["pins"].get(key)
        if existing is not None and existing.get("sha256") != digest and not overwrite:
            raise PickleIntegrityError(
                f"refusing to overwrite the existing pin for {key!r} in {self.path}; "
                f"pass --repin (or overwrite=True) if the change is intended"
            )
        entry = {
            "sha256": digest,
            "size_bytes": int(size_bytes),
            "recorded_at": _utc_now(),
            "recorded_by": recorded_by,
            "note": note,
        }
        doc["pins"][key] = entry
        doc["version"] = PIN_FILE_VERSION
        doc["_comment"] = _PIN_FILE_COMMENT
        self._write(doc)
        return entry

    def _write(self, doc: Dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        doc["pins"] = dict(sorted(doc["pins"].items()))
        payload = json.dumps(doc, indent=2, sort_keys=False) + "\n"
        fd, tmp = tempfile.mkstemp(
            prefix=self.path.name + ".", suffix=".tmp", dir=str(self.path.parent)
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(payload)
            os.replace(tmp, self.path)
        except BaseException:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise


def _default_store_for(path: Path) -> PinStore:
    override = os.environ.get("HERMES_PICKLE_PINS_FILE", "").strip()
    if override:
        return PinStore(override)
    return PinStore(path.parent / PIN_FILE_NAME)


# ---------------------------------------------------------------------------
# The gate
# ---------------------------------------------------------------------------


def _warn_recorded(key: str, digest: str, store: PinStore, size_bytes: int) -> None:
    message = (
        f"SECURITY: no SHA-256 pin was recorded for pickle artifact {key!r}. "
        f"Recording {digest} ({size_bytes} bytes) on first use in {store.path} and "
        f"loading it. Unpickling executes arbitrary code embedded in the file, so "
        f"this run is trusting the artifact you already have on disk. Review that "
        f"pin now; every later load is refused unless the bytes match it exactly. "
        f"Set {_STRICT_ENV}=1 to refuse unpinned artifacts instead."
    )
    print("=" * 78, file=sys.stderr)
    print(message, file=sys.stderr)
    print("=" * 78, file=sys.stderr)
    sys.stderr.flush()
    warnings.warn(message, UnpinnedPickleWarning, stacklevel=3)


def _gate(
    digest: str,
    size_bytes: int,
    *,
    key: str,
    store: PinStore,
    allow_record_on_first_use: Optional[bool],
    note: str,
    origin: str,
) -> str:
    """Verify ``digest`` against the store, or record it. Returns the outcome.

    ``"verified"`` — the pin existed and matched.
    ``"recorded"`` — no pin existed and one was written (loud warning).

    Raises :class:`PickleIntegrityError` in every other case. This function is
    the only place a load is authorised, and it never touches the payload.
    """
    if allow_record_on_first_use is None:
        allow_record_on_first_use = not _strict_by_default()

    entry = store.get(key)
    if entry is not None:
        pinned = str(entry.get("sha256", "")).strip().lower()
        if not pinned:
            raise PickleIntegrityError(
                f"pin entry for {key!r} in {store.path} has no sha256; refusing to load "
                f"{origin}"
            )
        if pinned != digest:
            raise PickleIntegrityError(
                "refusing to unpickle: artifact does not match its recorded pin.\n"
                f"  artifact : {origin}\n"
                f"  key      : {key}\n"
                f"  pin file : {store.path}\n"
                f"  expected : {pinned}\n"
                f"  actual   : {digest}\n"
                "Nothing was unpickled. If the change is intended, re-pin deliberately: "
                "python -m tools.security.safe_pickle --repin <artifact>"
            )
        return "verified"

    if not allow_record_on_first_use:
        raise PickleIntegrityError(
            "refusing to unpickle: no SHA-256 pin is recorded for this artifact and "
            f"record-on-first-use is disabled ({_STRICT_ENV} is set, or the caller "
            "passed allow_record_on_first_use=False).\n"
            f"  artifact : {origin}\n"
            f"  key      : {key}\n"
            f"  pin file : {store.path}\n"
            f"  actual   : {digest}\n"
            "Nothing was unpickled. Vouch for it explicitly with: "
            "python -m tools.security.safe_pickle --pin <artifact>"
        )

    store.record(key, digest, size_bytes=size_bytes, note=note)
    _warn_recorded(key, digest, store, size_bytes)
    return "recorded"


def safe_pickle_load(
    path: os.PathLike[str] | str,
    *,
    key: Optional[str] = None,
    store: Optional[PinStore] = None,
    allow_record_on_first_use: Optional[bool] = None,
    note: str = "",
    **pickle_kwargs: Any,
) -> Any:
    """Load a pickle file whose SHA-256 matches its recorded pin.

    Only loads what this repository already vouched for. The digest is computed
    and checked before any byte reaches :func:`pickle.load`, so a swapped or
    tampered artifact raises :class:`PickleIntegrityError` without executing.

    Parameters
    ----------
    path:
        The pickle artifact.
    key:
        Pin-store key. Defaults to the file's basename.
    store:
        Where pins live. Defaults to ``<artifact dir>/.hermes-pickle-pins.json``,
        overridable with ``HERMES_PICKLE_PINS_FILE``.
    allow_record_on_first_use:
        ``None`` (default) honours ``HERMES_PICKLE_PINS_STRICT``. ``False``
        refuses an unpinned artifact. ``True`` records it with a loud warning.
    note:
        Free text stored with a newly recorded pin.
    """
    artifact = Path(path)
    if not artifact.is_file():
        raise FileNotFoundError(f"pickle artifact not found: {artifact}")

    resolved_store = store if store is not None else _default_store_for(artifact)
    resolved_key = key if key is not None else artifact.name
    digest = sha256_file(artifact)
    size_bytes = artifact.stat().st_size

    _gate(
        digest,
        size_bytes,
        key=resolved_key,
        store=resolved_store,
        allow_record_on_first_use=allow_record_on_first_use,
        note=note,
        origin=str(artifact),
    )

    with open(artifact, "rb") as handle:
        return pickle.load(handle, **pickle_kwargs)  # noqa: S301 - gated above


def safe_pickle_loads(
    data: bytes,
    *,
    key: str,
    store: PinStore | os.PathLike[str] | str,
    allow_record_on_first_use: Optional[bool] = None,
    note: str = "",
    origin: str = "<in-memory payload>",
    **pickle_kwargs: Any,
) -> Any:
    """Load an in-memory pickle payload whose SHA-256 matches its recorded pin.

    Used for a nested blob inside an outer pickle: the inner payload gets its
    own pin under its own key, so it is vouched for in its own right rather
    than inheriting the outer file's trust.
    """
    if not isinstance(data, (bytes, bytearray, memoryview)):
        raise TypeError(f"expected bytes-like payload, got {type(data).__name__}")
    payload = bytes(data)
    resolved_store = store if isinstance(store, PinStore) else PinStore(store)
    digest = sha256_bytes(payload)

    _gate(
        digest,
        len(payload),
        key=key,
        store=resolved_store,
        allow_record_on_first_use=allow_record_on_first_use,
        note=note,
        origin=origin,
    )

    return pickle.load(io.BytesIO(payload), **pickle_kwargs)  # noqa: S301 - gated above


def open_verified(
    path: os.PathLike[str] | str,
    *,
    key: Optional[str] = None,
    store: Optional[PinStore] = None,
    allow_record_on_first_use: Optional[bool] = None,
    note: str = "",
) -> BinaryIO:
    """Verify ``path`` against its pin and return an open binary handle.

    For callers that must drive the deserialiser themselves (``torch.load``,
    ``joblib.load``, a custom ``Unpickler``). Same gate, same refusal.
    """
    artifact = Path(path)
    if not artifact.is_file():
        raise FileNotFoundError(f"artifact not found: {artifact}")
    resolved_store = store if store is not None else _default_store_for(artifact)
    _gate(
        sha256_file(artifact),
        artifact.stat().st_size,
        key=key if key is not None else artifact.name,
        store=resolved_store,
        allow_record_on_first_use=allow_record_on_first_use,
        note=note,
        origin=str(artifact),
    )
    return open(artifact, "rb")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _selftest() -> int:
    """Ground-truth checks that need no repository and write only to a tempdir."""
    import shutil
    import tempfile as _tf

    failures: list[str] = []

    def check(name: str, cond: bool, detail: str = "") -> None:
        if cond:
            print(f"  PASS  {name}")
        else:
            print(f"  FAIL  {name} {detail}")
            failures.append(name)

    tmp = Path(_tf.mkdtemp(prefix="safe_pickle_selftest_"))
    try:
        art = tmp / "payload.pkl"
        art.write_bytes(pickle.dumps({"a": 1}))
        store = PinStore(tmp / PIN_FILE_NAME)

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            first = safe_pickle_load(art, store=store, allow_record_on_first_use=True)
        check("record-on-first-use loads", first == {"a": 1})
        check(
            "record-on-first-use warns loudly",
            any(issubclass(w.category, UnpinnedPickleWarning) for w in caught),
        )
        check("pin written", store.get("payload.pkl") is not None)

        with warnings.catch_warnings(record=True) as caught2:
            warnings.simplefilter("always")
            second = safe_pickle_load(art, store=store)
        check("verified load succeeds", second == {"a": 1})
        check("verified load is silent", not caught2)

        art.write_bytes(pickle.dumps({"a": 2}))
        try:
            safe_pickle_load(art, store=store)
            check("mismatch refused", False, "(no exception raised)")
        except PickleIntegrityError:
            check("mismatch refused", True)

        unpinned = tmp / "other.pkl"
        unpinned.write_bytes(pickle.dumps([1, 2, 3]))
        try:
            safe_pickle_load(unpinned, store=store, allow_record_on_first_use=False)
            check("strict refuses unpinned", False, "(no exception raised)")
        except PickleIntegrityError:
            check("strict refuses unpinned", True)

        blob = pickle.dumps(["inner"])
        s2 = PinStore(tmp / "inner-pins.json")
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            check(
                "loads() records then verifies",
                safe_pickle_loads(blob, key="k", store=s2) == ["inner"]
                and safe_pickle_loads(blob, key="k", store=s2) == ["inner"],
            )
        try:
            safe_pickle_loads(pickle.dumps(["tampered"]), key="k", store=s2)
            check("loads() mismatch refused", False, "(no exception raised)")
        except PickleIntegrityError:
            check("loads() mismatch refused", True)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print()
    if failures:
        print(f"SELFTEST FAILED: {len(failures)} check(s): {', '.join(failures)}")
        return 1
    print("SELFTEST PASSED")
    return 0


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m tools.security.safe_pickle",
        description="Hash-pin pickle artifacts (Work Packet 9.1). "
        "Pinning never unpickles.",
    )
    parser.add_argument("artifact", nargs="?", help="path to the pickle artifact")
    parser.add_argument("--key", default=None, help="pin-store key (default: basename)")
    parser.add_argument("--pins", default=None, help="pin file (default: alongside)")
    parser.add_argument("--note", default="", help="note stored with a new pin")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--show", action="store_true", help="print recorded pins")
    mode.add_argument("--pin", action="store_true", help="record a pin if absent")
    mode.add_argument("--repin", action="store_true", help="replace an existing pin")
    mode.add_argument("--verify", action="store_true", help="check without loading")
    mode.add_argument("--selftest", action="store_true", help="run built-in checks")
    args = parser.parse_args(argv)

    if args.selftest:
        return _selftest()

    if not args.artifact:
        parser.error("an artifact path is required unless --selftest is given")

    artifact = Path(args.artifact)
    store = PinStore(args.pins) if args.pins else _default_store_for(artifact)
    key = args.key or artifact.name

    if args.show:
        entries = store.entries()
        print(f"pin file: {store.path}")
        if not entries:
            print("  (no pins recorded)")
        for name, entry in entries.items():
            print(f"  {name}\n    sha256 {entry.get('sha256')}\n"
                  f"    size   {entry.get('size_bytes')}\n"
                  f"    at     {entry.get('recorded_at')}  by {entry.get('recorded_by')}")
            if entry.get("note"):
                print(f"    note   {entry['note']}")
        return 0

    if not artifact.is_file():
        print(f"artifact not found: {artifact}", file=sys.stderr)
        return 2

    digest = sha256_file(artifact)
    size = artifact.stat().st_size

    if args.pin or args.repin:
        store.record(
            key,
            digest,
            size_bytes=size,
            note=args.note,
            recorded_by="cli --repin" if args.repin else "cli --pin",
            overwrite=bool(args.repin),
        )
        print(f"pinned {key} = {digest} ({size} bytes) in {store.path}")
        return 0

    # default and --verify: check, do not load
    entry = store.get(key)
    if entry is None:
        print(f"NO PIN   {key}: actual {digest} (not recorded in {store.path})")
        return 1
    if str(entry.get("sha256", "")).lower() != digest:
        print(f"MISMATCH {key}\n  expected {entry.get('sha256')}\n  actual   {digest}")
        return 1
    print(f"OK       {key} = {digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
