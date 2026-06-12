"""Deprecated alias for ``muse_constants`` (hermes_constants was renamed).

Permanent compatibility shim (PIL/Pillow style) — do not remove. The alias
shares the *same module object* as ``muse_constants``, so string-based
``mock.patch("hermes_constants.X")`` targets and old imports keep working.
"""

import sys as _sys
import warnings as _warnings

import muse_constants as _target

_warnings.warn(
    "'hermes_constants' is deprecated; import 'muse_constants' "
    "(this alias is permanent)",
    DeprecationWarning,
    stacklevel=2,
)

_sys.modules[__name__] = _target
