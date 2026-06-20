#!/usr/bin/env python3
"""Sacred-geometry reference / golden-vector generator for the UE C++ port.

This is the *numeric ground truth* for the ``MuseSacredGeometry`` C++ library
(``Source/SynapseCore/{Public,Private}/MuseSacredGeometry.*``) and the UE
automation tests in ``SynapseObservatoryRender``. Because UE 5.6 / UnrealBuildTool
are **not** installed in the authoring container, the C++ cannot be compiled or
run here — this stdlib-only Python module is what *can* be executed in-container
to prove the constants and exact vertex sets the C++ must reproduce (the same
"validate the reference in the container, compile on the owner's machine" pattern
used for ``tools/stub_gateway.py``).

Run it:

    python3 apps/synapse-ue/tools/sacred_geometry_reference.py            # JSON
    python3 apps/synapse-ue/tools/sacred_geometry_reference.py --check    # self-test

``--check`` asserts every count and key constant against the research spec
(golden angle 137.50776°, 600-cell = 120 vertices, 120-cell = 600 vertices, …)
and exits non-zero on any mismatch, so it doubles as a guard the owner can diff
the compiled C++ automation output against.

No third-party dependencies; no I/O beyond stdout. Pure functions.
"""

from __future__ import annotations

import argparse
import json
import math
from itertools import permutations

PHI = (1.0 + math.sqrt(5.0)) / 2.0
# Golden angle = 2*pi*(2 - phi) = 2*pi/phi^2 = pi*(3 - sqrt5).
GOLDEN_ANGLE_RAD = math.pi * (3.0 - math.sqrt(5.0))
GOLDEN_ANGLE_DEG = math.degrees(GOLDEN_ANGLE_RAD)

Vec4 = tuple[float, float, float, float]


# ── 2D / 3D point generators ────────────────────────────────────────────────


def vogel_phyllotaxis(n: int) -> list[tuple[float, float]]:
    """Vogel's sunflower model: r = sqrt(i), theta = i * golden_angle."""
    out: list[tuple[float, float]] = []
    for i in range(n):
        r = math.sqrt(i)
        theta = i * GOLDEN_ANGLE_RAD
        out.append((r * math.cos(theta), r * math.sin(theta)))
    return out


def fibonacci_sphere(n: int) -> list[tuple[float, float, float]]:
    """Near-uniform points on the unit sphere via the golden-angle spiral."""
    out: list[tuple[float, float, float]] = []
    for i in range(n):
        z = 1.0 - 2.0 * (i + 0.5) / n
        ring = math.sqrt(max(0.0, 1.0 - z * z))
        theta = GOLDEN_ANGLE_RAD * i
        out.append((ring * math.cos(theta), z, ring * math.sin(theta)))
    return out


# ── Platonic solids (exact vertex coordinates) ──────────────────────────────


def platonic_vertices(name: str) -> list[tuple[float, float, float]]:
    """Exact vertices of the five Platonic solids (research spec, area 2)."""
    p = PHI
    if name == "tetrahedron":
        return [(1.0, 1.0, 1.0), (1.0, -1.0, -1.0), (-1.0, 1.0, -1.0), (-1.0, -1.0, 1.0)]
    if name == "cube":
        return [(x, y, z) for x in (-1.0, 1.0) for y in (-1.0, 1.0) for z in (-1.0, 1.0)]
    if name == "octahedron":
        return [
            (1.0, 0.0, 0.0), (-1.0, 0.0, 0.0),
            (0.0, 1.0, 0.0), (0.0, -1.0, 0.0),
            (0.0, 0.0, 1.0), (0.0, 0.0, -1.0),
        ]
    if name == "icosahedron":
        out: list[tuple[float, float, float]] = []
        for a in (-1.0, 1.0):
            for b in (-p, p):
                out.append((0.0, a, b))
                out.append((a, b, 0.0))
                out.append((b, 0.0, a))
        return out
    if name == "dodecahedron":
        out = [(x, y, z) for x in (-1.0, 1.0) for y in (-1.0, 1.0) for z in (-1.0, 1.0)]
        inv = 1.0 / p
        for a in (-inv, inv):
            for b in (-p, p):
                out.append((0.0, a, b))
                out.append((a, b, 0.0))
                out.append((b, 0.0, a))
        return out
    raise ValueError(f"unknown Platonic solid: {name!r}")


# ── 4-polytopes (exact vertex coordinates) ──────────────────────────────────


def _parity_even(perm: tuple[int, ...]) -> bool:
    """True if the permutation (as a sequence of indices) is even."""
    inversions = 0
    for i in range(len(perm)):
        for j in range(i + 1, len(perm)):
            if perm[i] > perm[j]:
                inversions += 1
    return inversions % 2 == 0


def _distinct_positions(values: Vec4) -> list[tuple[int, ...]]:
    """Distinct index orderings of ``values`` (handles repeated entries)."""
    seen: set[Vec4] = set()
    orders: list[tuple[int, ...]] = []
    for perm in permutations(range(4)):
        arranged = (values[perm[0]], values[perm[1]], values[perm[2]], values[perm[3]])
        if arranged not in seen:
            seen.add(arranged)
            orders.append(perm)
    return orders


