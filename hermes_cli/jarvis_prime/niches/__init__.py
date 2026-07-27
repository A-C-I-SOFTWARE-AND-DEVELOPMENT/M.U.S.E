"""Niche AXIOM specialists — thin YAML specs + forge + pool indexing.

Hundreds of niche definitions live on disk (cheap). Only top-K activate
concurrently. Scout prefetch feeds them so they spend tokens on work.
"""

from __future__ import annotations

from hermes_cli.jarvis_prime.niches.schema import NicheSpec, validate_niche_dict
from hermes_cli.jarvis_prime.niches.loader import (
    SPECS_DIR,
    load_all_niches,
    load_niche,
    niches_dir,
)
from hermes_cli.jarvis_prime.niches.forge import forge_niche, ForgeResult

__all__ = [
    "NicheSpec",
    "validate_niche_dict",
    "SPECS_DIR",
    "niches_dir",
    "load_all_niches",
    "load_niche",
    "forge_niche",
    "ForgeResult",
]
