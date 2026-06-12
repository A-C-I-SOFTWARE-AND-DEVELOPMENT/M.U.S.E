"""Generate the deterministic fixture benchmark suite for the template fast path.

Why fixtures: ``$HERMES_HOME/flywheel/events.jsonl`` carried no usable
(task, output, verdict) triples in this environment, so per the ship-plan's
sanctioned fallback the corpus is built from repo fixtures instead. Every
"passed" tag is still *earned* — ``bench/corpus.py`` executes each candidate
through ``research_fabric.verifier.algorithms.score_algorithm_candidate``
rather than trusting the labels written here.

The suite is plain ``BenchmarkTaskSpec`` JSONL (the existing
``research_fabric/benchmarks`` shape) so Phase 4 can grade it with
``load_suite``/``run_suite`` unchanged. Each payload additionally embeds:

- ``candidate``      — a known-good solution (used by ``run_suite`` directly)
- ``candidate_fail`` — a known-bad solution (corpus negative examples only)

Run: ``python -m hermes_cli.jarvis_prime.bench.make_fixture_suite`` (rewrites
``bench/fixtures/algorithm_suite.jsonl`` byte-deterministically).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

FIXTURE_PATH = Path(__file__).resolve().parent / "fixtures" / "algorithm_suite.jsonl"

# Per-domain prompt framing. Same verifier (executable algorithm lane — cheap,
# hard to game) across all six REQUIRED_DOMAINS; the framing is what the
# cluster layer learns to separate.
_FRAMES = {
    "code_generation": "Write a Python function `{entry}` that {what}.",
    "code_editing": "The function `{entry}` below is buggy. Edit it so that {what}. Return the full corrected function.",
    "code_review": "Review the implementation of `{entry}` and submit a corrected version such that {what}.",
    "software_development": "Implement the repository utility `{entry}` so that {what}. Keep it dependency-free.",
    "reasoning": "Reason step by step about the problem, then implement `{entry}` so that {what}.",
    "safety": "Implement the policy check `{entry}` so that {what}. The check must fail closed.",
}

# (entry, what, good_body, bad_body, cases) per domain; bodies are the function
# body lines. Good candidates put a reasoning comment BEFORE the answer code
# (reasoning-before-answer ordering, mirrored later by the mined scaffolds).
_TASKS: dict[str, list[dict[str, Any]]] = {
    "code_generation": [
        dict(entry="sum_list", what="returns the sum of a list of integers",
             good="return sum(xs)", bad="return sum(xs) + 1",
             cases=[([[1, 2, 3]], 6), ([[0]], 0), ([[-1, 1]], 0), ([[10, 20]], 30), ([[5]], 5), ([[2, 2, 2]], 6)]),
        dict(entry="reverse_string", what="returns its string argument reversed",
             good="return xs[::-1]", bad="return xs",
             cases=[(["abc"], "cba"), ([""], ""), (["a"], "a"), (["muse"], "esum"), (["ab"], "ba"), (["xyz"], "zyx")]),
        dict(entry="count_vowels", what="returns the number of vowels (aeiou) in a lowercase string",
             good="return sum(1 for c in xs if c in 'aeiou')", bad="return sum(1 for c in xs if c in 'aeiu')",
             cases=[(["abc"], 1), (["aeiou"], 5), ([""], 0), (["xyz"], 0), (["banana"], 3), (["queue"], 4)]),
        dict(entry="max_of", what="returns the maximum element of a non-empty integer list",
             good="return max(xs)", bad="return min(xs)",
             cases=[([[1, 3, 2]], 3), ([[5]], 5), ([[-2, -1]], -1), ([[9, 9]], 9), ([[0, 7, 4]], 7), ([[3, 1]], 3)]),
        dict(entry="fib", what="returns the n-th Fibonacci number with fib(0)=0 and fib(1)=1",
             good="a, b = 0, 1\n    for _ in range(xs):\n        a, b = b, a + b\n    return a",
             bad="a, b = 1, 1\n    for _ in range(xs):\n        a, b = b, a + b\n    return a",
             cases=[([0], 0), ([1], 1), ([2], 1), ([5], 5), ([7], 13), ([10], 55)]),
    ],
    "code_editing": [
        dict(entry="double_all", what="it returns every element doubled",
             good="return [x * 2 for x in xs]", bad="return [x + 2 for x in xs]",
             cases=[([[1, 2]], [2, 4]), ([[0]], [0]), ([[-1]], [-2]), ([[3, 3]], [6, 6]), ([[]], []), ([[5]], [10])]),
        dict(entry="strip_blanks", what="it removes empty strings from the list",
             good="return [x for x in xs if x]", bad="return [x for x in xs if not x]",
             cases=[([["a", "", "b"]], ["a", "b"]), ([[""]], []), ([["x"]], ["x"]), ([[]], []), ([["", ""]], []), ([["m", "u"]], ["m", "u"])]),
        dict(entry="last_index", what="it returns the index of the last occurrence of t in xs, or -1",
             good="for i in range(len(xs) - 1, -1, -1):\n        if xs[i] == t:\n            return i\n    return -1",
             bad="for i in range(len(xs)):\n        if xs[i] == t:\n            return i\n    return -1",
             cases=[([[1, 2, 1], 1], 2), ([[1], 2], -1), ([[3, 3, 3], 3], 2), ([[], 0], -1), ([[5, 6], 6], 1), ([[7, 8, 7, 8], 8], 3)]),
        dict(entry="clamp", what="it clamps v into the inclusive range [lo, hi]",
             good="return max(lo, min(hi, v))", bad="return min(lo, max(hi, v))",
             cases=[([5, 0, 10], 5), ([-1, 0, 10], 0), ([11, 0, 10], 10), ([0, 0, 0], 0), ([7, 7, 9], 7), ([10, 0, 10], 10)]),
        dict(entry="dedupe", what="it removes duplicates while preserving first-seen order",
             good="seen = []\n    for x in xs:\n        if x not in seen:\n            seen.append(x)\n    return seen",
             bad="return sorted(set(xs))",
             cases=[([[2, 1, 2]], [2, 1]), ([[1, 1]], [1]), ([[]], []), ([[3]], [3]), ([[4, 5, 4, 5]], [4, 5]), ([[9, 8, 7]], [9, 8, 7])]),
    ],
    "code_review": [
        dict(entry="is_even", what="it returns True exactly when n is even",
             good="return n % 2 == 0", bad="return n % 2 == 1",
             cases=[([2], True), ([3], False), ([0], True), ([-2], True), ([-3], False), ([10], True)]),
        dict(entry="safe_div", what="it returns a / b, or None when b is zero",
             good="return None if b == 0 else a / b", bad="return a / b if a else None",
             cases=[([6, 3], 2.0), ([1, 0], None), ([0, 5], 0.0), ([9, 3], 3.0), ([8, 2], 4.0), ([5, 0], None)]),
        dict(entry="word_count", what="it returns the number of whitespace-separated words",
             good="return len(xs.split())", bad="return len(xs.split(' '))",
             cases=[(["a b"], 2), ([""], 0), (["one"], 1), (["a  b"], 2), (["x y z"], 3), (["  "], 0)]),
        dict(entry="all_positive", what="it returns True iff every element is > 0",
             good="return all(x > 0 for x in xs)", bad="return any(x > 0 for x in xs)",
             cases=[([[1, 2]], True), ([[0]], False), ([[]], True), ([[-1, 1]], False), ([[3]], True), ([[2, -2]], False)]),
        dict(entry="median3", what="it returns the median of three integers",
             good="return sorted([a, b, c])[1]", bad="return (a + b + c) // 3",
             cases=[([1, 2, 3], 2), ([3, 1, 2], 2), ([5, 5, 1], 5), ([0, 9, 4], 4), ([7, 7, 7], 7), ([2, 8, 5], 5)]),
    ],
    "software_development": [
        dict(entry="parse_kv", what="it parses 'k=v' comma-separated pairs into a dict of strings",
             good="out = {}\n    for part in xs.split(','):\n        if '=' in part:\n            k, v = part.split('=', 1)\n            out[k] = v\n    return out",
             bad="return dict(part.split('=') for part in xs.split(','))",
             cases=[(["a=1,b=2"], {"a": "1", "b": "2"}), ([""], {}), (["k=v"], {"k": "v"}), (["x=1,broken"], {"x": "1"}), (["a=b=c"], {"a": "b=c"}), (["m=,n=2"], {"m": "", "n": "2"})]),
        dict(entry="slug", what="it lowercases and replaces spaces with single hyphens",
             good="return '-'.join(xs.lower().split())", bad="return xs.lower().replace(' ', '-')",
             cases=[(["My File"], "my-file"), (["a  b"], "a-b"), ([""], ""), (["X"], "x"), (["Big  Gap Here"], "big-gap-here"), (["ok"], "ok")]),
        dict(entry="chunked", what="it splits a list into consecutive chunks of size n (last may be short)",
             good="return [xs[i:i + n] for i in range(0, len(xs), n)]",
             bad="return [xs[i:i + n] for i in range(len(xs))]",
             cases=[([[1, 2, 3], 2], [[1, 2], [3]]), ([[], 3], []), ([[1], 1], [[1]]), ([[1, 2, 3, 4], 2], [[1, 2], [3, 4]]), ([[1, 2], 5], [[1, 2]]), ([[1, 2, 3], 1], [[1], [2], [3]])]),
        dict(entry="env_truthy", what="it returns True for the strings '1', 'true', 'yes', 'on' (case/space-insensitive)",
             good="return xs.strip().lower() in ('1', 'true', 'yes', 'on')",
             bad="return bool(xs)",
             cases=[(["1"], True), (["true"], True), ([" YES "], True), (["0"], False), ([""], False), (["off"], False)]),
        dict(entry="merge_dicts", what="it merges two dicts with the second winning on conflicts",
             good="out = dict(a)\n    out.update(b)\n    return out",
             bad="out = dict(b)\n    out.update(a)\n    return out",
             cases=[([{"x": 1}, {"x": 2}], {"x": 2}), ([{}, {}], {}), ([{"a": 1}, {"b": 2}], {"a": 1, "b": 2}), ([{"k": 0}, {}], {"k": 0}), ([{}, {"z": 9}], {"z": 9}), ([{"p": 1, "q": 2}, {"q": 3}], {"p": 1, "q": 3})]),
    ],
    "reasoning": [
        dict(entry="min_coins", what="it returns the minimum number of coins from denominations [1, 5, 10] summing to n",
             good="count = 0\n    for d in (10, 5, 1):\n        count += n // d\n        n %= d\n    return count",
             bad="return n // 10 + n % 10",
             cases=[([17], 4), ([0], 0), ([5], 1), ([26], 4), ([9], 5), ([30], 3)]),
        dict(entry="is_palindrome", what="it returns True iff the lowercase string reads the same reversed",
             good="return xs == xs[::-1]", bad="return xs[0] == xs[-1] if xs else True",
             cases=[(["aba"], True), (["ab"], False), ([""], True), (["abba"], True), (["abca"], False), (["x"], True)]),
        dict(entry="grid_paths", what="it returns the number of monotone lattice paths in an r-by-c grid",
             good="from math import comb\n    return comb(r + c, r)",
             bad="return r * c",
             cases=[([1, 1], 2), ([2, 2], 6), ([0, 5], 1), ([3, 2], 10), ([2, 3], 10), ([1, 4], 5)]),
        dict(entry="next_odd", what="it returns n if n is odd, else n + 1",
             good="return n if n % 2 == 1 else n + 1", bad="return n + 1",
             cases=[([3], 3), ([4], 5), ([0], 1), ([-3], -3), ([7], 7), ([10], 11)]),
        dict(entry="digit_sum", what="it returns the sum of decimal digits of a non-negative integer",
             good="return sum(int(c) for c in str(n))", bad="return n % 9",
             cases=[([123], 6), ([0], 0), ([999], 27), ([10], 1), ([55], 10), ([406], 10)]),
    ],
    "safety": [
        dict(entry="gate_action", what="it returns 'deny' for actions in the irreversible set ('deploy', 'spend', 'publish') and 'allow' otherwise",
             good="return 'deny' if action in ('deploy', 'spend', 'publish') else 'allow'",
             bad="return 'allow'",
             cases=[(["deploy"], "deny"), (["read"], "allow"), (["spend"], "deny"), (["list"], "allow"), (["publish"], "deny"), (["plan"], "allow")]),
        dict(entry="redact_secret", what="it replaces any token starting with 'sk-' with '[REDACTED]' in a word list",
             good="return ['[REDACTED]' if w.startswith('sk-') else w for w in xs]",
             bad="return xs",
             cases=[([["sk-abc", "ok"]], ["[REDACTED]", "ok"]), ([[]], []), ([["plain"]], ["plain"]), ([["sk-1", "sk-2"]], ["[REDACTED]", "[REDACTED]"]), ([["a"]], ["a"]), ([["sk-x"]], ["[REDACTED]"])]),
        dict(entry="needs_owner_gate", what="it returns True iff the request mentions any of 'merge to main', 'oauth', 'credential'",
             good="low = xs.lower()\n    return any(t in low for t in ('merge to main', 'oauth', 'credential'))",
             bad="return False",
             cases=[(["please merge to main"], True), (["read docs"], False), (["rotate CREDENTIAL"], True), (["OAuth grant"], True), (["run tests"], False), (["fix typo"], False)]),
        dict(entry="cap_confidence", what="it caps a confidence float at 0.45 (community-trust ceiling) and floors it at 0.0",
             good="return max(0.0, min(0.45, c))", bad="return c",
             cases=[([0.9], 0.45), ([0.2], 0.2), ([-0.1], 0.0), ([0.45], 0.45), ([1.0], 0.45), ([0.0], 0.0)]),
        dict(entry="fail_closed", what="it returns 'deny' for unknown verdict strings, passing through only 'allow' and 'deny'",
             good="return verdict if verdict in ('allow', 'deny') else 'deny'",
             bad="return verdict if verdict in ('allow', 'deny') else 'allow'",
             cases=[(["allow"], "allow"), (["deny"], "deny"), ([""], "deny"), (["maybe"], "deny"), (["ALLOW"], "deny"), (["yes"], "deny")]),
    ],
}

# Reasoning comment goes BEFORE the answer code in every good candidate —
# the same reasoning-first ordering the mined scaffolds must preserve.
_GOOD_TEMPLATE = "# Reasoning: {what} — verified against the public cases first.\ndef {entry}({params}):\n    {body}\n"
_BAD_TEMPLATE = "def {entry}({params}):\n    {body}\n"


def _params_for(cases: list[tuple[list[Any], Any]]) -> str:
    n = len(cases[0][0])
    names = ["xs", "t", "u"] if n <= 3 else [f"a{i}" for i in range(n)]
    special = {1: ["xs"], 2: ["xs", "t"], 3: ["a", "b", "c"]}
    return ", ".join(special.get(n, names)[:n])


# Tasks whose two/three params have semantic names baked into the bodies.
_PARAM_OVERRIDES = {
    "fib": "xs", "min_coins": "n", "is_even": "n", "next_odd": "n", "digit_sum": "n",
    "safe_div": "a, b", "clamp": "v, lo, hi", "median3": "a, b, c",
    "grid_paths": "r, c", "merge_dicts": "a, b", "chunked": "xs, n",
    "last_index": "xs, t", "cap_confidence": "c", "fail_closed": "verdict",
    "gate_action": "action",
}


def build_specs() -> list[dict[str, Any]]:
    specs: list[dict[str, Any]] = []
    for domain, tasks in _TASKS.items():
        frame = _FRAMES[domain]
        for i, t in enumerate(tasks):
            cases = t["cases"]
            params = _PARAM_OVERRIDES.get(t["entry"]) or _params_for(cases)
            good = _GOOD_TEMPLATE.format(what=t["what"], entry=t["entry"], params=params, body=t["good"])
            bad = _BAD_TEMPLATE.format(entry=t["entry"], params=params, body=t["bad"])
            public = [{"args": c[0], "expected": c[1]} for c in cases[:3]]
            holdout = [{"args": c[0], "expected": c[1]} for c in cases[3:]]
            specs.append(
                {
                    "task_id": f"tpl-fixture-{domain}-{i:02d}-{t['entry']}",
                    "domain": domain,
                    "kind": "algorithm",
                    "payload": {
                        "entrypoint": t["entry"],
                        "prompt": frame.format(entry=t["entry"], what=t["what"]),
                        "public_cases": public,
                        "holdout_cases": holdout,
                        "candidate": good,
                        "candidate_fail": bad,
                    },
                }
            )
    return specs


def write_suite(path: Path = FIXTURE_PATH) -> Path:
    specs = build_specs()
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [json.dumps(s, sort_keys=True, ensure_ascii=False) for s in specs]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


if __name__ == "__main__":
    out = write_suite()
    print(f"wrote {out} ({len(build_specs())} specs)")
