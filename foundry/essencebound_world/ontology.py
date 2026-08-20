"""Bounded vocabulary for the Essencebound World Architect specialist."""

from __future__ import annotations

from copy import deepcopy

SPECIALIST_ID = "NEEDLE-EB-WORLD-ARCHITECT"
REGISTRY_ID = "needle-eb-world-architect"

CATEGORIES = (
    "CONCEPT_FIDELITY",
    "MACRO_LAYOUT",
    "TRAVERSAL",
    "BRIDGES",
    "SKYWAYS",
    "PLAYER_SCALE",
    "ARCHITECTURE",
    "ARCHITECTURAL_PURPOSE",
    "FLOATING_ISLAND_GEOLOGY",
    "LANDMASS",
    "WILDERNESS",
    "ROADS",
    "SETTLEMENTS",
    "MARKETS",
    "SHOPS",
    "INTERIORS",
    "ENVIRONMENTAL_STORYTELLING",
    "MATERIALS",
    "LIGHTING",
    "MAGIC",
    "ESSENCE_INFRASTRUCTURE",
    "CRYSTALS",
    "COMPOSITION",
    "SILHOUETTE",
    "PERFORMANCE",
    "INSTANCING",
    "CULLING",
    "DESTRUCTION",
    "INTERACTION",
    "COLLISION",
    "OBJECT_INTERSECTIONS",
    "BLENDER",
    "UNREAL",
    "PYTHON_GENERATION",
    "REPO_REASONING",
    "VERIFICATION",
    "FAILURE_DETECTION",
    "QUALITY_GATES",
    "COMPLETION_STATUS",
    "TASK_PRIORITIZATION",
)

VERDICTS = ("PASS", "FAIL", "WARN", "UNVERIFIED", "BLOCKED")
EVIDENCE_STATES = (
    "SUPPORTED_BY_INPUT",
    "INSUFFICIENT_EVIDENCE",
    "REQUIRES_MEASUREMENT",
    "REQUIRES_REPO_INSPECTION",
    "REQUIRES_SCENE_INSPECTION",
)
STAGES = (
    "AUDIT",
    "STRUCTURAL",
    "LAYOUT",
    "CONNECTED",
    "ARCHITECTURE",
    "MATERIAL",
    "LIGHTING",
    "POLISH",
    "AAA_QA",
)

ISSUE_TEXT = {
    "NONE": "The supplied state satisfies the stated rule",
    "GENERIC_FANTASY_LANGUAGE": "The design reads as generic fantasy instead of Essencebound",
    "MISSING_LANDING": "The route terminates without a traversable landing",
    "UNREACHABLE_DESTINATION": "The destination has no valid player route",
    "UNSUPPORTED_STRUCTURE": "The structure lacks believable physical or Essence support",
    "HUMAN_SCALE_VIOLATION": "The architecture is not human-scaled",
    "EXCESSIVE_EMISSIVE": "Emissive treatment overwhelms the intended visual hierarchy",
    "MISSING_POWER_CAUSALITY": "The Essence effect has no source, conduit, or consumer logic",
    "INVALID_BRIDGE_GRADE": "The bridge grade exceeds the intended traversal target",
    "INVALID_PLAYER_CLEARANCE": "The route does not provide safe player clearance",
    "BROKEN_ROAD_NETWORK": "The road does not connect meaningful destinations",
    "DUPLICATE_SETTLEMENT": "The settlement repeats another location without regional identity",
    "MISSING_INTERIOR_LOGIC": "The interior lacks a valid entrance, circulation, or function",
    "UNJUSTIFIED_DESTRUCTION": "Destruction would remove critical traversal or structure",
    "MISSING_INTERACTION_FEEDBACK": "The interaction lacks a readable state or response",
    "COLLISION_BLOCKER": "Collision prevents the intended route or interaction",
    "ACCIDENTAL_INTERSECTION": "Geometry intersects without structural or artistic justification",
    "INSTANCE_BUDGET_EXCEEDED": "The proposed instance count exceeds the island gate",
    "UNPARTITIONED_INSTANCING": "Instances use oversized bounds instead of localized cells",
    "CULLING_NOT_MEASURED": "Culling effectiveness has not been demonstrated",
    "FOG_HIDES_FAILURE": "Fog is masking unresolved scene quality problems",
    "MISSING_CONCEPT_COMPARISON": "No comparison against the authoritative concept sheets is available",
    "FALSE_COMPLETION_CLAIM": "The claimed completion state is unsupported",
    "WRONG_STAGE_ORDER": "Later polish is proposed before a blocking earlier gate",
    "MISSING_REPO_EVIDENCE": "The repository claim is not supported by inspected files",
    "MISSING_SCENE_EVIDENCE": "The scene claim is not supported by scene inspection",
    "MISSING_MEASUREMENT": "The performance claim is not supported by measurement",
}

