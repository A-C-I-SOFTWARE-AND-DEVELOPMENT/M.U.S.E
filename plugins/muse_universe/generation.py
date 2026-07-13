from __future__ import annotations

import hashlib
import json
import math
import random
import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .catalog import STATIONS
from .models import deep_freeze
from .validation import validate_finite_numbers, validate_no_secret_fields


_SAFE_REFERENCE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}$")
_PRIVATE_PATH = re.compile(
    r"(?ix)(?:"
    r"(?<![a-z0-9])file:(?://)?"
    r"|(?<![a-z0-9])[a-z]:[\\/]"
    r"|(?<![a-z0-9])\\\\[^\\/\s]+[\\/]"
    r"|(?<![a-z0-9:])//[^/\s]+/"
    r"|(?<![a-z0-9])~[\\/]"
    r"|(?<![a-z0-9])\$\{?home\}?[\\/]"
    r"|(?<![a-z0-9])/(?:home|root|users|private|etc|var|tmp|opt|srv)(?:/|$)"
    r")"
)
_EDGE_TYPES = ("dependency", "communication", "deployment")
_MINIMUM_CLEARANCE_M = 250.0
_PLACEMENT_ATTEMPT_LIMIT = 64
_PATCH_FIELDS = frozenset({"anomaly_rate", "density", "spread", "verticality"})


@dataclass(frozen=True)
class _RegionSpec:
    region_id: str
    name: str
    frozen: bool
    recipe_items: tuple[tuple[str, float], ...]

    def recipe(self) -> dict[str, float]:
        return dict(self.recipe_items)


@dataclass(frozen=True)
class _RecipeStrategy:
    version: str
    region_specs: tuple[_RegionSpec, ...]
    region_generator: Callable[..., dict[str, Any]]

    @property
    def region_ids(self) -> tuple[str, ...]:
        return tuple(spec.region_id for spec in self.region_specs)

    def region_spec(self, region_id: str) -> _RegionSpec:
        for spec in self.region_specs:
            if spec.region_id == region_id:
                return spec
        raise ValueError(f"unknown region {region_id!r}")


_V1_REGION_SPECS = (
    _RegionSpec(
        region_id="region-1",
        name="Atlas Crown Inner Orbit",
        frozen=True,
        recipe_items=(
            ("anomaly_rate", 0.05),
            ("density", 0.30),
            ("spread", 0.40),
            ("verticality", 0.15),
        ),
    ),
    _RegionSpec(
        region_id="region-2",
        name="Production and Research Reach",
        frozen=False,
        recipe_items=(
            ("anomaly_rate", 0.12),
            ("density", 0.55),
            ("spread", 0.65),
            ("verticality", 0.30),
        ),
    ),
    _RegionSpec(
        region_id="region-3",
        name="Frontier and Deployment Reach",
        frozen=False,
        recipe_items=(
            ("anomaly_rate", 0.20),
            ("density", 0.42),
            ("spread", 0.85),
            ("verticality", 0.50),
        ),
    ),
)


class _OccupancyIndex:
    """Deterministic world-space occupancy shared by all generated regions."""

    def __init__(self, occupants: Sequence[Mapping[str, Any]] = ()) -> None:
        self._occupants: list[Mapping[str, Any]] = list(occupants)

    def allows(
        self,
        position: tuple[float, float, float],
        radius: float,
        minimum_clearance: float,
    ) -> bool:
        for occupant in self._occupants:
            other = occupant["transform"]["position_m"]
            distance = math.sqrt(
                sum(
                    (float(left) - float(right)) ** 2
                    for left, right in zip(position, other)
                )
            )
            required = radius + float(occupant["radius_m"]) + minimum_clearance
            if distance < required:
                return False
        return True

    def reserve(self, occupant: Mapping[str, Any]) -> None:
        self._occupants.append(occupant)

    def fallback_position(
        self, radius: float, minimum_clearance: float
    ) -> tuple[float, float, float]:
        furthest_edge = max(
            (
                float(occupant["transform"]["position_m"][0])
                + float(occupant["radius_m"])
                for occupant in self._occupants
            ),
            default=0.0,
        )
        return (
            round(furthest_edge + radius + minimum_clearance + 0.001, 3),
            0.0,
            0.0,
        )


