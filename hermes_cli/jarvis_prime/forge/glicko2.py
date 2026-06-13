"""Pure-stdlib Glicko-2 rating system (Glickman, glicko.net/glicko/glicko2.pdf).

Used for Forge matchmaking and leaderboards: a rating (skill estimate), a
rating deviation RD (uncertainty), and a volatility (how erratic the skill
is). The implementation follows the paper's steps 1–8 exactly, including the
Illinois-method iteration for the new volatility; the paper's worked example
is pinned as a test vector.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

DEFAULT_RATING = 1500.0
DEFAULT_RD = 350.0
DEFAULT_VOL = 0.06
TAU = 0.5  # system constant; smaller = volatility changes more slowly
GLICKO2_SCALE = 173.7178
CONVERGENCE_TOL = 1e-6

WIN, DRAW, LOSS = 1.0, 0.5, 0.0


@dataclass(frozen=True)
class GlickoRating:
    rating: float = DEFAULT_RATING
    rd: float = DEFAULT_RD
    volatility: float = DEFAULT_VOL

    def to_dict(self) -> dict[str, Any]:
        return {
            "rating": round(self.rating, 4),
            "rd": round(self.rd, 4),
            "volatility": round(self.volatility, 6),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "GlickoRating":
        return cls(
            rating=float(data.get("rating", DEFAULT_RATING)),
            rd=float(data.get("rd", DEFAULT_RD)),
            volatility=float(data.get("volatility", DEFAULT_VOL)),
        )


def _to_glicko2(r: GlickoRating) -> tuple[float, float]:
    return (r.rating - DEFAULT_RATING) / GLICKO2_SCALE, r.rd / GLICKO2_SCALE


def _g(phi: float) -> float:
    return 1.0 / math.sqrt(1.0 + 3.0 * phi * phi / (math.pi * math.pi))


def _e(mu: float, mu_j: float, phi_j: float) -> float:
    return 1.0 / (1.0 + math.exp(-_g(phi_j) * (mu - mu_j)))


def expected_score(a: GlickoRating, b: GlickoRating) -> float:
    """Expected score of ``a`` against ``b`` (uses b's deviation, per Glicko)."""

    mu_a, _ = _to_glicko2(a)
    mu_b, phi_b = _to_glicko2(b)
    return _e(mu_a, mu_b, phi_b)


def _new_volatility(phi: float, v: float, delta: float, sigma: float, tau: float) -> float:
    """Step 5 of the paper: Illinois-method root of f(x)."""

    a = math.log(sigma * sigma)

    def f(x: float) -> float:
        ex = math.exp(x)
        num = ex * (delta * delta - phi * phi - v - ex)
        den = 2.0 * (phi * phi + v + ex) ** 2
        return num / den - (x - a) / (tau * tau)

    big_a = a
    if delta * delta > phi * phi + v:
        big_b = math.log(delta * delta - phi * phi - v)
    else:
        k = 1
        while f(a - k * tau) < 0:
            k += 1
        big_b = a - k * tau

    f_a, f_b = f(big_a), f(big_b)
    while abs(big_b - big_a) > CONVERGENCE_TOL:
        big_c = big_a + (big_a - big_b) * f_a / (f_b - f_a)
        f_c = f(big_c)
        if f_c * f_b <= 0:
            big_a, f_a = big_b, f_b
        else:
            f_a = f_a / 2.0
        big_b, f_b = big_c, f_c
    return math.exp(big_a / 2.0)


def update_rating(
    r: GlickoRating,
    results: Sequence[tuple[GlickoRating, float]],
    *,
    tau: float = TAU,
) -> GlickoRating:
    """One Glicko-2 rating period for player ``r``.

    ``results`` is ``[(opponent_rating, score), ...]`` with score 1/0.5/0.
    With no games, only the deviation inflates (step 6 special case).
    """

    mu, phi = _to_glicko2(r)
    sigma = r.volatility

    if not results:
        phi_star = math.sqrt(phi * phi + sigma * sigma)
        return GlickoRating(
            rating=r.rating,
            rd=phi_star * GLICKO2_SCALE,
            volatility=sigma,
        )

    v_inv = 0.0
    delta_sum = 0.0
    for opponent, score in results:
        mu_j, phi_j = _to_glicko2(opponent)
        g_j = _g(phi_j)
        e_j = _e(mu, mu_j, phi_j)
        v_inv += g_j * g_j * e_j * (1.0 - e_j)
        delta_sum += g_j * (score - e_j)
    v = 1.0 / v_inv
    delta = v * delta_sum

    sigma_prime = _new_volatility(phi, v, delta, sigma, tau)
    phi_star = math.sqrt(phi * phi + sigma_prime * sigma_prime)
    phi_prime = 1.0 / math.sqrt(1.0 / (phi_star * phi_star) + 1.0 / v)
    mu_prime = mu + phi_prime * phi_prime * delta_sum

    return GlickoRating(
        rating=mu_prime * GLICKO2_SCALE + DEFAULT_RATING,
        rd=phi_prime * GLICKO2_SCALE,
        volatility=sigma_prime,
    )


__all__ = [
    "DEFAULT_RATING",
    "DEFAULT_RD",
    "DEFAULT_VOL",
    "TAU",
    "GLICKO2_SCALE",
    "WIN",
    "DRAW",
    "LOSS",
    "GlickoRating",
    "expected_score",
    "update_rating",
]
