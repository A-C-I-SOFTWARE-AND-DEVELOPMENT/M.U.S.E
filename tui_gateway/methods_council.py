"""Council-roster JSON-RPC handlers — the agent list, over a transport.

MUSE has a structured agent registry
(``skills/aos-enterprise-council/operating-registry/registry.json``) and a
normalizer for it (``aos_council.dispatcher.roster``), but until now
``roster()`` was reachable only from the CLI. No transport exposed the agents,
so any client wanting to *show* them — the TUI's rooms, a desktop app's agent
sidebar — had nothing to call.

Note the near-miss: ``agents.list`` in ``methods_tools.py`` sounds like this
but is unrelated — it enumerates running OS processes from the process
registry, not council members.

- ``council.roster``  — the full roster, by section, with no request routing.
- ``council.members`` — the same members flattened into one list, which is what
  a picker or sidebar actually wants.

Everything a handler needs is imported INSIDE its body — including this
module's own helper. ``install()`` rebuilds each handler against server.py's
globals (see method_ctx.py), so module-level names here are invisible at call
time: a module-level constant or helper reference raises ``NameError`` on the
first request, not at import. Hence the literal error codes below rather than
named constants.

Codes continue the split-module convention (rooms took 5064/5065):
5066 = council internal error, 5067 = council client error.
"""

from .method_ctx import HandlerRegistry

_registry = HandlerRegistry()
method = _registry.method
_profile_scoped = _registry.profile_scoped


def _roster_sections() -> dict:
    """``{section: [member dict]}`` from the operating registry."""
    from hermes_cli.jarvis_prime.aos_council import dispatcher

    return {
        section: [member.to_dict() for member in members]
        for section, members in dispatcher.roster().items()
    }


@method("council.roster")
def _(rid, params: dict) -> dict:
    """The full council roster, grouped by section.

    Sections are the registry's own: ``active_council`` and
    ``domain_specialists``. Grouping is preserved because the two are not
    interchangeable — the council seats a fixed table, the specialists are
    called in on their domain.
    """
    try:
        from tui_gateway.methods_council import _roster_sections

        sections = _roster_sections()
        return _ok(
            rid,
            {
                "sections": sections,
                "counts": {name: len(members) for name, members in sections.items()},
            },
        )
    except Exception as e:
        return _err(rid, 5066, str(e))


@method("council.members")
def _(rid, params: dict) -> dict:
    """Every council member as one flat list.

    Optional ``section`` filters to a single registry section. An unknown
    section is the client's mistake and comes back as a client error listing
    the sections that do exist, rather than an empty list that looks like
    "there are no agents".
    """
    try:
        from tui_gateway.methods_council import _roster_sections

        sections = _roster_sections()

        wanted = str(params.get("section") or "").strip()
        if wanted:
            if wanted not in sections:
                return _err(
                    rid,
                    5067,
                    f"unknown section {wanted!r}; have: {', '.join(sorted(sections))}",
                )
            selected = {wanted: sections[wanted]}
        else:
            selected = sections

        members = [
            {**member, "section": name}
            for name, group in selected.items()
            for member in group
        ]
        return _ok(rid, {"members": members, "count": len(members)})
    except Exception as e:
        return _err(rid, 5066, str(e))


def register(server) -> None:
    """Bind this module's handlers onto ``server``'s globals and registry."""
    _registry.install(server)