ACTION_TEXT = {
    "KEEP_AND_VERIFY": "Preserve it and run the matching verification gate",
    "ADD_VALID_LANDING": "Add stairs, a ramp, or corrected elevation, then rerun traversal and collision checks",
    "CREATE_REACHABLE_ROUTE": "Create and validate a primary route before downstream polish",
    "ADD_STRUCTURAL_SUPPORT": "Seat it on foundations or show explicit Essence suspension technology",
    "RESTORE_HUMAN_SCALE": "Restore human-scaled architecture and expand landscape spacing instead",
    "RESTRAIN_EMISSIVE": "Reserve cyan light for high-value Essence infrastructure",
    "CONNECT_ESSENCE_NETWORK": "Show the source, conduit, channel, and consuming system",
    "REDUCE_GRADE": "Regrade the span or add switchbacks, lifts, or landings",
    "RESTORE_CLEARANCE": "Adjust width, railings, and obstacles to restore intended clearance",
    "CONNECT_ROAD_DESTINATIONS": "Connect the road to real destinations and remove ornamental dead ends",
    "DIFFERENTIATE_SETTLEMENT": "Give the settlement a distinct function, layout, materials, and story",
    "FIX_INTERIOR_CIRCULATION": "Add a valid entrance, circulation loop, and functional spaces",
    "EXEMPT_CRITICAL_STRUCTURE": "Keep traversal-critical geometry intact or provide a verified replacement",
    "ADD_INTERACTION_STATE": "Add readable affordance, feedback, and active/inactive states",
    "REPAIR_COLLISION": "Correct collision and rerun player-route validation",
    "REPAIR_INTERSECTION": "Separate the meshes or redesign the joint as intentional support",
    "REDUCE_INSTANCE_DENSITY": "Reduce density, reuse clustered assets, and remeasure scene counts",
    "PARTITION_BY_CELL": "Batch by localized kilometer-scale cells with useful bounds",
    "MEASURE_CULLING": "Measure culling and bounds behavior under the defined QA configuration",
    "REMOVE_FOG_CRUTCH": "Evaluate the scene in clear QA views and fix the exposed defects",
    "COMPARE_CONCEPT_SHEETS": "Capture player-height views and compare them with the source sheets",
    "WITHHOLD_COMPLETION": "Keep the state unverified until every required gate has evidence",
    "RETURN_TO_BLOCKING_STAGE": "Complete the earliest blocking stage before later polish",
    "INSPECT_REPOSITORY": "Inspect the relevant files and manifests before relying on the claim",
    "INSPECT_SCENE": "Inspect the Blender or Unreal scene before relying on the claim",
    "RUN_MEASUREMENT": "Run the defined performance measurement before claiming success",
}

PRIORITY_TEXT = {
    "FIX_CONNECTIVITY_FIRST": "Establish and validate connectivity first",
    "FIX_STRUCTURE_FIRST": "Resolve structural support first",
    "FIX_SCALE_FIRST": "Correct player and architectural scale first",
    "RUN_QA_FIRST": "Run the named QA gate before further production work",
    "PRESERVE_EXISTING_ASSET": "Preserve the existing asset while evidence is gathered",
}

BLOCKER_TEXT = {
    "NONE": "no blocking defect",
    "TRAVERSAL_BLOCKED": "unresolved traversal",
    "STRUCTURE_BLOCKED": "unresolved structural logic",
    "SCALE_BLOCKED": "invalid player or world scale",
    "EVIDENCE_BLOCKED": "missing verification evidence",
    "PERFORMANCE_BLOCKED": "unmeasured or failed performance",
}

CONSTRAINTS = (
    "PLAYER_HEIGHT_CM",
    "WALKWAY_WIDTH_CM",
    "PRIMARY_PATH_WIDTH_CM",
    "COMBAT_ROUTE_WIDTH_CM",
    "BRIDGE_WIDTH_CM",
    "DOOR_WIDTH_CM",
    "RAILING_HEIGHT_CM",
    "STAIR_RISE_CM",
    "BRIDGE_GRADE_DEG",
    "ISLAND_RADIUS_UU",
    "ISLAND_INSTANCES",
    "VRAM_GB",
    "FRAME_TIME_REGRESSION_PERCENT",
)