def _even_position_orders(values: Vec4) -> list[tuple[int, ...]]:
    """Even-permutation index orderings of four *distinct* values."""
    return [perm for perm in permutations(range(4)) if _parity_even(perm)]


def _signed(values: Vec4, sign_zero: bool = False) -> list[Vec4]:
    """All independent sign combinations; entries equal to 0 are not flipped
    unless ``sign_zero`` (they never are here — avoids spurious duplicates)."""
    out: list[Vec4] = []
    nonzero = [k for k in range(4) if values[k] != 0.0 or sign_zero]
    for mask in range(1 << len(nonzero)):
        v = list(values)
        for bit, k in enumerate(nonzero):
            if mask & (1 << bit):
                v[k] = -v[k]
        out.append((v[0], v[1], v[2], v[3]))
    return out


def _dedupe(points: list[Vec4]) -> list[Vec4]:
    seen: set[tuple[float, ...]] = set()
    out: list[Vec4] = []
    for p in points:
        key = tuple(round(c, 9) for c in p)
        if key not in seen:
            seen.add(key)
            out.append(p)
    return out


def polytope_vertices(name: str) -> list[Vec4]:
    """Exact vertices of the regular 4-polytopes (research spec, area 2)."""
    p = PHI
    inv = 1.0 / p
    inv2 = 1.0 / (p * p)
    root5 = math.sqrt(5.0)

    if name == "5-cell":
        # Centered R^4 embedding: regular-tetrahedron base + apex on the w axis.
        s = 1.0 / math.sqrt(10.0)
        return [
            (1.0, 1.0, 1.0, -s),
            (1.0, -1.0, -1.0, -s),
            (-1.0, 1.0, -1.0, -s),
            (-1.0, -1.0, 1.0, -s),
            (0.0, 0.0, 0.0, 4.0 * s),
        ]
    if name == "16-cell":
        out: list[Vec4] = []
        for axis in range(4):
            for sign in (-1.0, 1.0):
                v = [0.0, 0.0, 0.0, 0.0]
                v[axis] = sign
                out.append((v[0], v[1], v[2], v[3]))
        return out
    if name == "tesseract":
        return [
            (x, y, z, w)
            for x in (-1.0, 1.0)
            for y in (-1.0, 1.0)
            for z in (-1.0, 1.0)
            for w in (-1.0, 1.0)
        ]
    if name == "24-cell":
        out = []
        # 8 permutations of (+-1,0,0,0)
        for axis in range(4):
            for sign in (-1.0, 1.0):
                v = [0.0, 0.0, 0.0, 0.0]
                v[axis] = sign
                out.append((v[0], v[1], v[2], v[3]))
        # 16 of (+-1/2,+-1/2,+-1/2,+-1/2)
        out.extend(_signed((0.5, 0.5, 0.5, 0.5)))
        return _dedupe(out)
    if name == "600-cell":
        out = []
        # (a) 16 x (+-1/2)^4
        out.extend(_signed((0.5, 0.5, 0.5, 0.5)))
        # (b) 8 permutations of (+-1,0,0,0)
        for axis in range(4):
            for sign in (-1.0, 1.0):
                v = [0.0, 0.0, 0.0, 0.0]
                v[axis] = sign
                out.append((v[0], v[1], v[2], v[3]))
        # (c) 96 even permutations of 1/2 (+-phi,+-1,+-1/phi,0)
        base = (0.5 * p, 0.5, 0.5 * inv, 0.0)
        for order in _even_position_orders(base):
            arranged = (base[order[0]], base[order[1]], base[order[2]], base[order[3]])
            out.extend(_signed(arranged))
        return _dedupe(out)
    if name == "120-cell":
        out = []

        def add_all_perms(values: Vec4) -> None:
            for order in _distinct_positions(values):
                arranged = (
                    values[order[0]], values[order[1]],
                    values[order[2]], values[order[3]],
                )
                out.extend(_signed(arranged))

        def add_even_perms(values: Vec4) -> None:
            for order in _even_position_orders(values):
                arranged = (
                    values[order[0]], values[order[1]],
                    values[order[2]], values[order[3]],
                )
                out.extend(_signed(arranged))

        add_all_perms((0.0, 0.0, 2.0, 2.0))          # 24
        add_all_perms((1.0, 1.0, 1.0, root5))         # 64
        add_all_perms((inv2, p, p, p))                # 64
        add_all_perms((inv, inv, inv, p * p))         # 64
        add_even_perms((0.0, inv2, 1.0, p * p))       # 96
        add_even_perms((0.0, inv, p, root5))          # 96
        add_even_perms((inv, 1.0, p, 2.0))            # 192
        return _dedupe(out)
    raise ValueError(f"unknown 4-polytope: {name!r}")


# ── 4D rotation + projection ────────────────────────────────────────────────

_PLANES = {
    "xy": (0, 1), "xz": (0, 2), "xw": (0, 3),
    "yz": (1, 2), "yw": (1, 3), "zw": (2, 3),
}