class GeneratedSystem(BaseModel):
    """Immutable deterministic star-system projection and generation audit."""

    model_config = ConfigDict(frozen=True)

    system_id: str
    recipe_version: str
    seed: str
    semantic_sources: tuple[str, ...]
    revision: int = Field(ge=1)
    star_system: dict[str, Any]
    regions: dict[str, dict[str, Any]]
    stations: tuple[dict[str, Any], ...]
    routes: tuple[dict[str, Any], ...]
    events: tuple[dict[str, Any], ...] = ()

    @field_validator("star_system", "regions", mode="after")
    @classmethod
    def _freeze_mappings(cls, value: dict[str, Any]) -> dict[str, Any]:
        return deep_freeze(value)

    @field_validator("stations", "routes", "events", mode="after")
    @classmethod
    def _freeze_sequences(
        cls, value: tuple[dict[str, Any], ...]
    ) -> tuple[dict[str, Any], ...]:
        return deep_freeze(value)


def generate_system(
    seed: str,
    semantic_sources: Sequence[str],
    recipe_version: str = "1",
) -> GeneratedSystem:
    """Generate a reproducible Atlas Crown system from safe semantic refs."""

    seed = _safe_persisted_reference(seed, "seed")
    recipe_version = _safe_persisted_reference(recipe_version, "recipe_version")
    strategy = _recipe_strategy(recipe_version)
    recipe_version = strategy.version
    sources = _normalize_semantic_sources(semantic_sources)

    # This is the canonical system RNG required by the generation contract.
    seed_digest = hashlib.sha256(
        f"{recipe_version}:{seed}".encode("utf-8")
    ).digest()
    rng = random.Random(seed_digest)
    system_id = f"sys_{seed_digest.hex()[:20]}"

    recipes = {
        spec.region_id: spec.recipe() for spec in strategy.region_specs
    }
    sources_by_region = _sources_by_region(sources, strategy.region_ids)
    stations = _authored_stations(rng, strategy.region_ids)
    occupancy = _OccupancyIndex(stations)
    regions: dict[str, dict[str, Any]] = {}
    for spec in strategy.region_specs:
        regions[spec.region_id] = strategy.region_generator(
            seed=seed,
            recipe_version=recipe_version,
            region_spec=spec,
            recipe=recipes[spec.region_id],
            semantic_sources=sources_by_region[spec.region_id],
            occupancy=occupancy,
        )
    routes = _typed_routes(stations, sources, rng)
    generation_event = {
        "event_id": f"gen_{seed_digest.hex()[:24]}",
        "event_type": "star_system.generated",
        "system_id": system_id,
        "revision": 1,
        "recipe_version": recipe_version,
        "seed": seed,
        "semantic_sources": list(sources),
        "region_ids": list(strategy.region_ids),
        "rollback": {},
    }
    star_system = {
        "id": system_id,
        "entity_type": "star_system",
        "version": 1,
        "revision": 1,
        "seed": seed,
        "recipe_version": recipe_version,
        "semantic_sources": list(sources),
        "recipe": {
            "version": recipe_version,
            "regions": recipes,
        },
        "region_recipes": recipes,
        "navigation": {
            "units": "meters",
            "minimum_clearance_m": _MINIMUM_CLEARANCE_M,
            "placement_attempt_limit": _PLACEMENT_ATTEMPT_LIMIT,
        },
        "authorship": "MUSE-ORIGINAL-1.0",
    }
    result = GeneratedSystem(
        system_id=system_id,
        recipe_version=recipe_version,
        seed=seed,
        semantic_sources=sources,
        revision=1,
        star_system=star_system,
        regions=regions,
        stations=stations,
        routes=routes,
        events=(generation_event,),
    )
    _validate_generation(result)
    return result