EVIDENCE_TEXT = {
    "REPOSITORY_STATE": "repository inspection",
    "SCENE_STATE": "scene inspection",
    "PERFORMANCE_MEASUREMENT": "an actual performance measurement",
    "CONCEPT_COMPARISON": "concept-sheet comparison",
    "PLAYER_EYE_RENDER": "player-height renders",
    "TEST_OUTPUT": "actual verifier output",
}

CLAIM_TEXT = {
    "ASSET_EXISTS": "Asset existence",
    "SCENE_IMPLEMENTED": "Scene implementation",
    "PERFORMANCE_PASS": "Performance success",
    "AAA_COMPLETE": "AAA completion",
    "TRAVERSAL_PASS": "Traversal success",
    "CONCEPT_MATCH": "Concept fidelity",
}

GATE_TEXT = {
    "RUN_REPO_INSPECTION": "Inspect the repository and manifest",
    "RUN_SCENE_INSPECTION": "Inspect the authored scene",
    "RUN_PERFORMANCE_GATE": "Run the defined performance gate",
    "RUN_CONCEPT_GATE": "Compare player-height renders against the concept sheets",
    "RUN_TRAVERSAL_GATE": "Run traversal, collision, and landing validation",
    "RUN_AAA_QA": "Run the full visual, gameplay, collision, and performance QA suite",
}


def _compact_codes(values, prefix: str, width: int = 2) -> dict[str, str]:
    return {value: f"{prefix}{index:0{width}d}" for index, value in enumerate(values)}


CATEGORY_CODES = _compact_codes(CATEGORIES, "C")
EVIDENCE_STATE_CODES = _compact_codes(EVIDENCE_STATES, "E", 1)
STAGE_CODES = _compact_codes(STAGES, "S", 1)
ISSUE_CODES = _compact_codes(tuple(ISSUE_TEXT), "I")
ACTION_CODES = _compact_codes(tuple(ACTION_TEXT), "A")
PRIORITY_CODES = _compact_codes(tuple(PRIORITY_TEXT), "P", 1)
BLOCKER_CODES = _compact_codes(tuple(BLOCKER_TEXT), "B", 1)
CONSTRAINT_CODES = _compact_codes(CONSTRAINTS, "K")
EVIDENCE_KIND_CODES = _compact_codes(tuple(EVIDENCE_TEXT), "D", 1)
CLAIM_CODES = _compact_codes(tuple(CLAIM_TEXT), "M", 1)
GATE_CODES = _compact_codes(tuple(GATE_TEXT), "G", 1)


def ontology_payload() -> dict:
    """Return a serialization-safe copy of the specialist vocabulary."""
    return deepcopy(
        {
            "specialist": SPECIALIST_ID,
            "categories": list(CATEGORIES),
            "verdicts": list(VERDICTS),
            "evidence_states": list(EVIDENCE_STATES),
            "stages": list(STAGES),
            "issue_codes": list(ISSUE_TEXT),
            "action_codes": list(ACTION_TEXT),
            "priority_codes": list(PRIORITY_TEXT),
            "blocker_codes": list(BLOCKER_TEXT),
            "constraint_codes": list(CONSTRAINTS),
            "evidence_kinds": list(EVIDENCE_TEXT),
            "claim_kinds": list(CLAIM_TEXT),
            "next_gates": list(GATE_TEXT),
            "category_codes": CATEGORY_CODES,
            "evidence_state_codes": EVIDENCE_STATE_CODES,
            "stage_codes": STAGE_CODES,
            "issue_code_map": ISSUE_CODES,
            "action_code_map": ACTION_CODES,
            "priority_code_map": PRIORITY_CODES,
            "blocker_code_map": BLOCKER_CODES,
            "constraint_code_map": CONSTRAINT_CODES,
            "evidence_kind_codes": EVIDENCE_KIND_CODES,
            "claim_codes": CLAIM_CODES,
            "gate_codes": GATE_CODES,
            "rendering": {
                "issues": ISSUE_TEXT,
                "actions": ACTION_TEXT,
                "priorities": PRIORITY_TEXT,
                "blockers": BLOCKER_TEXT,
                "evidence": EVIDENCE_TEXT,
                "claims": CLAIM_TEXT,
                "gates": GATE_TEXT,
            },
        }
    )
