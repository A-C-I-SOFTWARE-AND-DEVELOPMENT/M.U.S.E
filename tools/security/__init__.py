"""Security utilities for Hermes Agent.

Deliberately dependency-free and side-effect-free on import, because the
consumers include vendored training scripts and developer tooling that run
outside the main agent process.

Modules
-------
``safe_pickle``
    Hash-pinned deserialisation. See its module docstring for the contract
    (short version: it only loads artifacts this repository already vouched
    for; it does *not* make untrusted pickle safe, because nothing can).

``secret_scan``
    A credential scanner that records **locations only** and never a matched
    value. Its output is a triage queue, not a finding of leaked credentials.
"""

__all__ = ["safe_pickle", "secret_scan"]
