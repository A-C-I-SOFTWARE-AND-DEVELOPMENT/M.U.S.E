"""Tests for the hash-pinned pickle gate.

The load-bearing test is :func:`test_tampered_artifact_never_executes`: it
builds a pickle whose ``__reduce__`` writes a sentinel file when unpickled,
swaps it in behind a recorded pin, and asserts the sentinel never appears. That
is the actual security property — "refuses on mismatch" is only meaningful if
the refusal happens *before* the opcodes run.
"""

from __future__ import annotations

import json
import os
import pickle
import subprocess
import sys
import warnings
from pathlib import Path

import pytest

from tools.security.safe_pickle import (
    PIN_FILE_NAME,
    PIN_FILE_VERSION,
    PickleIntegrityError,
    PinStore,
    UnpinnedPickleWarning,
    open_verified,
    safe_pickle_load,
    safe_pickle_loads,
    sha256_bytes,
    sha256_file,
)


@pytest.fixture()
def store(tmp_path: Path) -> PinStore:
    return PinStore(tmp_path / PIN_FILE_NAME)


def _write_pickle(path: Path, obj: object) -> Path:
    path.write_bytes(pickle.dumps(obj))
    return path


# ---------------------------------------------------------------------------
# The security property
# ---------------------------------------------------------------------------


class _Detonator:
    """Unpickling this writes a sentinel file. Stands in for a malicious payload."""

    def __init__(self, sentinel: str) -> None:
        self.sentinel = sentinel

    def __reduce__(self):  # pragma: no cover - only runs if the gate fails
        return (_write_sentinel, (self.sentinel,))


def _write_sentinel(path: str) -> str:  # pragma: no cover - see above
    Path(path).write_text("detonated", encoding="utf-8")
    return path


def test_detonator_really_would_execute(tmp_path: Path) -> None:
    """Control: raw pickle.load on the payload does execute it.

    Without this the main test could pass for the wrong reason (a payload that
    does nothing).
    """
    sentinel = tmp_path / "control.txt"
    blob = pickle.dumps(_Detonator(str(sentinel)))
    assert not sentinel.exists()
    pickle.loads(blob)
    assert sentinel.read_text(encoding="utf-8") == "detonated"


def test_tampered_artifact_never_executes(tmp_path: Path, store: PinStore) -> None:
    """A swapped artifact is refused *before* the unpickler sees an opcode."""
    artifact = _write_pickle(tmp_path / "tokenizer.pkl", {"vocab_size": 8192})
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UnpinnedPickleWarning)
        assert safe_pickle_load(artifact, store=store) == {"vocab_size": 8192}

    sentinel = tmp_path / "boom.txt"
    artifact.write_bytes(pickle.dumps(_Detonator(str(sentinel))))

    with pytest.raises(PickleIntegrityError) as excinfo:
        safe_pickle_load(artifact, store=store)

    assert not sentinel.exists(), "payload executed despite the pin mismatch"
    assert "does not match its recorded pin" in str(excinfo.value)
    assert "Nothing was unpickled" in str(excinfo.value)


def test_strict_mode_refuses_unpinned_payload_without_executing(
    tmp_path: Path, store: PinStore
) -> None:
    sentinel = tmp_path / "boom-strict.txt"
    artifact = tmp_path / "hostile.pkl"
    artifact.write_bytes(pickle.dumps(_Detonator(str(sentinel))))

    with pytest.raises(PickleIntegrityError):
        safe_pickle_load(artifact, store=store, allow_record_on_first_use=False)

    assert not sentinel.exists()
    assert store.get("hostile.pkl") is None, "a refused artifact must not be pinned"


# ---------------------------------------------------------------------------
# Record-on-first-use, then refuse thereafter
# ---------------------------------------------------------------------------


