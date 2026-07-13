from __future__ import annotations

import math

import pytest

from plugins.muse_universe.catalog import STATIONS
from plugins.muse_universe.generation import generate_system, regenerate_region


def _distance(left: dict[str, object], right: dict[str, object]) -> float:
    left_position = left["transform"]["position_m"]  # type: ignore[index]
    right_position = right["transform"]["position_m"]  # type: ignore[index]
    return math.sqrt(
        sum(
            (float(a) - float(b)) ** 2
            for a, b in zip(left_position, right_position)
        )
    )


def test_generation_is_reproducible_landmarked_and_source_order_independent() -> None:
    a = generate_system("seed-42", ["repo:a", "dataset:b", "repo:a"])
    b = generate_system("seed-42", ["dataset:b", "repo:a"])

    assert a.model_dump() == b.model_dump()
    assert a.semantic_sources == ("dataset:b", "repo:a")
    assert a.star_system["seed"] == "seed-42"
    assert a.star_system["recipe_version"] == "1"
    assert a.star_system["region_recipes"] == {
        region_id: region["recipe"] for region_id, region in a.regions.items()
    }
    station_types = {station["type"] for station in a.stations}
    assert "atlas_crown" in station_types
    assert {station["id"] for station in STATIONS}.issubset(station_types)


def test_unknown_recipe_version_is_rejected_until_implemented() -> None:
    with pytest.raises(ValueError, match="unsupported recipe_version"):
        generate_system("seed-42", ["repo:a"], recipe_version="2")


def test_recipe_version_one_golden_replay_contract() -> None:
    generated = generate_system("golden-v1", ["repo:a", "dataset:b"])
    replay = generated.model_dump(mode="json")

    assert {
        "recipe_version": replay["recipe_version"],
        "recipe": replay["star_system"]["recipe"],
        "region_contracts": {
            region_id: {
                "name": region["name"],
                "frozen": region["frozen"],
                "recipe": region["recipe"],
            }
            for region_id, region in replay["regions"].items()
        },
        "station_ids": [station["id"] for station in replay["stations"]],
        "atlas_transform": replay["stations"][0]["transform"],
        "site_count": sum(
            len(region["sites"]) for region in replay["regions"].values()
        ),
        "route_count": len(replay["routes"]),
    } == {
        "recipe_version": "1",
        "recipe": {
            "version": "1",
            "regions": {
                "region-1": {
                    "anomaly_rate": 0.05,
                    "density": 0.3,
                    "spread": 0.4,
                    "verticality": 0.15,
                },
                "region-2": {
                    "anomaly_rate": 0.12,
                    "density": 0.55,
                    "spread": 0.65,
                    "verticality": 0.3,
                },
                "region-3": {
                    "anomaly_rate": 0.2,
                    "density": 0.42,
                    "spread": 0.85,
                    "verticality": 0.5,
                },
            },
        },
        "region_contracts": {
            "region-1": {
                "name": "Atlas Crown Inner Orbit",
                "frozen": True,
                "recipe": {
                    "anomaly_rate": 0.05,
                    "density": 0.3,
                    "spread": 0.4,
                    "verticality": 0.15,
                },
            },
            "region-2": {
                "name": "Production and Research Reach",
                "frozen": False,
                "recipe": {
                    "anomaly_rate": 0.12,
                    "density": 0.55,
                    "spread": 0.65,
                    "verticality": 0.3,
                },
            },
            "region-3": {
                "name": "Frontier and Deployment Reach",
                "frozen": False,
                "recipe": {
                    "anomaly_rate": 0.2,
                    "density": 0.42,
                    "spread": 0.85,
                    "verticality": 0.5,
                },
            },
        },
        "station_ids": [
            "stn_atlas_crown",
            "stn_neural_shipyard",
            "stn_deep_observatory",
            "stn_fabrication_foundry",
            "stn_cinema_array",
            "stn_game_foundry",
            "stn_memory_archive",
            "stn_quarantine_moon",
            "stn_relay_embassy",
            "stn_academy_station",
            "stn_blueprint_exchange",
            "stn_release_dock",
        ],
        "atlas_transform": {
            "units": "meters",
            "position_m": [0.0, 0.0, 0.0],
            "rotation_degrees": [0.0, 0.0, 0.0],
            "scale": [1.0, 1.0, 1.0],
        },
        "site_count": 13,
        "route_count": 13,
    }


