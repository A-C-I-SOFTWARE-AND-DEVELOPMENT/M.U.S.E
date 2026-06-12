"""Deprecated alias for ``muse_state`` (hermes_state was renamed).

Permanent compatibility shim (PIL/Pillow style) — do not remove. The alias
shares the *same module object* as ``muse_state``, so string-based
``mock.patch("hermes_state.X")`` targets and old imports keep working.
"""

import sys as _sys
import warnings as _warnings

import muse_state as _target

_warnings.warn(
    "'hermes_state' is deprecated; import 'muse_state' "
    "(this alias is permanent)",
    DeprecationWarning,
    stacklevel=2,
)

_sys.modules[__name__] = _target