def test_record_on_first_use_warns_loudly_and_records(
    tmp_path: Path, store: PinStore, capsys: pytest.CaptureFixture[str]
) -> None:
    artifact = _write_pickle(tmp_path / "snapshot.pkl", ["a", "b"])

    with pytest.warns(UnpinnedPickleWarning) as caught:
        assert safe_pickle_load(artifact, store=store, note="unit test") == ["a", "b"]

    message = str(caught[0].message)
    assert "no SHA-256 pin was recorded" in message
    assert "HERMES_PICKLE_PINS_STRICT" in message
    # Loud means loud: it also reaches stderr, not only the warnings filter.
    assert "SECURITY: no SHA-256 pin was recorded" in capsys.readouterr().err

    entry = store.get("snapshot.pkl")
    assert entry is not None
    assert entry["sha256"] == sha256_file(artifact)
    assert entry["size_bytes"] == artifact.stat().st_size
    assert entry["note"] == "unit test"
    assert entry["recorded_by"] == "record-on-first-use"
    assert entry["recorded_at"].endswith("Z")


def test_second_load_verifies_silently(tmp_path: Path, store: PinStore) -> None:
    artifact = _write_pickle(tmp_path / "snapshot.pkl", {"k": 1})
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UnpinnedPickleWarning)
        safe_pickle_load(artifact, store=store)

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        assert safe_pickle_load(artifact, store=store) == {"k": 1}
    assert [w for w in caught if issubclass(w.category, UnpinnedPickleWarning)] == []


def test_env_var_switches_default_to_strict(
    tmp_path: Path, store: PinStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    artifact = _write_pickle(tmp_path / "x.pkl", 1)
    monkeypatch.setenv("HERMES_PICKLE_PINS_STRICT", "1")
    with pytest.raises(PickleIntegrityError, match="record-on-first-use is disabled"):
        safe_pickle_load(artifact, store=store)

    monkeypatch.setenv("HERMES_PICKLE_PINS_STRICT", "0")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UnpinnedPickleWarning)
        assert safe_pickle_load(artifact, store=store) == 1


def test_mismatch_is_not_silently_repinned(tmp_path: Path, store: PinStore) -> None:
    artifact = _write_pickle(tmp_path / "x.pkl", 1)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UnpinnedPickleWarning)
        safe_pickle_load(artifact, store=store)
    first = store.get("x.pkl")["sha256"]

    _write_pickle(artifact, 2)
    with pytest.raises(PickleIntegrityError):
        safe_pickle_load(artifact, store=store)
    assert store.get("x.pkl")["sha256"] == first, "pin was rewritten by a failed load"

    with pytest.raises(PickleIntegrityError, match="refusing to overwrite"):
        store.record("x.pkl", sha256_file(artifact), size_bytes=1)

    store.record("x.pkl", sha256_file(artifact), size_bytes=1, overwrite=True)
    assert store.get("x.pkl")["sha256"] != first


# ---------------------------------------------------------------------------
# Pin file format and durability
# ---------------------------------------------------------------------------


def test_pin_file_is_versioned_json(tmp_path: Path, store: PinStore) -> None:
    artifact = _write_pickle(tmp_path / "x.pkl", 1)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UnpinnedPickleWarning)
        safe_pickle_load(artifact, store=store)

    doc = json.loads(store.path.read_text(encoding="utf-8"))
    assert doc["version"] == PIN_FILE_VERSION
    assert "only load what we already vouched for" in doc["_comment"]
    assert set(doc["pins"]["x.pkl"]) == {
        "sha256",
        "size_bytes",
        "recorded_at",
        "recorded_by",
        "note",
    }


def test_unsupported_pin_file_version_refuses(tmp_path: Path) -> None:
    pins = tmp_path / PIN_FILE_NAME
    pins.write_text(json.dumps({"version": 99, "pins": {}}), encoding="utf-8")
    artifact = _write_pickle(tmp_path / "x.pkl", 1)
    with pytest.raises(PickleIntegrityError, match="not supported by this build"):
        safe_pickle_load(artifact, store=PinStore(pins))


def test_corrupt_pin_file_refuses_rather_than_treating_it_as_empty(
    tmp_path: Path,
) -> None:
    pins = tmp_path / PIN_FILE_NAME
    pins.write_text("{not json", encoding="utf-8")
    artifact = _write_pickle(tmp_path / "x.pkl", 1)
    with pytest.raises(PickleIntegrityError, match="unreadable"):
        safe_pickle_load(artifact, store=PinStore(pins))


