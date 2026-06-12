"""Deprecated alias for ``muse_time`` (hermes_time was renamed).

Permanent compatibility shim (PIL/Pillow style) — do not remove. The alias
shares the *same module object* as ``muse_time``, so string-based
``mock.patch("hermes_time.X")`` targets and old imports keep working.
"""

import sys as _sys
import warnings as _warnings

import muse_time as _target

_warnings.warn(
    "'hermes_time' is deprecated; import 'muse_time' "
    "(this alias is permanent)",
    DeprecationWarning,
    stacklevel=2,
)

_sys.modules[__name__] = _target