def regenerate_region(
    generated: GeneratedSystem,
    region_id: str,
    *,
    recipe_patch: Mapping[str, object],
) -> GeneratedSystem:
    """Regenerate one unfrozen region and attach deterministic rollback data."""

    if not isinstance(generated, GeneratedSystem):
        raise TypeError("generated must be a GeneratedSystem")
    strategy = _recipe_strategy(generated.recipe_version)
    if region_id not in generated.regions:
        raise ValueError(f"unknown region {region_id!r}")
    previous_region = generated.regions[region_id]
    if previous_region.get("frozen") is True:
        raise ValueError(f"region {region_id!r} is frozen")
    patch = _validated_recipe_patch(recipe_patch)
    previous_recipe = dict(previous_region["recipe"])
    next_recipe = {**previous_recipe, **patch}
    region_sources = tuple(previous_region.get("semantic_sources", ()))
    occupancy = _external_occupancy(generated, excluded_region_id=region_id)
    next_region = strategy.region_generator(
        seed=generated.seed,
        recipe_version=generated.recipe_version,
        region_spec=strategy.region_spec(region_id),
        recipe=next_recipe,
        semantic_sources=region_sources,
        occupancy=occupancy,
    )

    before_hash = _content_hash(previous_region)
    after_hash = _content_hash(next_region)
    changed_fields = tuple(
        sorted(
            key
            for key in set(previous_region) | set(next_region)
            if previous_region.get(key) != next_region.get(key)
        )
    )
    diff = {
        "region_id": region_id,
        "before_hash": before_hash,
        "after_hash": after_hash,
        "changed_fields": list(changed_fields),
        "recipe_patch": patch,
    }
    rollback = {
        "region_id": region_id,
        "region": previous_region,
        "region_hash": before_hash,
        "restore_revision": generated.revision,
        "recipe": previous_recipe,
    }
    next_revision = generated.revision + 1
    event_material = {
        "system_id": generated.system_id,
        "revision": next_revision,
        "region_id": region_id,
        "diff": diff,
        "rollback": rollback,
    }
    event_id = f"regen_{_content_hash(event_material)[:24]}"
    regeneration_event = {
        "event_id": event_id,
        "event_type": "world.region_regenerated",
        "system_id": generated.system_id,
        "revision": next_revision,
        "region_id": region_id,
        "bounded_scope": {"region_ids": [region_id]},
        "diff": diff,
        "rollback": rollback,
    }

    regions = dict(generated.regions)
    regions[region_id] = next_region
    region_recipes = {
        key: dict(value["recipe"]) for key, value in regions.items()
    }
    star_system = dict(generated.star_system)
    star_system.update(
        {
            "version": next_revision,
            "revision": next_revision,
            "recipe": {
                "version": generated.recipe_version,
                "regions": region_recipes,
            },
            "region_recipes": region_recipes,
            "last_regeneration": {
                "event_id": event_id,
                "region_id": region_id,
                "diff": diff,
                "rollback": rollback,
            },
        }
    )
    result = GeneratedSystem(
        system_id=generated.system_id,
        recipe_version=generated.recipe_version,
        seed=generated.seed,
        semantic_sources=generated.semantic_sources,
        revision=next_revision,
        star_system=star_system,
        regions=regions,
        stations=generated.stations,
        routes=generated.routes,
        events=(*generated.events, regeneration_event),
    )
    _validate_generation(result)
    return result


