"""Autodiscovery for the ``methods_*`` @method handler modules.

server.py used to name every handler family twice — once in a ``from . import
(...)`` tuple and once in a registration tuple — so a new method family meant
two hand-edits in the middle of a 19K-line file, and a typo in either list
silently dropped a whole family of RPC methods.

This module walks ``tui_gateway/methods_*.py`` instead.  Discovery is by file
name, so adding ``methods_rooms.py`` with a ``register(server)`` is the whole
change.  See :mod:`tui_gateway.method_ctx` for why ``register`` exists at all
(handlers are rebound onto server.py's globals rather than moved).

Two properties this deliberately guarantees:

* **Deterministic order.**  Modules are imported and installed in sorted name
  order, never in filesystem order, so registration order is a property of the
  names and not of the directory listing.  Handler names are unique across the
  families today, so order does not change the resulting ``_methods`` map — but
  order that depends on luck is a bug waiting to be written.
* **One broken family does not take the gateway down.**  An import or install
  error is logged with a traceback and skipped; the rest of the RPC surface
  still comes up.
"""

import importlib
import logging
import pkgutil
from pathlib import Path

logger = logging.getLogger(__name__)

#: Filename prefix that marks a split ``@method`` handler family.
METHOD_MODULE_PREFIX = "methods_"

_PACKAGE = __package__ or "tui_gateway"
_PACKAGE_PATH = str(Path(__file__).resolve().parent)


def discover_method_modules() -> list[str]:
    """Return the ``methods_*`` submodule names of this package, sorted.

    Names are bare submodule names (``"methods_tools"``), not dotted paths.
    """
    return sorted(
        name
        for _finder, name, ispkg in pkgutil.iter_modules([_PACKAGE_PATH])
        if not ispkg and name.startswith(METHOD_MODULE_PREFIX)
    )


def install_method_modules(server) -> list[str]:
    """Import every ``methods_*`` module and install its handlers on ``server``.

    ``server`` is the live ``tui_gateway.server`` module object: each family's
    ``register()`` rebinds its handlers onto that namespace's globals and drops
    them into ``server._methods``.

    Returns the names of the modules that installed successfully, in the order
    they were installed.  Failures are logged and skipped so a single broken
    family cannot stop the gateway from serving the rest.
    """
    installed: list[str] = []

    for name in discover_method_modules():
        try:
            module = importlib.import_module(f".{name}", _PACKAGE)
        except Exception:
            logger.exception("method module %s failed to import; skipping", name)
            continue

        register = getattr(module, "register", None)
        if not callable(register):
            logger.warning("method module %s has no register(server); skipping", name)
            continue

        try:
            register(server)
        except Exception:
            logger.exception("method module %s failed to register; skipping", name)
            continue

        installed.append(name)

    return installed
