"""Deprecated alias for ``muse_bootstrap`` (hermes_bootstrap was renamed).

Permanent compatibility shim (PIL/Pillow style) — do not remove. The alias
shares the *same module object* as ``muse_bootstrap``, so string-based
``mock.patch("hermes_bootstrap.X")`` targets and old imports keep working.
"""

import sys as _sys
import warnings as _warnings

import muse_bootstrap as _target

_warnings.warn(
    "'hermes_bootstrap' is deprecated; import 'muse_bootstrap' "
    "(this alias is permanent)",
    DeprecationWarning,
    stacklevel=2,
)

_sys.modules[__name__] = _target