def _authored_stations(
    rng: random.Random, region_ids: tuple[str, ...]
) -> tuple[dict[str, Any], ...]:
    rotation = rng.uniform(0.0, math.tau)
    stations: list[dict[str, Any]] = [
        {
            "id": "stn_atlas_crown",
            "type": "atlas_crown",
            "name": "Atlas Crown Neural Core Citadel",
            "region_id": "region-1",
            "authored_landmark": True,
            "radius_m": 650.0,
            "transform": _metric_transform((0.0, 0.0, 0.0), yaw_degrees=0.0),
            "physical_form": {
                "stationary_neural_core": True,
                "non_rotating_axial_spine": True,
                "counter_rotating_structures": 2,
                "crown_sectors": 5,
            },
        }
    ]
    count = len(STATIONS)
    for index, station in enumerate(STATIONS):
        angle = rotation + math.tau * index / count
        orbital_radius = 6_200.0
        position = (
            round(math.cos(angle) * orbital_radius, 3),
            round(math.sin(angle) * orbital_radius, 3),
            float(((index % 3) - 1) * 700),
        )
        station_type = str(station["id"])
        stations.append(
            {
                "id": f"stn_{station_type}",
                "type": station_type,
                "name": station_type.replace("_", " ").title(),
                "region_id": region_ids[index % len(region_ids)],
                "authored_landmark": True,
                "radius_m": 180.0,
                "transform": _metric_transform(
                    position,
                    yaw_degrees=round(math.degrees(angle) + 90.0, 3),
                ),
            }
        )
    return tuple(stations)


def _typed_routes(
    stations: tuple[dict[str, Any], ...],
    semantic_sources: tuple[str, ...],
    rng: random.Random,
) -> tuple[dict[str, Any], ...]:
    atlas = stations[0]
    routes: list[dict[str, Any]] = []
    edge_offset = rng.randrange(len(_EDGE_TYPES))
    for index, station in enumerate(stations[1:]):
        edge_type = _EDGE_TYPES[(index + edge_offset) % len(_EDGE_TYPES)]
        routes.append(
            _route_record(
                source=atlas,
                target=station,
                edge_type=edge_type,
                semantic_source=None,
            )
        )

    # Explicit semantic sources add only typed, inspectable graph routes. They
    # never infer a relationship from visual proximity.
    station_count = len(stations) - 1
    for source_ref in semantic_sources:
        digest = hashlib.sha256(source_ref.encode("utf-8")).digest()
        left_index = int.from_bytes(digest[:2], "big") % station_count + 1
        right_index = int.from_bytes(digest[2:4], "big") % station_count + 1
        if right_index == left_index:
            right_index = right_index % station_count + 1
        edge_type = _EDGE_TYPES[digest[4] % len(_EDGE_TYPES)]
        routes.append(
            _route_record(
                source=stations[left_index],
                target=stations[right_index],
                edge_type=edge_type,
                semantic_source=source_ref,
            )
        )
    return tuple(sorted(routes, key=lambda route: str(route["id"])))


def _route_record(
    *,
    source: Mapping[str, Any],
    target: Mapping[str, Any],
    edge_type: str,
    semantic_source: str | None,
) -> dict[str, Any]:
    source_position = source["transform"]["position_m"]
    target_position = target["transform"]["position_m"]
    distance = math.sqrt(
        sum(
            (float(left) - float(right)) ** 2
            for left, right in zip(source_position, target_position)
        )
    )
    material = (
        f"{source['id']}\0{target['id']}\0{edge_type}\0{semantic_source or ''}"
    )
    route_id = hashlib.sha256(material.encode("utf-8")).hexdigest()[:20]
    return {
        "id": f"rte_{route_id}",
        "source": source["id"],
        "target": target["id"],
        "edge_type": edge_type,
        "semantic_source": semantic_source,
        "distance_m": round(distance, 3),
        "observation_state": "observed" if semantic_source else "authored",
    }


