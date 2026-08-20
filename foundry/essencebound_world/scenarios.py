"""Curated scenario seeds spanning every Essencebound dataset category."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ScenarioSeed:
    category: str
    subject: str
    failure: str
    success: str
    issue_code: str
    action_code: str
    constraint: tuple[str, float, float, str] | None = None


SCENARIO_SEEDS = {
    "CONCEPT_FIDELITY": ScenarioSeed(
        "CONCEPT_FIDELITY", "temple district",
        "white marble columns and neon roof outlines replace the dark-stone and bronze language",
        "dark monumental stone, aged bronze frames, tall arches, and restrained cyan conduits form a coherent identity",
        "GENERIC_FANTASY_LANGUAGE", "COMPARE_CONCEPT_SHEETS"),
    "MACRO_LAYOUT": ScenarioSeed(
        "MACRO_LAYOUT", "Axiom hub composition",
        "all landmarks carry equal visual weight and the Axiom Core has no readable hierarchy",
        "the Axiom Core anchors the view with two secondary landmarks and quieter tertiary detail",
        "WRONG_STAGE_ORDER", "RETURN_TO_BLOCKING_STAGE"),
    "TRAVERSAL": ScenarioSeed(
        "TRAVERSAL", "Archive approach",
        "the primary route ends above the plaza with no stairs, ramp, lift, or alternate arrival",
        "the primary route reaches a clear landing and an optional loop returns to the hub",
        "MISSING_LANDING", "ADD_VALID_LANDING"),
    "BRIDGES": ScenarioSeed(
        "BRIDGES", "monumental bridge",
        "the span meets bare cliff, lacks anchors, and rises too steeply for the intended encounter",
        "both ends have supported landings, readable anchors, safe width, lighting, and collision",
        "INVALID_BRIDGE_GRADE", "REDUCE_GRADE", ("BRIDGE_GRADE_DEG", 31.0, 25.0, "degrees")),
    "SKYWAYS": ScenarioSeed(
        "SKYWAYS", "Skyway station",
        "the arrival gate faces a wall and gives the player no readable exit",
        "the gate frames the destination, provides safe arrival clearance, and connects to the road network",
        "UNREACHABLE_DESTINATION", "CREATE_REACHABLE_ROUTE"),
    "PLAYER_SCALE": ScenarioSeed(
        "PLAYER_SCALE", "public entrance",
        "a ninety-five-centimeter door and oversized stair rise conflict with the 180 cm player reference",
        "the entrance, landing, railing, and stair dimensions remain within the intended human-scale ranges",
        "HUMAN_SCALE_VIOLATION", "RESTORE_HUMAN_SCALE", ("DOOR_WIDTH_CM", 95.0, 150.0, "cm")),
    "ARCHITECTURE": ScenarioSeed(
        "ARCHITECTURE", "Wayfinder hall",
        "the hall floats above terrain and decorative crystals are its only explanation",
        "layered foundations, buttresses, bronze clamps, and Essence machinery explain every major load",
        "UNSUPPORTED_STRUCTURE", "ADD_STRUCTURAL_SUPPORT"),
    "ARCHITECTURAL_PURPOSE": ScenarioSeed(
        "ARCHITECTURAL_PURPOSE", "maintenance annex",
        "twenty towers fill empty space without location, function, entrance, or gameplay purpose",
        "the annex sits beside the Skyway because it maintains the gate and creates a secondary service route",
        "WRONG_STAGE_ORDER", "RETURN_TO_BLOCKING_STAGE"),
    "FLOATING_ISLAND_GEOLOGY": ScenarioSeed(
        "FLOATING_ISLAND_GEOLOGY", "floating island underside",
        "a smooth symmetrical cone forms the entire underside with uniform scaled rocks",
        "fractured shelves, tapering plates, roots, mineral seams, and selective fragments form an asymmetric silhouette",
        "GENERIC_FANTASY_LANGUAGE", "COMPARE_CONCEPT_SHEETS"),
    "LANDMASS": ScenarioSeed(
        "LANDMASS", "regional island terrain",
        "the island radius grew but every building and crystal was uniformly scaled with it",
        "human-scaled settlements occupy an expanded landscape of wilderness, roads, ruins, and landmarks",
        "HUMAN_SCALE_VIOLATION", "RESTORE_HUMAN_SCALE", ("ISLAND_RADIUS_UU", 343000.0, 343000.0, "uu")),
    "WILDERNESS": ScenarioSeed(
        "WILDERNESS", "wilderness corridor",
        "uniformly scattered clutter erases paths, silhouettes, and encounter clearings",
        "distance-aware vegetation clusters frame readable trails, clearings, and regional landmarks",
        "COLLISION_BLOCKER", "RESTORE_CLEARANCE"),
    "ROADS": ScenarioSeed(
        "ROADS", "capital road network",
        "ornamental road segments stop in fields and never connect the capital, villages, or services",
        "primary, secondary, ring, and service roads connect real destinations through readable junctions",
        "BROKEN_ROAD_NETWORK", "CONNECT_ROAD_DESTINATIONS"),
    "SETTLEMENTS": ScenarioSeed(
        "SETTLEMENTS", "satellite village",
        "the village copies the capital block-for-block and has no regional function or history",
        "the village has a distinct economy, terrain response, civic focus, and connection to regional travel",
        "DUPLICATE_SETTLEMENT", "DIFFERENTIATE_SETTLEMENT"),
    "MARKETS": ScenarioSeed(
        "MARKETS", "market square",
        "stalls block the primary route and have no storage, delivery access, or vendor logic",
        "stalls form navigable edges around a civic focus with service access and readable circulation",
        "INVALID_PLAYER_CLEARANCE", "RESTORE_CLEARANCE"),
    "SHOPS": ScenarioSeed(
        "SHOPS", "blacksmith shop",
        "the shop façade has no entrance, work yard, chimney logic, storage, or connection to trade routes",
        "the forge, storage, sales space, delivery access, and warm inhabited lighting support its role",
        "MISSING_INTERIOR_LOGIC", "FIX_INTERIOR_CIRCULATION"),
    "INTERIORS": ScenarioSeed(
        "INTERIORS", "Archive reading hall",
        "the exterior door opens into a blocked wall and rooms have no circulation or service function",
        "entrance, public loop, restricted stacks, vertical route, and service spaces form a coherent plan",
        "MISSING_INTERIOR_LOGIC", "FIX_INTERIOR_CIRCULATION"),
    "ENVIRONMENTAL_STORYTELLING": ScenarioSeed(
        "ENVIRONMENTAL_STORYTELLING", "abandoned refinery",
        "random debris is scattered without explaining work, damage, abandonment, or recovery",
        "tool placement, damaged conduits, repair attempts, and evacuation traces reveal a causal history",
        "MISSING_POWER_CAUSALITY", "CONNECT_ESSENCE_NETWORK"),
    "MATERIALS": ScenarioSeed(
        "MATERIALS", "monumental façade",
        "uniform clean materials erase age, use, moisture, repairs, and material hierarchy",
        "dark stone, aged bronze, localized weathering, and selective luminous details reinforce construction and history",
        "MISSING_CONCEPT_COMPARISON", "COMPARE_CONCEPT_SHEETS"),
    "LIGHTING": ScenarioSeed(
        "LIGHTING", "inhabited exterior-interior threshold",
        "cyan emission covers every edge and fog hides unfinished geometry",
        "cold restrained Essence light outside contrasts with warm amber inhabited light inside",
        "EXCESSIVE_EMISSIVE", "RESTRAIN_EMISSIVE"),
    "MAGIC": ScenarioSeed(
        "MAGIC", "runic mechanism",
        "particles and glow appear everywhere without an active system or readable state",
        "rotation, restrained particles, and light flow appear only where the powered mechanism justifies them",
        "MISSING_POWER_CAUSALITY", "CONNECT_ESSENCE_NETWORK"),
    "ESSENCE_INFRASTRUCTURE": ScenarioSeed(
        "ESSENCE_INFRASTRUCTURE", "Essence distribution network",
        "glowing lines decorate surfaces without a crystal source, conduit path, or consuming facility",
        "a crystal source feeds conduits, floor channels, machinery, and the destination facility with damaged and dormant states",
        "MISSING_POWER_CAUSALITY", "CONNECT_ESSENCE_NETWORK"),
    "CRYSTALS": ScenarioSeed(
        "CRYSTALS", "crystal machinery bay",
        "identical crystals cover every surface and flatten the hero hierarchy",
        "crystals cluster at sources, housings, damaged conduits, and high-value machinery",
        "EXCESSIVE_EMISSIVE", "RESTRAIN_EMISSIVE"),
    "COMPOSITION": ScenarioSeed(
        "COMPOSITION", "player-height vista",
        "foreground, midground, background, and distant silhouettes compete without a focal hierarchy",
        "foreground framing leads to one primary focus, two secondary landmarks, and quieter distant depth",
        "MISSING_CONCEPT_COMPARISON", "COMPARE_CONCEPT_SHEETS"),
    "SILHOUETTE": ScenarioSeed(
        "SILHOUETTE", "Grand Suspended Archive",
        "the hero location is indistinguishable from repeated generic towers at distance",
        "the Archive reads from silhouette through a unique vertical mass, controlled curves, and suspended structure",
        "GENERIC_FANTASY_LANGUAGE", "COMPARE_CONCEPT_SHEETS"),
    "PERFORMANCE": ScenarioSeed(
        "PERFORMANCE", "island population pass",
        "the generator proposes 1.9 million instances and calls the result performant without measurement",
        "the island remains within the preferred gate and reports measured VRAM, frame time, culling, and instance counts",
        "INSTANCE_BUDGET_EXCEEDED", "REDUCE_INSTANCE_DENSITY", ("ISLAND_INSTANCES", 1900000.0, 600000.0, "instances")),
    "INSTANCING": ScenarioSeed(
        "INSTANCING", "procedural placement batch",
        "one giant instance component spans kilometers and gives culling unusable bounds",
        "mesh, materials, cull settings, and kilometer-scale cell form localized instance batches",
        "UNPARTITIONED_INSTANCING", "PARTITION_BY_CELL", ("ISLAND_INSTANCES", 900000.0, 600000.0, "instances")),
    "CULLING": ScenarioSeed(
        "CULLING", "distant wilderness cells",
        "saved cull distances are treated as proof even though runtime bounds and visibility were never measured",
        "localized bounds and distance-aware placement are verified in the defined runtime QA view",
        "CULLING_NOT_MEASURED", "MEASURE_CULLING", ("FRAME_TIME_REGRESSION_PERCENT", 28.0, 20.0, "percent")),
    "DESTRUCTION": ScenarioSeed(
        "DESTRUCTION", "combat arena support",
        "a destructible pillar removes the only exit bridge when broken",
        "breakable props preserve critical traversal or reveal a verified replacement route",
        "UNJUSTIFIED_DESTRUCTION", "EXEMPT_CRITICAL_STRUCTURE"),
    "INTERACTION": ScenarioSeed(
        "INTERACTION", "inactive Wayfinder console",
        "the console glows but supplies no affordance, response, inactive state, or failure feedback",
        "the console communicates availability, interaction, success, damage, and dormant states",
        "MISSING_INTERACTION_FEEDBACK", "ADD_INTERACTION_STATE"),
    "COLLISION": ScenarioSeed(
        "COLLISION", "primary combat route",
        "invisible collision blocks the intended path while the visible opening appears clear",
        "collision follows visible structure and the intended player route passes the traversal test",
        "COLLISION_BLOCKER", "REPAIR_COLLISION"),
    "OBJECT_INTERSECTIONS": ScenarioSeed(
        "OBJECT_INTERSECTIONS", "bridge tower joint",
        "the tower clips through the deck and cliff without a designed joint or load path",
        "a layered foundation, pier, clamp, and cut-stone transition make the joint intentional",
        "ACCIDENTAL_INTERSECTION", "REPAIR_INTERSECTION"),
    "BLENDER": ScenarioSeed(
        "BLENDER", "Blender world scene",
        "a script exit code is treated as proof that collections, duplicates, scale, cameras, and geometry are correct",
        "the scene is inspected through QA collections, player-eye cameras, scale checks, and duplicate cleanup reports",
        "MISSING_SCENE_EVIDENCE", "INSPECT_SCENE"),
    "UNREAL": ScenarioSeed(
        "UNREAL", "Unreal island map",
        "all twelve Skyrim-scale islands are merged blindly into one map without verifying project architecture",
        "each island uses the verified map and streaming architecture while Axiom remains the measured hub and vista",
        "MISSING_REPO_EVIDENCE", "INSPECT_REPOSITORY"),
    "PYTHON_GENERATION": ScenarioSeed(
        "PYTHON_GENERATION", "world placement generator",
        "the generator creates millions of uniform objects without manifests, cells, seeds, or validation",
        "deterministic cell-aware generation emits manifests, counts, bounds, provenance, and verifier inputs",
        "UNPARTITIONED_INSTANCING", "PARTITION_BY_CELL"),
    "REPO_REASONING": ScenarioSeed(
        "REPO_REASONING", "bridge kit manifest",
        "a missing manifest entry is ignored and the asset is claimed to exist",
        "the registered path and hash are inspected before route generation references the asset",
        "MISSING_REPO_EVIDENCE", "INSPECT_REPOSITORY"),
    "VERIFICATION": ScenarioSeed(
        "VERIFICATION", "world validation claim",
        "process liveness or exit code zero is treated as proof that every world gate passed",
        "each claim names actual repository, scene, render, test, collision, or performance evidence",
        "FALSE_COMPLETION_CLAIM", "WITHHOLD_COMPLETION"),
    "FAILURE_DETECTION": ScenarioSeed(
        "FAILURE_DETECTION", "eastern causeway review",
        "a roofline endpoint is approved because the bridge visually reaches the district",
        "the suspended endpoint is classified as inaccessible and corrected before materials",
        "MISSING_LANDING", "ADD_VALID_LANDING"),
    "QUALITY_GATES": ScenarioSeed(
        "QUALITY_GATES", "AAA screenshot gate",
        "greybox geometry with fog is called visually final after automation passes",
        "clear player-height renders, concept comparison, materials, lighting, collision, and performance all pass",
        "FALSE_COMPLETION_CLAIM", "WITHHOLD_COMPLETION"),
    "COMPLETION_STATUS": ScenarioSeed(
        "COMPLETION_STATUS", "island completion report",
        "the report declares AAA complete while traversal and performance evidence are absent",
        "the report remains at its verified stage and names every outstanding gate",
        "FALSE_COMPLETION_CLAIM", "WITHHOLD_COMPLETION"),
    "TASK_PRIORITIZATION": ScenarioSeed(
        "TASK_PRIORITIZATION", "Archive production order",
        "material polish is scheduled while the major playable landmark has no connection",
        "connectivity and structural gates pass before material, lighting, and polish work",
        "WRONG_STAGE_ORDER", "RETURN_TO_BLOCKING_STAGE"),
}

LOCATIONS = (
    "Firstbound Arrival", "Axiom Core", "Firstbound Overlook", "Grand Suspended Archive",
    "Crystal Sanctum", "Arena Island", "Glyph Ruins", "Skyway Station", "Chronos capital",
    "eastern village", "western wilderness", "northern market", "southern refinery",
    "Archive service district", "Wayfinder terrace", "river ravine", "outer gate",
    "temple quarter", "alchemist lane", "blacksmith yard", "library court",
    "floating quarry", "coastal shelf", "undercity approach", "distant vista cell",
)

CONDITIONS = (
    "review occurs before structural sign-off",
    "review occurs at player height in clear weather",
    "proposal is intended for a combat route",
    "proposal is intended for an exploration route",
)
