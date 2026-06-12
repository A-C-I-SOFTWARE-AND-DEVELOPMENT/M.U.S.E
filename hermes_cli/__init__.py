"""Deprecated alias package: ``hermes_cli`` was renamed to ``muse_cli``.

This shim is PERMANENT compatibility infrastructure (PIL/Pillow style), not a
temporary bridge — do not remove it. Importing ``hermes_cli`` or any of its
submodules returns the *same module object* as the corresponding ``muse_cli``
module, so:

- ``import hermes_cli.main`` and ``import muse_cli.main`` yield one module,
  never two copies (no duplicate state, ``isinstance`` stays correct);
- string-based targets like ``mock.patch("hermes_cli.config.X")``,
  ``monkeypatch.setattr("hermes_cli...")``, pickled module paths in session
  DBs and queued jobs all keep resolving;
- ``python -m hermes_cli.main`` runs exactly ``python -m muse_cli.main``
  (the alias loader implements ``get_code`` for runpy).

A bare ``sys.modules[__name__] = muse_cli`` would NOT be enough: submodule
imports under the old name would re-execute ``muse_cli/<mod>.py`` a second
time as distinct module objects. The meta-path finder below aliases the whole
``hermes_cli.*`` namespace lazily instead.
"""

import importlib
import importlib.abc
import importlib.machinery
import importlib.util
import sys
import warnings

_OLD, _NEW = "hermes_cli", "muse_cli"


class _AliasLoader(importlib.abc.Loader):
    def __init__(self, alias: str, target: str):
        self._alias, self._target = alias, target

    def create_module(self, spec):
        module = importlib.import_module(self._target)
        # Identity alias, not a copy. The import machinery's
        # _init_module_attrs(override=False) preserves the target's existing
        # __name__/__spec__/__loader__, so the real module is not mutated.
        sys.modules[self._alias] = module
        return module

    def exec_module(self, module):
        pass  # target already executed by the normal import

    def get_code(self, fullname):
        # runpy support: ``python -m hermes_cli.x`` executes the *target's*
        # code object under __main__ — exactly ``python -m muse_cli.x``.
        target_spec = importlib.util.find_spec(self._target)
        if target_spec is None or target_spec.loader is None:
            raise ImportError(f"cannot resolve {self._target!r} for {fullname!r}")
        get_code = getattr(target_spec.loader, "get_code", None)
        if get_code is None:
            raise ImportError(
                f"loader for {self._target!r} does not support get_code"
            )
        return get_code(self._target)


class _AliasFinder(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname != _OLD and not fullname.startswith(_OLD + "."):
            return None
        new_name = _NEW + fullname[len(_OLD):]
        target_spec = importlib.util.find_spec(new_name)
        if target_spec is None:
            return None
        warnings.warn(
            f"'{fullname}' is deprecated; use '{new_name}' (the hermes_cli "
            "package was renamed to muse_cli; this alias is permanent)",
            DeprecationWarning,
            stacklevel=2,
        )
        spec = importlib.machinery.ModuleSpec(
            fullname,
            _AliasLoader(fullname, new_name),
            origin=target_spec.origin,
            is_package=target_spec.submodule_search_locations is not None,
        )
        spec.submodule_search_locations = target_spec.submodule_search_locations
        # Mirror has_location so runpy populates __file__ from origin
        # (otherwise ``python -m hermes_cli.x`` runs with __file__=None).
        # _set_fileattr is the private backing field of the read-only
        # ModuleSpec.has_location property.
        spec._set_fileattr = target_spec.has_location  # ty: ignore[unresolved-attribute]
        return spec


if not any(isinstance(f, _AliasFinder) for f in sys.meta_path):
    sys.meta_path.insert(0, _AliasFinder())

warnings.warn(
    "'hermes_cli' is deprecated; import 'muse_cli' (this alias is permanent)",
    DeprecationWarning,
    stacklevel=2,
)

# This module itself becomes an identity alias of muse_cli. The import
# machinery re-reads sys.modules after executing a module body, so replacing
# our own entry here is a supported pattern.
sys.modules[__name__] = importlib.import_module(_NEW)