def _generate_region_v1(
    *,
    seed: str,
    recipe_version: str,
    region_spec: _RegionSpec,
    recipe: Mapping[str, object],
    semantic_sources: Sequence[str],
    occupancy: _OccupancyIndex,
) -> dict[str, Any]:
    region_id = region_spec.region_id
    normalized_recipe = _validated_recipe(recipe)
    sources = tuple(sorted(set(semantic_sources)))
    material = {
        "recipe_version": recipe_version,
        "seed": seed,
        "region_id": region_id,
        "recipe": normalized_recipe,
        "semantic_sources": sources,
    }
    region_rng = random.Random(
        hashlib.sha256(_canonical_json(material).encode("utf-8")).digest()
    )
    density = float(normalized_recipe["density"])
    spread = float(normalized_recipe["spread"])
    verticality = float(normalized_recipe["verticality"])
    site_count = max(1, min(8, round(2 + density * 4 + len(sources))))
    clearance = max(
        _MINIMUM_CLEARANCE_M,
        round(180.0 + (1.0 - density) * 120.0, 3),
    )
    sites = _place_region_sites(
        rng=region_rng,
        region_id=region_id,
        count=site_count,
        sources=sources,
        spread=spread,
        verticality=verticality,
        minimum_clearance=clearance,
        occupancy=occupancy,
    )
    semantic_weight = sum(
        int.from_bytes(hashlib.sha256(source.encode("utf-8")).digest()[:4], "big")
        for source in sources
    )
    return {
        "id": region_id,
        "name": region_spec.name,
        "frozen": region_spec.frozen,
        "recipe": normalized_recipe,
        "semantic_sources": list(sources),
        "metrics": {
            "source_count": len(sources),
            "site_count": site_count,
            "semantic_weight": semantic_weight,
            "density_index": round(density * (1 + len(sources)), 6),
        },
        "navigation": {
            "units": "meters",
            "minimum_clearance_m": clearance,
            "placement_attempt_limit": _PLACEMENT_ATTEMPT_LIMIT,
            "clearance_valid": _sites_have_clearance(sites, clearance),
        },
        "sites": sites,
    }


_RECIPE_STRATEGIES: Mapping[str, _RecipeStrategy] = MappingProxyType(
    {
        "1": _RecipeStrategy(
            version="1",
            region_specs=_V1_REGION_SPECS,
            region_generator=_generate_region_v1,
        )
    }
)


def _recipe_strategy(recipe_version: str) -> _RecipeStrategy:
    strategy = _RECIPE_STRATEGIES.get(recipe_version)
    if strategy is None:
        raise ValueError(f"unsupported recipe_version {recipe_version!r}")
    return strategy


def _external_occupancy(
    generated: GeneratedSystem, *, excluded_region_id: str
) -> _OccupancyIndex:
    occupancy = _OccupancyIndex(generated.stations)
    for region_id, region in generated.regions.items():
        if region_id == excluded_region_id:
            continue
        for site in region["sites"]:
            occupancy.reserve(site)
    return occupancy


def _place_region_sites(
    *,
    rng: random.Random,
    region_id: str,
    count: int,
    sources: tuple[str, ...],
    spread: float,
    verticality: float,
    minimum_clearance: float,
    occupancy: _OccupancyIndex,
) -> list[dict[str, Any]]:
    sites: list[dict[str, Any]] = []
    horizontal_extent = 1_500.0 + spread * 3_500.0
    vertical_extent = 200.0 + verticality * 1_800.0
    for index in range(count):
        radius = round(70.0 + rng.uniform(0.0, 35.0), 3)
        position: tuple[float, float, float] | None = None
        for _attempt in range(_PLACEMENT_ATTEMPT_LIMIT):
            candidate = (
                round(rng.uniform(-horizontal_extent, horizontal_extent), 3),
                round(rng.uniform(-horizontal_extent, horizontal_extent), 3),
                round(rng.uniform(-vertical_extent, vertical_extent), 3),
            )
            if occupancy.allows(candidate, radius, minimum_clearance):
                position = candidate
                break
        if position is None:
            position = occupancy.fallback_position(radius, minimum_clearance)
        source_ref = sources[index % len(sources)] if sources else None
        site_material = f"{region_id}\0{index}\0{source_ref or 'authored'}"
        site_id = hashlib.sha256(site_material.encode("utf-8")).hexdigest()[:20]
        site = {
            "id": f"site_{site_id}",
            "region_id": region_id,
            "kind": _site_kind(source_ref, index),
            "source_ref": source_ref,
            "radius_m": radius,
            "transform": _metric_transform(
                position, yaw_degrees=round(rng.uniform(0.0, 360.0), 3)
            ),
        }
        sites.append(site)
        occupancy.reserve(site)
    return sites


