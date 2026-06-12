"""Deprecated alias for ``muse_model_catalog`` (hermes_model_catalog was renamed).

Permanent compatibility shim (PIL/Pillow style) — do not remove. The alias
shares the *same module object* as ``muse_model_catalog``, so string-based
``mock.patch("hermes_model_catalog.X")`` targets and old imports keep working.
"""

import sys as _sys
import warnings as _warnings

import muse_model_catalog as _target

_warnings.warn(
    "'hermes_model_catalog' is deprecated; import 'muse_model_catalog' "
    "(this alias is permanent)",
    DeprecationWarning,
    stacklevel=2,
)

_sys.modules[__name__] = _target
