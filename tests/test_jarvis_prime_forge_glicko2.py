"""Tests for the pure-stdlib Glicko-2 implementation."""

import math

from hermes_cli.jarvis_prime.forge.glicko2 import (
    DRAW,
    LOSS,
    WIN,
    GlickoRating,
    expected_score,
    update_rating,
)


def test_glickman_paper_example():
    # The worked example from glicko.net/glicko/glicko2.pdf: r=1500 RD=200
    # sigma=0.06 tau=0.5; W vs 1400/30, L vs 1550/100, L vs 1700/300.
    player = GlickoRating(rating=1500.0, rd=200.0, volatility=0.06)
    results = [
        (GlickoRating(1400.0, 30.0, 0.06), WIN),
        (GlickoRating(1550.0, 100.0, 0.06), LOSS),
        (GlickoRating(1700.0, 300.0, 0.06), LOSS),
    ]
    updated = update_rating(player, results, tau=0.5)
    assert math.isclose(updated.rating, 1464.06, abs_tol=0.05)
    assert math.isclose(updated.rd, 151.52, abs_tol=0.05)
    assert math.isclose(updated.volatility, 0.05999, abs_tol=0.0005)


def test_expected_scores_complement():
    a = GlickoRating(1600.0, 80.0)
    b = GlickoRating(1450.0, 120.0)
    assert expected_score(a, b) > 0.5 > expected_score(b, a)
    # Equal-rating, equal-RD players are even.
    c = GlickoRating(1500.0, 100.0)
    d = GlickoRating(1500.0, 100.0)
    assert math.isclose(expected_score(c, d), 0.5, abs_tol=1e-9)
    assert math.isclose(expected_score(c, d) + expected_score(d, c), 1.0, abs_tol=1e-9)


def test_no_games_inflates_rd_only():
    player = GlickoRating(rating=1525.0, rd=60.0, volatility=0.06)
    updated = update_rating(player, [])
    assert updated.rating == player.rating
    assert updated.rd > player.rd
    assert updated.volatility == player.volatility


def test_winner_rises_loser_falls_and_draw_is_gentle():
    a = GlickoRating()
    b = GlickoRating()
    a_after = update_rating(a, [(b, WIN)])
    b_after = update_rating(b, [(a, LOSS)])
    assert a_after.rating > a.rating
    assert b_after.rating < b.rating
    drawn = update_rating(a, [(b, DRAW)])
    assert abs(drawn.rating - a.rating) < abs(a_after.rating - a.rating)


def test_rd_shrinks_with_games_and_round_trip():
    rating = GlickoRating()
    for _ in range(5):
        rating = update_rating(rating, [(GlickoRating(), WIN)])
    assert rating.rd < GlickoRating().rd
    restored = GlickoRating.from_dict(rating.to_dict())
    assert math.isclose(restored.rating, rating.rating, abs_tol=1e-3)