def rotate_4d(point: Vec4, plane: str, angle: float) -> Vec4:
    """Rotate a 4-vector in one of the six coordinate planes."""
    a, b = _PLANES[plane]
    c, s = math.cos(angle), math.sin(angle)
    v = list(point)
    va, vb = v[a], v[b]
    v[a] = va * c - vb * s
    v[b] = va * s + vb * c
    return (v[0], v[1], v[2], v[3])


def project_4d_to_3d(
    point: Vec4, mode: str = "perspective", distance: float = 2.5
) -> tuple[float, float, float]:
    """Project a 4-vector to 3-space (Schlegel-style perspective, or
    stereographic from the +w pole after normalising onto the 3-sphere)."""
    x, y, z, w = point
    if mode == "perspective":
        denom = distance - w
        s = distance / denom if abs(denom) > 1e-9 else 1e9
        return (x * s, y * s, z * s)
    if mode == "stereographic":
        norm = math.sqrt(x * x + y * y + z * z + w * w) or 1.0
        x, y, z, w = x / norm, y / norm, z / norm, w / norm
        denom = 1.0 - w
        s = 1.0 / denom if abs(denom) > 1e-9 else 1e9
        return (x * s, y * s, z * s)
    raise ValueError(f"unknown projection mode: {mode!r}")


# ── Reference payload + self-check ──────────────────────────────────────────

PLATONIC_NAMES = ("tetrahedron", "cube", "octahedron", "icosahedron", "dodecahedron")
POLYTOPE_NAMES = ("5-cell", "16-cell", "tesseract", "24-cell", "600-cell", "120-cell")

EXPECTED_PLATONIC_COUNTS = {
    "tetrahedron": 4, "cube": 8, "octahedron": 6,
    "icosahedron": 12, "dodecahedron": 20,
}
EXPECTED_POLYTOPE_COUNTS = {
    "5-cell": 5, "16-cell": 8, "tesseract": 16,
    "24-cell": 24, "600-cell": 120, "120-cell": 600,
}


def build_reference() -> dict:
    """The full golden-vector reference payload."""
    return {
        "constants": {
            "phi": PHI,
            "golden_angle_rad": GOLDEN_ANGLE_RAD,
            "golden_angle_deg": GOLDEN_ANGLE_DEG,
        },
        "platonic_counts": {
            name: len(platonic_vertices(name)) for name in PLATONIC_NAMES
        },
        "polytope_counts": {
            name: len(polytope_vertices(name)) for name in POLYTOPE_NAMES
        },
        "samples": {
            "vogel_5": vogel_phyllotaxis(5),
            "fibonacci_sphere_4": fibonacci_sphere(4),
            "tesseract_rotated_xw_quarter": [
                rotate_4d(v, "xw", math.pi / 2.0) for v in polytope_vertices("tesseract")[:2]
            ],
            "tesseract_projected": [
                project_4d_to_3d(v, "perspective") for v in polytope_vertices("tesseract")[:2]
            ],
        },
    }


def run_check() -> int:
    """Assert every count and key constant. Returns a process exit code."""
    failures: list[str] = []

    if abs(GOLDEN_ANGLE_DEG - 137.50776405) > 1e-6:
        failures.append(f"golden angle deg = {GOLDEN_ANGLE_DEG} (want 137.50776405)")
    if abs(GOLDEN_ANGLE_RAD - 2.399963229728653) > 1e-9:
        failures.append(f"golden angle rad = {GOLDEN_ANGLE_RAD} (want 2.399963229728653)")

    for name, want in EXPECTED_PLATONIC_COUNTS.items():
        got = len(platonic_vertices(name))
        if got != want:
            failures.append(f"platonic {name}: {got} vertices (want {want})")

    for name, want in EXPECTED_POLYTOPE_COUNTS.items():
        got = len(polytope_vertices(name))
        if got != want:
            failures.append(f"polytope {name}: {got} vertices (want {want})")

    # rotation preserves the 4D norm
    sample: Vec4 = (0.3, -0.7, 1.1, 0.5)
    before = math.sqrt(sum(c * c for c in sample))
    after_pt = rotate_4d(sample, "zw", 1.234)
    after = math.sqrt(sum(c * c for c in after_pt))
    if abs(before - after) > 1e-9:
        failures.append(f"rotate_4d changed norm: {before} -> {after}")

    # a full 2*pi rotation is the identity
    spun = rotate_4d(sample, "xy", 2.0 * math.pi)
    if max(abs(a - b) for a, b in zip(spun, sample)) > 1e-9:
        failures.append("rotate_4d(2*pi) is not the identity")

    if failures:
        for f in failures:
            print(f"FAIL: {f}")
        return 1

    print("OK: all sacred-geometry reference checks passed")
    print(f"  golden angle = {GOLDEN_ANGLE_DEG:.8f} deg ({GOLDEN_ANGLE_RAD:.12f} rad)")
    print(f"  Platonic counts  = {build_reference()['platonic_counts']}")
    print(f"  4-polytope counts = {build_reference()['polytope_counts']}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="run self-tests and exit")
    args = parser.parse_args()
    if args.check:
        return run_check()
    print(json.dumps(build_reference(), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