def test_no_temp_files_left_behind(tmp_path: Path, store: PinStore) -> None:
    artifact = _write_pickle(tmp_path / "x.pkl", 1)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UnpinnedPickleWarning)
        safe_pickle_load(artifact, store=store)
    leftovers = [p.name for p in tmp_path.iterdir() if p.name.endswith(".tmp")]
    assert leftovers == []


def test_missing_artifact_raises_file_not_found(tmp_path: Path, store: PinStore) -> None:
    with pytest.raises(FileNotFoundError):
        safe_pickle_load(tmp_path / "nope.pkl", store=store)


# ---------------------------------------------------------------------------
# Nested payloads
# ---------------------------------------------------------------------------


def test_inner_blob_is_pinned_in_its_own_right(tmp_path: Path) -> None:
    inner = pickle.dumps({"organisms": [1, 2, 3]})
    outer_path = _write_pickle(tmp_path / "iteration_7.pkl", {"population_snapshot": inner})
    store = PinStore(tmp_path / PIN_FILE_NAME)

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UnpinnedPickleWarning)
        outer = safe_pickle_load(outer_path, store=store)
        got = safe_pickle_loads(
            outer["population_snapshot"],
            key="iteration_7.pkl#population_snapshot",
            store=store,
        )
    assert got == {"organisms": [1, 2, 3]}
    assert store.get("iteration_7.pkl#population_snapshot")["sha256"] == sha256_bytes(inner)

    sentinel = tmp_path / "inner-boom.txt"
    with pytest.raises(PickleIntegrityError):
        safe_pickle_loads(
            pickle.dumps(_Detonator(str(sentinel))),
            key="iteration_7.pkl#population_snapshot",
            store=store,
        )
    assert not sentinel.exists()


def test_loads_rejects_non_bytes(tmp_path: Path) -> None:
    with pytest.raises(TypeError):
        safe_pickle_loads("not bytes", key="k", store=tmp_path / PIN_FILE_NAME)  # type: ignore[arg-type]


def test_open_verified_gates_then_hands_back_a_handle(
    tmp_path: Path, store: PinStore
) -> None:
    artifact = _write_pickle(tmp_path / "x.pkl", {"z": 9})
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UnpinnedPickleWarning)
        with open_verified(artifact, store=store) as handle:
            assert pickle.load(handle) == {"z": 9}

    _write_pickle(artifact, {"z": 10})
    with pytest.raises(PickleIntegrityError):
        open_verified(artifact, store=store)


# ---------------------------------------------------------------------------
# Digests and CLI
# ---------------------------------------------------------------------------


def test_file_and_bytes_digests_agree(tmp_path: Path) -> None:
    payload = os.urandom(3 * 1024 * 1024 + 17)  # spans the streaming chunk size
    path = tmp_path / "big.bin"
    path.write_bytes(payload)
    assert sha256_file(path) == sha256_bytes(payload)


def _run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    repo_root = Path(__file__).resolve().parents[3]
    return subprocess.run(
        [sys.executable, "-m", "tools.security.safe_pickle", *args],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        check=False,
    )


def test_cli_pin_then_verify_then_detect_tamper(tmp_path: Path) -> None:
    artifact = _write_pickle(tmp_path / "cli.pkl", {"n": 1})
    pins = tmp_path / PIN_FILE_NAME

    unpinned = _run_cli(str(artifact), "--verify", "--pins", str(pins))
    assert unpinned.returncode == 1 and "NO PIN" in unpinned.stdout

    pinned = _run_cli(str(artifact), "--pin", "--pins", str(pins), "--note", "cli test")
    assert pinned.returncode == 0 and "pinned" in pinned.stdout

    ok = _run_cli(str(artifact), "--verify", "--pins", str(pins))
    assert ok.returncode == 0 and ok.stdout.startswith("OK")

    _write_pickle(artifact, {"n": 2})
    bad = _run_cli(str(artifact), "--verify", "--pins", str(pins))
    assert bad.returncode == 1 and "MISMATCH" in bad.stdout


def test_cli_selftest_passes() -> None:
    result = _run_cli("--selftest")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "SELFTEST PASSED" in result.stdout
