"""Glicko-2 ratings, implemented exactly from Glickman's paper
("Example of the Glicko-2 system", glicko.net/glicko/glicko2.pdf).

System constants: tau = 0.5 (volatility constraint), convergence
epsilon = 1e-6, scale factor 173.7178 between Glicko and Glicko-2
scales. Verified against the published worked example:
r=1500 RD=350->200 vol=0.06 vs three opponents -> r'~=1464.05,
RD'~=151.52, vol'~=0.05999.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

TAU = 0.5
EPSILON = 1e-06
GLICKO2_SCALE = 173.7178
DEFAULT_RATING = 1500.0
DEFAULT_RD = 350.0
DEFAULT_VOL = 0.06

WIN = 1.0
DRAW = 0.5
LOSS = 0.0


@dataclass
class Rating:
    rating: float = DEFAULT_RATING
    rd: float = DEFAULT_RD
    vol: float = DEFAULT_VOL


def _g(phi: float) -> float:
    return 1.0 / math.sqrt(1.0 + 3.0 * phi * phi / (math.pi * math.pi))


def _expected(mu: float, mu_j: float, phi_j: float) -> float:
    return 1.0 / (1.0 + math.exp(-_g(phi_j) * (mu - mu_j)))


def update(
    player: Rating,
    outcomes: list[tuple[float, float, float]],
) -> Rating:
    """One rating-period update.

    *outcomes* is a list of (opponent_rating, opponent_rd, score) with
    score in {1.0 win, 0.5 draw, 0.0 loss}. An empty list applies only
    the RD-inflation step (step 6 of the paper).
    """
    # Step 2: convert to the Glicko-2 scale.
    mu = (player.rating - DEFAULT_RATING) / GLICKO2_SCALE
    phi = player.rd / GLICKO2_SCALE
    sigma = player.vol

    if not outcomes:
        # No games: RD inflates with volatility (paper, end of step 6).
        phi_star = math.sqrt(phi * phi + sigma * sigma)
        return Rating(player.rating, phi_star * GLICKO2_SCALE, sigma)

    # Step 3: estimated variance v.
    v_inv = 0.0
    for r_j, rd_j, _s in outcomes:
        mu_j = (r_j - DEFAULT_RATING) / GLICKO2_SCALE
        phi_j = rd_j / GLICKO2_SCALE
        e = _expected(mu, mu_j, phi_j)
        v_inv += _g(phi_j) ** 2 * e * (1.0 - e)
    v = 1.0 / v_inv

    # Step 4: estimated improvement delta.
    delta_sum = 0.0
    for r_j, rd_j, s in outcomes:
        mu_j = (r_j - DEFAULT_RATING) / GLICKO2_SCALE
        phi_j = rd_j / GLICKO2_SCALE
        delta_sum += _g(phi_j) * (s - _expected(mu, mu_j, phi_j))
    delta = v * delta_sum

    # Step 5: new volatility via the Illinois variant of regula falsi.
    a = math.log(sigma * sigma)

    def f(x: float) -> float:
        ex = math.exp(x)
        num = ex * (delta * delta - phi * phi - v - ex)
        den = 2.0 * (phi * phi + v + ex) ** 2
        return num / den - (x - a) / (TAU * TAU)

    big_a = a
    if delta * delta > phi * phi + v:
        big_b = math.log(delta * delta - phi * phi - v)
    else:
        k = 1
        while f(a - k * TAU) < 0:
            k += 1
        big_b = a - k * TAU

    fa, fb = f(big_a), f(big_b)
    while abs(big_b - big_a) > EPSILON:
        big_c = big_a + (big_a - big_b) * fa / (fb - fa)
        fc = f(big_c)
        if fc * fb <= 0:
            big_a, fa = big_b, fb
        else:
            fa = fa / 2.0
        big_b, fb = big_c, fc
    sigma_new = math.exp(big_a / 2.0)

    # Step 6: pre-rating-period RD.
    phi_star = math.sqrt(phi * phi + sigma_new * sigma_new)

    # Step 7: new phi and mu.
    phi_new = 1.0 / math.sqrt(1.0 / (phi_star * phi_star) + 1.0 / v)
    mu_new = mu + phi_new * phi_new * delta_sum

    # Step 8: back to the Glicko scale.
    return Rating(
        rating=mu_new * GLICKO2_SCALE + DEFAULT_RATING,
        rd=phi_new * GLICKO2_SCALE,
        vol=sigma_new,
    )