def _position_has_clearance(
    position: tuple[float, float, float],
    radius: float,
    sites: Sequence[Mapping[str, Any]],
    minimum_clearance: float,
) -> bool:
    for site in sites:
        other = site["transform"]["position_m"]
        distance = math.sqrt(
            sum(
                (float(left) - float(right)) ** 2
                for left, right in zip(position, other)
            )
        )
        if distance < radius + float(site["radius_m"]) + minimum_clearance:
            return False
    return True


def _sites_have_clearance(
    sites: Sequence[Mapping[str, Any]], minimum_clearance: float
) -> bool:
    for index, site in enumerate(sites):
        position = tuple(float(value) for value in site["transform"]["position_m"])
        if not _position_has_clearance(
            position,
            float(site["radius_m"]),
            sites[:index],
            minimum_clearance,
        ):
            return False
    return True


def _metric_transform(
    position: tuple[float, float, float], *, yaw_degrees: float
) -> dict[str, Any]:
    return {
        "units": "meters",
        "position_m": [round(float(value), 3) for value in position],
        "rotation_degrees": [0.0, round(float(yaw_degrees), 3), 0.0],
        "scale": [1.0, 1.0, 1.0],
    }


def _sources_by_region(
    semantic_sources: tuple[str, ...],
    region_ids: tuple[str, ...],
) -> dict[str, tuple[str, ...]]:
    grouped: dict[str, list[str]] = {region_id: [] for region_id in region_ids}
    for source in semantic_sources:
        digest = hashlib.sha256(source.encode("utf-8")).digest()
        grouped[region_ids[digest[0] % len(region_ids)]].append(source)
    return {key: tuple(value) for key, value in grouped.items()}


def _normalize_semantic_sources(values: Sequence[str]) -> tuple[str, ...]:
    if isinstance(values, (str, bytes, bytearray)) or not isinstance(values, Sequence):
        raise ValueError("semantic_sources must be a sequence of safe references")
    return tuple(
        sorted(
            {
                _safe_persisted_reference(value, "semantic source")
                for value in values
            }
        )
    )


def _safe_persisted_reference(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value or not value.isprintable():
        raise ValueError(f"{field_name} must be a printable string")
    if _looks_private_path(value):
        raise ValueError(f"{field_name} contains a private filesystem path")
    if _looks_secretish(value):
        raise ValueError(f"{field_name} contains secret-like material")
    if not _SAFE_REFERENCE.fullmatch(value):
        raise ValueError(f"{field_name} is not a safe persisted reference")
    return value


def _validated_recipe_patch(values: Mapping[str, object]) -> dict[str, float]:
    if not isinstance(values, Mapping):
        raise ValueError("recipe_patch must be a mapping")
    validate_no_secret_fields(values, path="recipe_patch")
    validate_finite_numbers(values, path="recipe_patch")
    unsupported = set(values) - _PATCH_FIELDS
    if unsupported:
        raise ValueError(
            "unsupported recipe patch fields: " + ", ".join(sorted(unsupported))
        )
    if not values:
        raise ValueError("recipe_patch cannot be empty")
    return _validated_recipe(values, partial=True)


def _validated_recipe(
    values: Mapping[str, object], *, partial: bool = False
) -> dict[str, float]:
    validate_no_secret_fields(values, path="recipe")
    validate_finite_numbers(values, path="recipe")
    if not partial and set(values) != _PATCH_FIELDS:
        raise ValueError("region recipe fields are incomplete")
    normalized: dict[str, float] = {}
    for key, value in values.items():
        if key not in _PATCH_FIELDS:
            raise ValueError(f"unsupported recipe field {key!r}")
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"recipe {key} must be numeric")
        number = float(value)
        if not 0.0 <= number <= 1.0:
            raise ValueError(f"recipe {key} must be between 0 and 1")
        normalized[key] = number
    return {key: normalized[key] for key in sorted(normalized)}


