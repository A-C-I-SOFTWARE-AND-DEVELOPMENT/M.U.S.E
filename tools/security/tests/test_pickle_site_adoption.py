"""Adoption tests for the three §9.1 pickle load sites.

The helper being correct is not the same as the sites using it. These tests
drive the real call sites:

* ``hermes_cli/jarvis_prime/research_fabric/autoresearch/vendor/prepare.py``
  (``Tokenizer.from_directory`` — was ``pickle.load`` at line 219)
* ``optional-skills/research/darwinian-evolver/scripts/show_snapshot.py``
  (was ``pickle.loads`` at lines 59 and 62: the outer snapshot and the inner
  ``population_snapshot`` blob)

``prepare.py`` imports torch/tiktoken/rustbpe/pyarrow at module scope, which are
not installed in every environment, so its site is exercised by loading the
module source under stubbed third-party modules rather than by skipping. The
gate under test is the ``Tokenizer.from_directory`` body, which touches none of
them.
"""

from __future__ import annotations

import ast
import hashlib
import importlib.util
import os
import pickle
import subprocess
import sys
from pathlib import Path
from unittest import mock

import pytest

from tools.security.safe_pickle import PIN_FILE_NAME, PinStore, sha256_bytes

REPO_ROOT = Path(__file__).resolve().parents[3]
PREPARE_PY = (
    REPO_ROOT
    / "hermes_cli/jarvis_prime/research_fabric/autoresearch/vendor/prepare.py"
)
SHOW_SNAPSHOT_PY = (
    REPO_ROOT / "optional-skills/research/darwinian-evolver/scripts/show_snapshot.py"
)


def test_target_files_exist() -> None:
    assert PREPARE_PY.is_file(), PREPARE_PY
    assert SHOW_SNAPSHOT_PY.is_file(), SHOW_SNAPSHOT_PY


# ---------------------------------------------------------------------------
# Source-level assertions: no un-gated pickle load remains at the three sites
# ---------------------------------------------------------------------------