def test_routes_are_typed_and_reference_authored_landmarks() -> None:
    generated = generate_system("seed-42", ["repo:a", "dataset:b"])
    station_ids = {station["id"] for station in generated.stations}

    assert generated.routes
    assert all(
        route["edge_type"] in {"dependency", "communication", "deployment"}
        for route in generated.routes
    )
    assert all(route["source"] in station_ids for route in generated.routes)
    assert all(route["target"] in station_ids for route in generated.routes)
    assert all(float(route["distance_m"]) > 0 for route in generated.routes)


def test_metric_transforms_respect_navigation_clearance() -> None:
    generated = generate_system("seed-clearance", ["repo:a"])
    stations = list(generated.stations)

    for station in stations:
        assert station["transform"]["units"] == "meters"
        assert len(station["transform"]["position_m"]) == 3
        assert float(station["radius_m"]) > 0

    for index, left in enumerate(stations):
        for right in stations[index + 1 :]:
            required = (
                float(left["radius_m"])
                + float(right["radius_m"])
                + float(generated.star_system["navigation"]["minimum_clearance_m"])
            )
            assert _distance(left, right) >= required

    assert all(
        region["navigation"]["clearance_valid"] is True
        and region["navigation"]["placement_attempt_limit"] > 0
        for region in generated.regions.values()
    )


def test_world_clearance_includes_station_site_and_cross_region_pairs() -> None:
    generated = generate_system("seed-global-clearance", ["repo:a", "dataset:b"])
    minimum_clearance = float(
        generated.star_system["navigation"]["minimum_clearance_m"]
    )
    occupants = [
        ("station", str(station["region_id"]), station)
        for station in generated.stations
    ]
    occupants.extend(
        ("site", region_id, site)
        for region_id, region in generated.regions.items()
        for site in region["sites"]
    )
    measured_pair_types: set[str] = set()

    for index, (left_kind, left_region, left) in enumerate(occupants):
        for right_kind, right_region, right in occupants[index + 1 :]:
            if {left_kind, right_kind} == {"station", "site"}:
                measured_pair_types.add("station/site")
            if (
                left_kind == right_kind == "site"
                and left_region != right_region
            ):
                measured_pair_types.add("cross-region site/site")
            required = (
                float(left["radius_m"])
                + float(right["radius_m"])
                + minimum_clearance
            )
            assert _distance(left, right) >= required

    assert measured_pair_types == {"station/site", "cross-region site/site"}


def test_bounded_region_regeneration_preserves_other_and_frozen_regions() -> None:
    original = generate_system("seed-42", ["repo:a"])

    changed = regenerate_region(
        original, "region-2", recipe_patch={"density": 0.8}
    )

    assert changed is not original
    assert changed.regions["region-1"] == original.regions["region-1"]
    assert changed.regions["region-3"] == original.regions["region-3"]
    assert changed.regions["region-2"] != original.regions["region-2"]
    assert original.regions["region-2"]["recipe"]["density"] != 0.8
    assert changed.regions["region-2"]["recipe"]["density"] == 0.8
    assert changed.stations == original.stations
    assert changed.routes == original.routes
    assert changed.revision == original.revision + 1


def test_regenerated_region_respects_all_external_world_occupancy() -> None:
    original = generate_system("seed-regeneration-clearance", ["repo:a", "dataset:b"])

    changed = regenerate_region(
        original,
        "region-2",
        recipe_patch={"density": 0.8, "spread": 0.9},
    )

    minimum_clearance = float(
        changed.star_system["navigation"]["minimum_clearance_m"]
    )
    replacement_sites = changed.regions["region-2"]["sites"]
    external_occupants = list(changed.stations)
    external_occupants.extend(
        site
        for region_id, region in changed.regions.items()
        if region_id != "region-2"
        for site in region["sites"]
    )
    assert replacement_sites
    assert external_occupants
    for site in replacement_sites:
        for external in external_occupants:
            required = (
                float(site["radius_m"])
                + float(external["radius_m"])
                + minimum_clearance
            )
            assert _distance(site, external) >= required


