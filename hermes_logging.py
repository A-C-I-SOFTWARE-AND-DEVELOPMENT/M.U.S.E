"""Deprecated alias for ``muse_logging`` (hermes_logging was renamed).

Permanent compatibility shim (PIL/Pillow style) — do not remove. The alias
shares the *same module object* as ``muse_logging``, so string-based
``mock.patch("hermes_logging.X")`` targets and old imports keep working.
"""

import sys as _sys
import warnings as _warnings

import muse_logging as _target

_warnings.warn(
    "'hermes_logging' is deprecated; import 'muse_logging' "
    "(this alias is permanent)",
    DeprecationWarning,
    stacklevel=2,
)

_sys.modules[__name__] = _target
