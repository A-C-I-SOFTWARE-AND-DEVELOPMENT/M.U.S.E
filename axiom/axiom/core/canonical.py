"""Canonical form and content-addressed identity (defends I1).

A Unit's identity is the blake3 hash of its canonical JSON form.
Names and docs are metadata — they are excluded from the hash, so
renaming a unit never changes what it *is*. Canonical JSON uses
sorted keys and compact separators, so dict insertion order is
irrelevant to identity.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

import blake3

# The closed effect vocabulary. Anything outside this set must use the
# explicit "regulated:" namespace so it is visibly exceptional.
EFFECT_VOCAB: frozenset[str] = frozenset(
    {"db.read", "db.write", "fs.read", "fs.write", "net"}
)
REGULATED_PREFIX = "regulated:"

# Canonical JSON: sorted keys, no whitespace. These two separators are
# part of the identity function and must never change.
_SEPARATORS = (",", ":")


def canonical_json(obj: Any) -> str:
    """Serialize *obj* to canonical JSON (sorted keys, compact)."""
    return json.dumps(obj, sort_keys=True, separators=_SEPARATORS, ensure_ascii=True)


def content_hash(obj: Any) -> str:
    """blake3 hex digest of the canonical JSON form of *obj*."""
    return blake3.blake3(canonical_json(obj).encode("utf-8")).hexdigest()


def effect_in_vocab(effect: str) -> bool:
    """True iff *effect* is in the closed vocabulary or regulated namespace."""
    return effect in EFFECT_VOCAB or effect.startswith(REGULATED_PREFIX)


@dataclass(frozen=True)
class Unit:
    """The verified unit form (ACIM).

    Semantic fields (hashed): params, intent, contracts, effects, refs, body.
    Metadata fields (NOT hashed): name, doc.
    """

    name: str
    doc: str
    params: dict[str, str] = field(default_factory=dict)  # name -> "float" | "bool"
    intent: str = ""  # EARS clause
    contracts: tuple[str, ...] = ()  # postcondition expressions
    effects: tuple[str, ...] = ()  # declared effects
    refs: dict[str, str] = field(default_factory=dict)  # alias -> unit_hash
    body: tuple[dict, ...] = ()  # op-language program

    def semantic_form(self) -> dict:
        """The hashed portion of the unit: everything except metadata."""
        return {
            "params": dict(self.params),
            "intent": self.intent,
            "contracts": list(self.contracts),
            "effects": list(self.effects),
            "refs": dict(self.refs),
            "body": [dict(op) for op in self.body],
        }

    def canonical(self) -> str:
        return canonical_json(self.semantic_form())

    def unit_hash(self) -> str:
        return blake3.blake3(self.canonical().encode("utf-8")).hexdigest()

    def full_form(self) -> dict:
        """Semantic form plus metadata, for storage/transport."""
        form = self.semantic_form()
        form["name"] = self.name
        form["doc"] = self.doc
        return form

    @staticmethod
    def from_form(form: dict) -> "Unit":
        return Unit(
            name=form.get("name", ""),
            doc=form.get("doc", ""),
            params=dict(form.get("params", {})),
            intent=form.get("intent", ""),
            contracts=tuple(form.get("contracts", ())),
            effects=tuple(form.get("effects", ())),
            refs=dict(form.get("refs", {})),
            body=tuple(dict(op) for op in form.get("body", ())),
        )