def test_regeneration_emits_deterministic_diff_and_rollback_metadata() -> None:
    original = generate_system("seed-42", ["repo:a"])

    first = regenerate_region(
        original,
        "region-2",
        recipe_patch={"density": 0.8, "verticality": 0.4},
    )
    second = regenerate_region(
        original,
        "region-2",
        recipe_patch={"verticality": 0.4, "density": 0.8},
    )

    assert first.model_dump() == second.model_dump()
    event = first.events[-1]
    assert event["event_type"] == "world.region_regenerated"
    assert event["region_id"] == "region-2"
    assert event["diff"]["before_hash"] != event["diff"]["after_hash"]
    assert event["diff"]["changed_fields"]
    assert event["rollback"]["region"] == original.regions["region-2"]
    assert event["rollback"]["restore_revision"] == original.revision
    assert first.star_system["last_regeneration"] == {
        "event_id": event["event_id"],
        "region_id": "region-2",
        "diff": event["diff"],
        "rollback": event["rollback"],
    }


def test_frozen_or_out_of_bounds_region_regeneration_fails_closed() -> None:
    generated = generate_system("seed-42", ["repo:a"])

    with pytest.raises(ValueError, match="frozen"):
        regenerate_region(generated, "region-1", recipe_patch={"density": 0.8})
    with pytest.raises(ValueError, match="density"):
        regenerate_region(generated, "region-2", recipe_patch={"density": 1.1})
    with pytest.raises(ValueError, match="unsupported"):
        regenerate_region(generated, "region-2", recipe_patch={"chaos": 0.4})


def test_generated_models_are_deeply_immutable() -> None:
    generated = generate_system("seed-42", ["repo:a"])

    with pytest.raises(TypeError):
        generated.regions["region-2"]["recipe"]["density"] = 0.9


@pytest.mark.parametrize(
    "seed,sources",
    [
        ("api-key-secret", ["repo:a"]),
        ("seed-42", ["repo:a", "access_token:do-not-copy"]),
        ("seed-42", ["https://user:password@example.invalid/repo"]),
    ],
)
def test_generation_rejects_secret_shaped_persisted_inputs(
    seed: str, sources: list[str]
) -> None:
    with pytest.raises(ValueError, match="secret"):
        generate_system(seed, sources)


@pytest.mark.parametrize(
    "unsafe_reference",
    [
        "C:/Users/alice/.hermes/config.yaml",
        r"\\server\private\profile.yaml",
        "/home/alice/.config/hermes/config.yaml",
        "~/.config/hermes/config.yaml",
        "file:///home/alice/private/profile.yaml",
        "repo:Bearer=abcdefghijklmnopqrstuvwxyz",
        "repo:token=ghp_abcdefghijklmnopqrstuvwxyz",
        "repo:-----BEGIN-PRIVATE-KEY-----",
    ],
)
def test_generation_rejects_private_paths_and_credentials_in_semantic_references(
    unsafe_reference: str,
) -> None:
    with pytest.raises(ValueError, match="private filesystem path|secret"):
        generate_system("seed-42", [unsafe_reference])


def test_generation_accepts_safe_opaque_semantic_references() -> None:
    generated = generate_system(
        "seed-42",
        [
            "repo:org/project",
            "dataset:catalog/v1",
            "workspace:atlas-plan",
            "https://example.invalid/catalog/v1",
        ],
    )

    assert generated.semantic_sources == (
        "dataset:catalog/v1",
        "https://example.invalid/catalog/v1",
        "repo:org/project",
        "workspace:atlas-plan",
    )


def test_regeneration_rejects_secret_fields_in_recipe_patch() -> None:
    generated = generate_system("seed-42", ["repo:a"])

    with pytest.raises(ValueError, match="secret"):
        regenerate_region(
            generated,
            "region-2",
            recipe_patch={"density": 0.8, "api_key": "do-not-copy"},
        )