def _site_kind(source_ref: str | None, index: int) -> str:
    if source_ref is None:
        return "authored_frontier"
    prefix = source_ref.partition(":")[0].casefold()
    return {
        "dataset": "dataset_moon",
        "repo": "repository_world",
        "workspace": "workspace_planet",
    }.get(prefix, "knowledge_domain") if index % 5 else "research_anomaly"


def _content_hash(value: object) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _canonical_json(value: object) -> str:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def _looks_secretish(value: str) -> bool:
    normalized = re.sub(r"[^a-z0-9]+", "_", value.casefold()).strip("_")
    segments = normalized.split("_") if normalized else []
    segment_set = set(segments)
    if segment_set & {"bearer", "credential", "credentials", "passwd", "password", "secret"}:
        return True
    joined = "_".join(segments)
    if any(
        marker in joined
        for marker in (
            "access_token",
            "api_key",
            "oauth_token",
            "private_key",
            "provider_key",
        )
    ):
        return True
    if re.search(r"(?i)(?:^|[^a-z0-9])sk-[a-z0-9_-]{8,}", value):
        return True
    if re.search(
        r"(?i)\b(?:access[_ -]?token|api[_ -]?key|oauth[_ -]?token|"
        r"provider[_ -]?key|token)\s*[:=]\s*\S+",
        value,
    ):
        return True
    if re.search(r"(?i)-----BEGIN(?:[ -][A-Z0-9]+)*[ -]PRIVATE[ -]KEY-----", value):
        return True
    if re.search(r"(?i)\bgh[pousr]_[a-z0-9]{20,}\b", value):
        return True
    return bool(re.search(r"^[a-z][a-z0-9+.-]*://[^/@\s]+:[^/@\s]+@", value))


def _looks_private_path(value: str) -> bool:
    return bool(_PRIVATE_PATH.search(value))


def _validate_generation(generated: GeneratedSystem) -> None:
    payload = generated.model_dump(mode="python")
    validate_no_secret_fields(payload, path="generated_system")
    validate_finite_numbers(payload, path="generated_system")
    station_ids = {station["id"] for station in generated.stations}
    if len(station_ids) != len(generated.stations):
        raise ValueError("generated station ids are not unique")
    for route in generated.routes:
        if route["edge_type"] not in _EDGE_TYPES:
            raise ValueError("generated route edge type is invalid")
        if route["source"] not in station_ids or route["target"] not in station_ids:
            raise ValueError("generated route endpoint does not exist")
    if any(
        region["navigation"]["clearance_valid"] is not True
        for region in generated.regions.values()
    ):
        raise ValueError("generated region navigation clearance is invalid")
    occupants: list[Mapping[str, Any]] = list(generated.stations)
    occupants.extend(
        site
        for region in generated.regions.values()
        for site in region["sites"]
    )
    occupant_ids = [str(occupant["id"]) for occupant in occupants]
    if len(set(occupant_ids)) != len(occupant_ids):
        raise ValueError("generated world occupancy ids are not unique")
    for index, left in enumerate(occupants):
        left_position = left["transform"]["position_m"]
        for right in occupants[index + 1 :]:
            right_position = right["transform"]["position_m"]
            distance = math.sqrt(
                sum(
                    (float(a) - float(b)) ** 2
                    for a, b in zip(left_position, right_position)
                )
            )
            required = (
                float(left["radius_m"])
                + float(right["radius_m"])
                + _MINIMUM_CLEARANCE_M
            )
            if distance < required:
                raise ValueError(
                    "world navigation clearance is invalid between "
                    f"{left['id']!r} and {right['id']!r}"
                )
