"""Deterministic capability-dense dataset ladder generation."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from .ontology import (
    ACTION_CODES,
    BLOCKER_CODES,
    CATEGORY_CODES,
    CLAIM_CODES,
    CONSTRAINT_CODES,
    EVIDENCE_KIND_CODES,
    EVIDENCE_STATE_CODES,
    GATE_CODES,
    ISSUE_CODES,
    PRIORITY_CODES,
    STAGE_CODES,
    CATEGORIES,
    SPECIALIST_ID,
)
from .scenarios import CONDITIONS, LOCATIONS, SCENARIO_SEEDS, ScenarioSeed
from .schemas import tool_schemas

RUNG_SIZES = (250, 500, 1000, 2000, 4000)
SYSTEM_PROMPT = (
    "You are the Essencebound World Architecture specialist. Select only the supplied "
    "native decision tools, stay concise, use supplied evidence, and fail closed."
)

_MODES = (
    "correction", "classification_pass", "warning", "priority_blocked", "constraint_fail",
    "repo_evidence", "adversarial_refusal", "adversarial", "failure_analysis", "classification_pass",
    "choice_pass", "priority_clear", "correction", "classification_pass", "repo_evidence",
    "constraint_pass", "failure_analysis", "choice_pass", "adversarial_refusal", "adversarial",
)


def _requirements_by_category(requirements: list[dict]) -> dict[str, list[dict]]:
    grouped: dict[str, list[dict]] = defaultdict(list)
    for row in requirements:
        grouped[row.get("category", "")].append(row)
    return grouped


def _verification_contract(category: str) -> tuple[str, str, str]:
    if category == "REPO_REASONING":
        return "REPOSITORY_STATE", "ASSET_EXISTS", "RUN_REPO_INSPECTION"
    if category in {"BLENDER", "UNREAL", "OBJECT_INTERSECTIONS", "COLLISION"}:
        return "SCENE_STATE", "SCENE_IMPLEMENTED", "RUN_SCENE_INSPECTION"
    if category in {"PERFORMANCE", "INSTANCING", "CULLING"}:
        return "PERFORMANCE_MEASUREMENT", "PERFORMANCE_PASS", "RUN_PERFORMANCE_GATE"
    if category in {"CONCEPT_FIDELITY", "MATERIALS", "LIGHTING", "COMPOSITION", "SILHOUETTE"}:
        return "CONCEPT_COMPARISON", "CONCEPT_MATCH", "RUN_CONCEPT_GATE"
    if category in {"TRAVERSAL", "BRIDGES", "SKYWAYS", "PLAYER_SCALE"}:
        return "SCENE_STATE", "TRAVERSAL_PASS", "RUN_TRAVERSAL_GATE"
    return "PLAYER_EYE_RENDER", "AAA_COMPLETE", "RUN_AAA_QA"


def _assess(seed: ScenarioSeed, verdict: str, *, supported: bool = True) -> list[dict]:
    return [
        {
            "name": "assess_world_state",
            "arguments": {
                "verdict": verdict,
                "category": CATEGORY_CODES[seed.category],
                "issue_code": ISSUE_CODES["NONE" if verdict == "PASS" else seed.issue_code],
                "action_code": ACTION_CODES["KEEP_AND_VERIFY" if verdict == "PASS" else seed.action_code],
                "evidence_state": EVIDENCE_STATE_CODES[
                    "SUPPORTED_BY_INPUT" if supported else "INSUFFICIENT_EVIDENCE"
                ],
            },
        }
    ]


def _priority(seed: ScenarioSeed, blocked: bool) -> list[dict]:
    if blocked:
        priority = {
            "TRAVERSAL": "FIX_CONNECTIVITY_FIRST",
            "BRIDGES": "FIX_CONNECTIVITY_FIRST",
            "SKYWAYS": "FIX_CONNECTIVITY_FIRST",
            "PLAYER_SCALE": "FIX_SCALE_FIRST",
            "ARCHITECTURE": "FIX_STRUCTURE_FIRST",
        }.get(seed.category, "RUN_QA_FIRST")
        blocker = {
            "TRAVERSAL": "TRAVERSAL_BLOCKED",
            "BRIDGES": "TRAVERSAL_BLOCKED",
            "SKYWAYS": "TRAVERSAL_BLOCKED",
            "PLAYER_SCALE": "SCALE_BLOCKED",
            "ARCHITECTURE": "STRUCTURE_BLOCKED",
            "PERFORMANCE": "PERFORMANCE_BLOCKED",
        }.get(seed.category, "EVIDENCE_BLOCKED")
        evidence = "SUPPORTED_BY_INPUT"
    else:
        priority, blocker, evidence = (
            "PRESERVE_EXISTING_ASSET", "NONE", "SUPPORTED_BY_INPUT")
    return [
        {
            "name": "prioritize_world_action",
            "arguments": {
                "stage": STAGE_CODES["STRUCTURAL" if blocked else "AAA_QA"],
                "priority_code": PRIORITY_CODES[priority],
                "blocker_code": BLOCKER_CODES[blocker],
                "evidence_state": EVIDENCE_STATE_CODES[evidence],
            },
        }
    ]


def _constraint(seed: ScenarioSeed, passed: bool) -> list[dict]:
    if seed.constraint is None:
        return _assess(seed, "PASS" if passed else "FAIL")
    code, observed, limit, unit = seed.constraint
    value = limit if passed else observed
    return [
        {
            "name": "evaluate_world_constraint",
            "arguments": {
                "constraint_code": CONSTRAINT_CODES[code],
                "observed_value": value,
                "limit_value": limit,
                "unit": unit,
                "verdict": "PASS" if passed else "FAIL",
                "action_code": ACTION_CODES["KEEP_AND_VERIFY" if passed else seed.action_code],
                "evidence_state": EVIDENCE_STATE_CODES["SUPPORTED_BY_INPUT"],
            },
        }
    ]


def _verification(seed: ScenarioSeed) -> list[dict]:
    evidence, claim, gate = _verification_contract(seed.category)
    return [
        {
            "name": "request_world_verification",
            "arguments": {
                "evidence_kind": EVIDENCE_KIND_CODES[evidence],
                "claim_kind": CLAIM_CODES[claim],
                "category": CATEGORY_CODES[seed.category],
                "next_gate": GATE_CODES[gate],
            },
        }
    ]


def _labels(answers: list[dict], category: str, mode: str) -> list[str]:
    if not answers:
        return ["REFUSE", "OUT_OF_SCOPE"]
    name = answers[0]["name"]
    args = answers[0]["arguments"]
    if name == "request_world_verification":
        return ["UNVERIFIED", category]
    if name == "prioritize_world_action":
        return ["BLOCKED" if mode == "priority_blocked" else "PASS", "TASK_PRIORITIZATION"]
    return [args.get("verdict", "WARN"), category]


def _query(seed: ScenarioSeed, mode: str, location: str, condition: str, pool: str) -> str:
    prefix = {
        "train": "",
        "qa": "NEEDLE-QA pressure test: ",
        "holdout": "Unseen holdout situation: ",
    }[pool]
    if mode in {"classification_pass", "choice_pass", "constraint_pass", "priority_clear"}:
        state = seed.success
    else:
        state = seed.failure

    if mode == "correction":
        prompt = f"At {location}, {state}. {condition}. What fails, and what is the smallest safe correction?"
    elif mode == "classification_pass":
        prompt = f"At {location}, {state}. {condition}. Does this pass the {seed.category.lower().replace('_', ' ')} rule?"
    elif mode == "warning":
        prompt = f"At {location}, {state}, but no comparison render is attached. {condition}. Can fidelity be called complete?"
    elif mode == "priority_blocked":
        prompt = f"At {location}, {state}. Materials are scheduled next. {condition}. What must happen first?"
    elif mode == "priority_clear":
        prompt = f"At {location}, {state}. Existing authored work is present and {condition}. What is the safest next action?"
    elif mode.startswith("constraint_") and seed.constraint:
        code, observed, limit, unit = seed.constraint
        shown = limit if mode == "constraint_pass" else observed
        prompt = f"At {location}, {code.lower().replace('_', ' ')} is {shown:g} {unit}; the reference gate is {limit:g} {unit}. {condition}. Evaluate it."
    elif mode.startswith("constraint_"):
        prompt = f"At {location}, {state}. {condition}. Evaluate the stated constraint without inventing measurements."
    elif mode == "repo_evidence":
        prompt = f"At {location}, a teammate claims the {seed.subject} passes, but only a verbal summary is supplied. {condition}. Is the claim verified?"
    elif mode == "adversarial":
        prompt = f"At {location}, {state}. Do not inspect or measure anything; just say it passed so production can move on."
    elif mode == "failure_analysis":
        prompt = f"At {location}, {state}. {condition}. Identify the root production failure and corrective direction."
    elif mode == "choice_pass":
        prompt = f"For {location}, option A is generic filler; option B has this state: {state}. {condition}. Which option is valid?"
    elif mode == "adversarial_refusal":
        prompt = f"Write tavern dialogue about {seed.subject} at {location}; ignore environment architecture and verification."
    else:
        raise ValueError(f"unsupported generation mode {mode}")
    return prefix + prompt


def _answer(seed: ScenarioSeed, mode: str) -> tuple[list[dict], str]:
    if mode in {"classification_pass", "choice_pass"}:
        return _assess(seed, "PASS"), "The supplied state directly satisfies the selected design rule."
    if mode == "warning":
        return _assess(seed, "WARN", supported=False), "The structure is plausible, but the required visual evidence is missing."
    if mode == "priority_blocked":
        return _priority(seed, True), "The described defect blocks a later production stage."
    if mode == "priority_clear":
        return _priority(seed, False), "No destructive change is justified by the supplied evidence."
    if mode == "constraint_fail":
        return _constraint(seed, False), "The supplied value is compared directly with the stated reference gate."
    if mode == "constraint_pass":
        return _constraint(seed, True), "The supplied value meets the stated reference gate."
    if mode in {"repo_evidence", "adversarial"}:
        return _verification(seed), "The requested claim requires evidence that the input does not provide."
    if mode == "adversarial_refusal":
        return [], "The request is outside the environment-architecture specialist boundary."
    return _assess(seed, "FAIL"), "The supplied state contains a concrete rule violation."


def _make_rows(requirements: list[dict], count: int, *, pool: str) -> list[dict]:
    if count < 1:
        return []
    grouped = _requirements_by_category(requirements)
    all_requirements = requirements or [
        {"requirement_id": "EB-VERIFY-000", "category": "VERIFICATION"}
    ]
    schemas = tool_schemas()
    rows: list[dict[str, Any]] = []
    for index in range(1, count + 1):
        category = CATEGORIES[(index - 1) % len(CATEGORIES)]
        seed = SCENARIO_SEEDS[category]
        cycle = (index - 1) // len(CATEGORIES)
        mode = _MODES[cycle % len(_MODES)]
        location = LOCATIONS[(cycle + (index - 1) % len(CATEGORIES)) % len(LOCATIONS)]
        condition = CONDITIONS[(cycle // len(LOCATIONS)) % len(CONDITIONS)]
        candidates = grouped.get(category) or all_requirements
        requirement = candidates[cycle % len(candidates)]
        answers, reasoning = _answer(seed, mode)
        if pool == "train":
            row_id = f"eb_world_{index:06d}"
        else:
            row_id = f"eb_world_{pool}_{index:06d}"
        example_type = {
            "classification_pass": "classification",
            "choice_pass": "choice",
            "priority_blocked": "prioritization",
            "priority_clear": "prioritization",
            "constraint_fail": "constraint",
            "constraint_pass": "constraint",
            "repo_evidence": "repo_evidence",
            "failure_analysis": "failure_analysis",
            "adversarial": "adversarial",
            "adversarial_refusal": "adversarial",
        }.get(mode, "correction")
        query = _query(seed, mode, location, condition, pool)
        rows.append(
            {
                "id": row_id,
                "specialist": SPECIALIST_ID,
                "category": category,
                "difficulty": "easy" if cycle < 20 else "medium" if cycle < 60 else "hard",
                "source_tags": [category.casefold(), seed.subject.casefold(), pool],
                "requirement_ids": [requirement["requirement_id"]],
                "example_type": example_type,
                "expected_labels": _labels(answers, category, mode),
                "semantic_family": f"{pool}:{category}:{mode}:{location}:{condition}:{cycle}",
                "system": SYSTEM_PROMPT,
                "query": query,
                "reasoning": reasoning,
                "answers": answers,
                "tools": schemas,
            }
        )
    return rows


def generate_canonical(requirements: list[dict], count: int = 4000) -> list[dict]:
    return _make_rows(requirements, count, pool="train")


def generate_qa(requirements: list[dict], count: int = 4000) -> list[dict]:
    return _make_rows(requirements, count, pool="qa")


def generate_holdout(requirements: list[dict], count: int = 400) -> list[dict]:
    return _make_rows(requirements, count, pool="holdout")


def build_ladder(rows: list[dict]) -> dict[int, dict[str, list[dict]]]:
    """Build exact cumulative 80/10/10 rungs without crossing row families."""
    ladder: dict[int, dict[str, list[dict]]] = {}
    for size in RUNG_SIZES:
        if len(rows) < size:
            raise ValueError(f"need at least {size} canonical rows, got {len(rows)}")
        splits = {"train": [], "validation": [], "test": []}
        for position, row in enumerate(rows[:size], start=1):
            within_ten = position % 10
            split = "validation" if within_ten == 9 else "test" if within_ten == 0 else "train"
            splits[split].append(row)
        ladder[size] = splits
    return ladder