def _deserialisation_calls(path: Path) -> list[str]:
    """Return every real ``pickle.load``/``loads``/``Unpickler`` *call* in a file.

    Parsed with :mod:`ast`, not grepped: both files now discuss ``pickle.load``
    in prose, and a comment explaining why the call was removed must not read as
    the call still being there.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Attribute) and func.attr in {
            "load",
            "loads",
            "Unpickler",
        }:
            value = func.value
            if isinstance(value, ast.Name) and value.id in {"pickle", "cPickle", "dill"}:
                found.append(f"{value.id}.{func.attr} at line {node.lineno}")
        elif isinstance(func, ast.Name) and func.id in {"loads", "Unpickler"}:
            found.append(f"{func.id} at line {node.lineno}")
    return found


def test_no_raw_pickle_load_remains_at_the_three_sites() -> None:
    assert _deserialisation_calls(PREPARE_PY) == []
    assert _deserialisation_calls(SHOW_SNAPSHOT_PY) == []

    prepare_src = PREPARE_PY.read_text(encoding="utf-8")
    snapshot_src = SHOW_SNAPSHOT_PY.read_text(encoding="utf-8")

    # prepare.py still legitimately *writes* a pickle; only reads are gated.
    assert "pickle.dump(" in prepare_src
    assert "safe_pickle_load(" in prepare_src

    # show_snapshot.py no longer imports pickle at all.
    assert "\nimport pickle" not in snapshot_src
    assert "safe_pickle_load(" in snapshot_src
    assert "safe_pickle_loads(" in snapshot_src


def test_the_ast_check_would_actually_catch_a_regression(tmp_path: Path) -> None:
    """Control for the test above: a file that does load raw pickle is detected."""
    regressed = tmp_path / "regressed.py"
    regressed.write_text(
        "import pickle\n"
        "# a comment merely mentioning pickle.load() must not count\n"
        "def f(p):\n"
        "    return pickle.load(open(p, 'rb'))\n",
        encoding="utf-8",
    )
    assert _deserialisation_calls(regressed) == ["pickle.load at line 4"]

    clean = tmp_path / "clean.py"
    clean.write_text(
        '"""Docstring mentioning pickle.load() and pickle.loads()."""\n'
        "# refusing to fall back to a bare pickle.load()\n"
        "X = 1\n",
        encoding="utf-8",
    )
    assert _deserialisation_calls(clean) == []


# ---------------------------------------------------------------------------
# prepare.py — Tokenizer.from_directory
# ---------------------------------------------------------------------------


class _FakeEncoding:
    """Stands in for a tiktoken Encoding; picklable, no third-party deps."""

    n_vocab = 8192

    def encode_single_token(self, token: str) -> int:
        return 0


@pytest.fixture()
def prepare_module(monkeypatch: pytest.MonkeyPatch):
    """Load prepare.py with its heavy third-party imports stubbed out.

    ``MagicMock`` rather than an empty module, because prepare.py applies
    ``@torch.no_grad()`` as a module-level decorator. The gate under test —
    ``Tokenizer.from_directory`` — touches none of these.
    """
    for name in ("requests", "rustbpe", "tiktoken", "torch"):
        if name not in sys.modules:
            monkeypatch.setitem(sys.modules, name, mock.MagicMock(name=name))
    if "pyarrow.parquet" not in sys.modules:
        pyarrow = mock.MagicMock(name="pyarrow")
        monkeypatch.setitem(sys.modules, "pyarrow", pyarrow)
        monkeypatch.setitem(sys.modules, "pyarrow.parquet", pyarrow.parquet)

    spec = importlib.util.spec_from_file_location(
        "_muse_test_prepare_vendor", str(PREPARE_PY)
    )
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, "_muse_test_prepare_vendor", module)
    spec.loader.exec_module(module)
    return module


def test_prepare_tokenizer_records_then_verifies_then_refuses(
    prepare_module, tmp_path: Path
) -> None:
    tokenizer_dir = tmp_path / "tokenizer"
    tokenizer_dir.mkdir()
    pkl = tokenizer_dir / "tokenizer.pkl"
    pkl.write_bytes(pickle.dumps(_FakeEncoding()))

    # First load: unpinned, so it records with a loud warning.
    with pytest.warns(UserWarning, match="no SHA-256 pin was recorded"):
        tok = prepare_module.Tokenizer.from_directory(str(tokenizer_dir))
    assert tok.get_vocab_size() == 8192

    store = PinStore(tokenizer_dir / PIN_FILE_NAME)
    assert store.get("tokenizer.pkl") is not None

    # Second load: pin matches, silent.
    assert prepare_module.Tokenizer.from_directory(str(tokenizer_dir)) is not None

    # The §9.1 scenario: the cache directory is repopulated from a downloaded
    # artifact. It is refused, and nothing is unpickled.
    from tools.security.safe_pickle import PickleIntegrityError

    pkl.write_bytes(pickle.dumps({"not": "a tokenizer"}))
    with pytest.raises(PickleIntegrityError, match="does not match its recorded pin"):
        prepare_module.Tokenizer.from_directory(str(tokenizer_dir))


def test_prepare_helper_bootstrap_finds_the_module(prepare_module) -> None:
    """The walk-up loader must work even though prepare.py is run as a script."""
    module = prepare_module._load_safe_pickle_module()
    assert hasattr(module, "safe_pickle_load")
    assert hasattr(module, "PinStore")
    assert module.PIN_FILE_NAME == PIN_FILE_NAME


def test_prepare_bootstrap_fails_closed_when_helper_is_missing(
    prepare_module, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """With no tools/security on any parent path, it raises rather than falling back."""
    orphan = tmp_path / "deep" / "vendor"
    orphan.mkdir(parents=True)
    fake_file = orphan / "prepare.py"
    fake_file.write_text("", encoding="utf-8")

    monkeypatch.setattr(prepare_module, "__file__", str(fake_file))
    # Make the package import fail too, so only the walk-up path is exercised.
    monkeypatch.setitem(sys.modules, "tools.security", None)
    with pytest.raises(ImportError, match="Refusing to fall back"):
        prepare_module._load_safe_pickle_module()


# ---------------------------------------------------------------------------
# show_snapshot.py — both load sites, driven as a real subprocess
# ---------------------------------------------------------------------------


class _Organism:
    def __init__(self, prompt_template: str) -> None:
        self.id = "org-1"
        self.prompt_template = prompt_template


class _Result:
    def __init__(self, score: float) -> None:
        self.score = score


def test_pickled_fixtures_are_importable_by_a_subprocess() -> None:
    """show_snapshot unpickles real objects, so their module must be importable.

    If this fails the subprocess tests below would fail for an uninteresting
    reason, so it is asserted separately rather than papered over with a skip.
    """
    assert __name__ == "tools.security.tests.test_pickle_site_adoption", __name__
    assert _Organism.__module__ == __name__


def _make_snapshot(path: Path) -> bytes:
    """Write a snapshot whose organisms are importable from this test module."""
    inner = pickle.dumps({"organisms": [(_Organism("hello world"), _Result(0.75))]})
    path.write_bytes(pickle.dumps({"population_snapshot": inner}))
    return inner


def _run_show_snapshot(*args: str, **extra_env: str) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(REPO_ROOT)
    env.update(extra_env)
    return subprocess.run(
        [sys.executable, str(SHOW_SNAPSHOT_PY), *args],
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )


def test_show_snapshot_gate_records_verifies_and_refuses(tmp_path: Path) -> None:
    # The pin store MUST live outside the snapshot's directory. A pin that
    # travels with the file it vouches for vouches for nothing -- see
    # test_show_snapshot_bundled_pin_cannot_waive_the_gate below.
    incoming = tmp_path / "incoming"
    incoming.mkdir()
    snapshot = incoming / "iteration_3.pkl"
    inner_bytes = _make_snapshot(snapshot)
    pins = tmp_path / "trusted" / PIN_FILE_NAME

    # 1. Unpinned and unacknowledged: refused, and nothing is pinned.
    first = _run_show_snapshot(str(snapshot), "--pins", str(pins))
    assert first.returncode != 0
    assert "no recorded SHA-256 pin" in first.stderr
    assert not pins.exists()

    # 2. Acknowledged: loads, and records both the outer file and the inner blob.
    second = _run_show_snapshot(str(snapshot), "--pins", str(pins), "--i-trust-this-file")
    assert second.returncode == 0, second.stderr
    assert "hello world" in second.stdout
    store = PinStore(pins)
    assert store.get("iteration_3.pkl") is not None
    assert store.get("iteration_3.pkl#population_snapshot")["sha256"] == sha256_bytes(
        inner_bytes
    )

    # 3. Pinned in a store the supplier does not control: loads with no flag.
    third = _run_show_snapshot(str(snapshot), "--pins", str(pins))
    assert third.returncode == 0, third.stderr
    assert "hello world" in third.stdout

    # 4. Swapped snapshot: refused even *with* the acknowledgement flag.
    snapshot.write_bytes(
        pickle.dumps({"population_snapshot": pickle.dumps({"organisms": []})})
    )
    fourth = _run_show_snapshot(str(snapshot), "--pins", str(pins), "--i-trust-this-file")
    assert fourth.returncode != 0
    assert "does not match its recorded pin" in fourth.stderr


def test_show_snapshot_bundled_pin_cannot_waive_the_gate(tmp_path: Path) -> None:
    """A pin shipped alongside the snapshot must not satisfy the trust gate.

    Regression test for a real regression introduced while adopting the
    hash-pinning helper here. The pin file defaulted to sitting beside the
    snapshot, so an attacker shipping `evolved.pkl` and `.muse-pickle-pins.json`
    in one tarball produced `already_pinned == True`, the acknowledgement was
    skipped, and `__reduce__` executed with no flag and no warning -- while the
    code *before* the adoption had refused. The pin must live somewhere the
    supplier of the artifact cannot write.
    """
    incoming = tmp_path / "incoming"
    incoming.mkdir()
    snapshot = incoming / "evolved.pkl"
    inner_bytes = _make_snapshot(snapshot)

    # The attacker supplies a pin that correctly describes their own payload.
    hostile_pins = incoming / PIN_FILE_NAME
    store = PinStore(hostile_pins)
    store.record(
        "evolved.pkl",
        hashlib.sha256(snapshot.read_bytes()).hexdigest(),
        size_bytes=snapshot.stat().st_size,
        recorded_by="attacker",
    )
    store.record(
        "evolved.pkl#population_snapshot",
        sha256_bytes(inner_bytes),
        size_bytes=len(inner_bytes),
        recorded_by="attacker",
    )

    # Default store: the bundled pin must be ignored for trust purposes.
    defaulted = _run_show_snapshot(str(snapshot))
    assert defaulted.returncode != 0, (
        "a snapshot bundled with its own pin was loaded without acknowledgement"
    )
    assert "no recorded SHA-256 pin" in defaulted.stderr

    # Even pointed at explicitly, a pin inside the snapshot's own directory
    # cannot waive the gate.
    explicit = _run_show_snapshot(str(snapshot), "--pins", str(hostile_pins))
    assert explicit.returncode != 0, (
        "an explicitly-supplied pin from the snapshot's own directory waived the gate"
    )


def test_show_snapshot_inner_blob_swap_is_refused(tmp_path: Path) -> None:
    """The outer file can be re-pinned while the inner blob is hostile."""
    incoming = tmp_path / "incoming"
    incoming.mkdir()
    snapshot = incoming / "iteration_9.pkl"
    _make_snapshot(snapshot)
    pins = tmp_path / "trusted" / PIN_FILE_NAME

    ok = _run_show_snapshot(str(snapshot), "--pins", str(pins), "--i-trust-this-file")
    assert ok.returncode == 0, ok.stderr

    # Replace only the inner blob, then deliberately re-pin the outer file so
    # the outer check passes. The inner pin must still catch it.
    snapshot.write_bytes(
        pickle.dumps({"population_snapshot": pickle.dumps({"organisms": []})})
    )
    store = PinStore(pins)
    store.record(
        "iteration_9.pkl",
        hashlib.sha256(snapshot.read_bytes()).hexdigest(),
        size_bytes=snapshot.stat().st_size,
        overwrite=True,
        recorded_by="test",
    )

    refused = _run_show_snapshot(str(snapshot), "--pins", str(pins))
    assert refused.returncode != 0
    assert "does not match its recorded pin" in refused.stderr
    assert "population_snapshot" in refused.stderr


def test_show_snapshot_strict_mode_refuses_unpinned(tmp_path: Path) -> None:
    incoming = tmp_path / "incoming"
    incoming.mkdir()
    snapshot = incoming / "iteration_1.pkl"
    _make_snapshot(snapshot)
    result = _run_show_snapshot(
        str(snapshot), "--pins", str(tmp_path / "trusted" / PIN_FILE_NAME),
        "--i-trust-this-file", MUSE_PICKLE_PINS_STRICT="1"
    )
    assert result.returncode != 0
    assert "record-on-first-use is disabled" in result.stderr


def test_show_snapshot_custom_pin_file(tmp_path: Path) -> None:
    snapshot = tmp_path / "iteration_5.pkl"
    _make_snapshot(snapshot)
    pins = tmp_path / "custom-pins.json"
    ok = _run_show_snapshot(
        str(snapshot), "--i-trust-this-file", "--pins", str(pins)
    )
    assert ok.returncode == 0, ok.stderr
    assert pins.is_file()
    assert not (tmp_path / PIN_FILE_NAME).exists()
