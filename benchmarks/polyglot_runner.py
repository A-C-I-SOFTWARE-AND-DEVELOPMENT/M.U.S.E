#!/usr/bin/env python3
"""
Aider Polyglot Benchmark Runner with Hermes Trajectory Format

A runner that uses Hermes-Agent's built-in execution environments
(local, docker, modal) to evaluate code-editing skills across many
programming languages, inspired by the Aider Polyglot benchmark.

Each task presents the agent with a broken/incomplete source file plus a
failing test.  The agent must inspect the failing test output, edit the
source file, and re-run the test until it passes.

Features:
- Uses Hermes-Agent's Docker, Modal, or Local environments for command execution
- Outputs trajectories in Hermes format (from/value pairs with <tool_call>/<tool_response> XML)
- Compatible with the trajectory compression pipeline
- Defines 10 inline sample tasks across 5 languages (Python, JavaScript,
  Rust, Go, C++) so the runner is self-contained and runnable without
  external datasets
- Scores 1 if the test passes after the agent's edit, else 0
- Writes per-task results to results.jsonl and prints per-language accuracy

Usage:
    # Run all Python tasks with local env
    python -m benchmarks.polyglot_runner --language python --limit 5 --model kimi-k3

    # Run all languages
    python -m benchmarks.polyglot_runner --limit 10 --model kimi-k3

    # Run with Docker
    python -m benchmarks.polyglot_runner --env docker --language javascript --limit 5
"""

import json
import logging
import os
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional, Literal

import fire
from dotenv import load_dotenv
from agent.tool_dispatch_helpers import make_tool_result_message

# Load environment variables
load_dotenv()


def _effective_temperature_for_model(
    model: str,
    base_url: Optional[str] = None,
) -> Optional[float]:
    """Return a fixed temperature for models with strict sampling contracts.

    Returns ``None`` when the model manages temperature server-side (Kimi);
    callers must omit the ``temperature`` kwarg entirely in that case.
    """
    try:
        from agent.auxiliary_client import _fixed_temperature_for_model, OMIT_TEMPERATURE
    except Exception:
        return None
    result = _fixed_temperature_for_model(model, base_url)
    if result is OMIT_TEMPERATURE:
        return None  # caller must omit temperature
    return result


# ============================================================================
# Inline Polyglot Sample Tasks
# ============================================================================
# Each task: {language, broken_code, test_code, instruction, source_filename,
# test_filename, test_command, workdir}
# 10 tasks across 5 languages (Python, JavaScript, Rust, Go, C++).
# Tasks are intentionally short, self-contained, and solvable in 1-3 edits.

POLYGLOT_TASKS: List[Dict[str, Any]] = [
    # ------------------------------------------------------------------
    # Python (2 tasks)
    # ------------------------------------------------------------------
    {
        "id": "py-fizzbuzz",
        "language": "python",
        "instruction": (
            "The file solution.py contains a broken `fizzbuzz` function. "
            "It should return 'Fizz' for multiples of 3, 'Buzz' for multiples of 5, "
            "'FizzBuzz' for multiples of both, and the number as a string otherwise. "
            "Read the failing test in test_solution.py, fix solution.py so the test passes, "
            "then run `python -m pytest test_solution.py -v` and confirm it is green."
        ),
        "source_filename": "solution.py",
        "test_filename": "test_solution.py",
        "workdir": "py_fizzbuzz",
        "broken_code": (
            "def fizzbuzz(n):\n"
            "    # BUG: returns the wrong string for multiples of 15\n"
            "    if n % 3 == 0:\n"
            "        return 'Fizz'\n"
            "    if n % 5 == 0:\n"
            "        return 'Buzz'\n"
            "    return str(n)\n"
        ),
        "test_code": (
            "from solution import fizzbuzz\n"
            "\n"
            "def test_fizzbuzz_multiples_of_3():\n"
            "    assert fizzbuzz(3) == 'Fizz'\n"
            "    assert fizzbuzz(9) == 'Fizz'\n"
            "\n"
            "def test_fizzbuzz_multiples_of_5():\n"
            "    assert fizzbuzz(5) == 'Buzz'\n"
            "    assert fizzbuzz(20) == 'Buzz'\n"
            "\n"
            "def test_fizzbuzz_multiples_of_15():\n"
            "    assert fizzbuzz(15) == 'FizzBuzz'\n"
            "    assert fizzbuzz(30) == 'FizzBuzz'\n"
            "\n"
            "def test_fizzbuzz_other_numbers():\n"
            "    assert fizzbuzz(1) == '1'\n"
            "    assert fizzbuzz(7) == '7'\n"
        ),
        "test_command": "python -m pytest test_solution.py -v",
    },
    {
        "id": "py-reverse",
        "language": "python",
        "instruction": (
            "solution.py should implement `reverse_words(s)` that returns the input "
            "string with the order of whitespace-separated words reversed, but the "
            "current implementation is broken.  Read the failing tests in test_solution.py, "
            "fix solution.py, and confirm `python -m pytest test_solution.py -v` passes."
        ),
        "source_filename": "solution.py",
        "test_filename": "test_solution.py",
        "workdir": "py_reverse",
        "broken_code": (
            "def reverse_words(s):\n"
            "    # BUG: returns the original string instead of reversing word order\n"
            "    return s\n"
        ),
        "test_code": (
            "from solution import reverse_words\n"
            "\n"
            "def test_reverse_simple():\n"
            "    assert reverse_words('hello world') == 'world hello'\n"
            "\n"
            "def test_reverse_multiple():\n"
            "    assert reverse_words('the quick brown fox') == 'fox brown quick the'\n"
            "\n"
            "def test_reverse_single_word():\n"
            "    assert reverse_words('hello') == 'hello'\n"
            "\n"
            "def test_reverse_empty():\n"
            "    assert reverse_words('') == ''\n"
        ),
        "test_command": "python -m pytest test_solution.py -v",
    },
    # ------------------------------------------------------------------
    # JavaScript (2 tasks)
    # ------------------------------------------------------------------
    {
        "id": "js-is-palindrome",
        "language": "javascript",
        "instruction": (
            "solution.js exports an `isPalindrome(str)` function that should return "
            "true when the input string reads the same forwards and backwards, ignoring "
            "case and non-alphanumeric characters.  The current implementation is broken. "
            "Run the failing test with `npx --yes jest test_solution.js` (or `node test_solution.js` "
            "if jest is unavailable), then fix solution.js until the test passes."
        ),
        "source_filename": "solution.js",
        "test_filename": "test_solution.js",
        "workdir": "js_palindrome",
        "broken_code": (
            "function isPalindrome(str) {\n"
            "  // BUG: does not normalize case or strip non-alphanumerics\n"
            "  return str === str.split('').reverse().join('');\n"
            "}\n"
            "\n"
            "module.exports = { isPalindrome };\n"
        ),
        "test_code": (
            "const { isPalindrome } = require('./solution.js');\n"
            "\n"
            "function assertEqual(actual, expected, label) {\n"
            "  if (actual !== expected) {\n"
            "    throw new Error(`FAIL ${label}: expected ${expected}, got ${actual}`);\n"
            "  }\n"
            "  console.log(`PASS ${label}`);\n"
            "}\n"
            "\n"
            "assertEqual(isPalindrome('racecar'), true, 'racecar');\n"
            "assertEqual(isPalindrome('RaceCar'), true, 'RaceCar case-insensitive');\n"
            "assertEqual(isPalindrome('A man a plan a canal Panama'), true, 'phrase');\n"
            "assertEqual(isPalindrome('hello'), false, 'hello');\n"
            "assertEqual(isPalindrome(''), true, 'empty');\n"
            "console.log('All tests passed.');\n"
        ),
        "test_command": "node test_solution.js",
    },
    {
        "id": "js-sum-array",
        "language": "javascript",
        "instruction": (
            "solution.js should export `sumArray(nums)` that returns the sum of all "
            "numbers in the array.  An empty array should return 0.  The current "
            "implementation returns 0 for non-empty arrays.  Run the test, fix the bug, "
            "and re-run until the test passes."
        ),
        "source_filename": "solution.js",
        "test_filename": "test_solution.js",
        "workdir": "js_sum",
        "broken_code": (
            "function sumArray(nums) {\n"
            "  // BUG: returns 0 always\n"
            "  return 0;\n"
            "}\n"
            "\n"
            "module.exports = { sumArray };\n"
        ),
        "test_code": (
            "const { sumArray } = require('./solution.js');\n"
            "\n"
            "function assertEqual(actual, expected, label) {\n"
            "  if (actual !== expected) {\n"
            "    throw new Error(`FAIL ${label}: expected ${expected}, got ${actual}`);\n"
            "  }\n"
            "  console.log(`PASS ${label}`);\n"
            "}\n"
            "\n"
            "assertEqual(sumArray([1, 2, 3]), 6, '[1,2,3]');\n"
            "assertEqual(sumArray([0, 0, 0]), 0, 'all zeros');\n"
            "assertEqual(sumArray([]), 0, 'empty');\n"
            "assertEqual(sumArray([-1, 1, -1, 1]), 0, 'mixed signs');\n"
            "assertEqual(sumArray([100]), 100, 'single');\n"
            "console.log('All tests passed.');\n"
        ),
        "test_command": "node test_solution.js",
    },
    # ------------------------------------------------------------------
    # Rust (2 tasks)
    # ------------------------------------------------------------------
    {
        "id": "rust-gcd",
        "language": "rust",
        "instruction": (
            "src/lib.rs should expose a `gcd(a: u64, b: u64) -> u64` function that "
            "computes the greatest common divisor of a and b using Euclid's algorithm. "
            "The current implementation is wrong.  Run `cargo test`, fix src/lib.rs, "
            "and re-run until the test passes."
        ),
        "source_filename": "src/lib.rs",
        "test_filename": "tests/gcd.rs",
        "workdir": "rust_gcd",
        "broken_code": (
            "pub fn gcd(a: u64, b: u64) -> u64 {\n"
            "    // BUG: returns a instead of the gcd\n"
            "    a\n"
            "}\n"
        ),
        "test_code": (
            "use polyglot_task::gcd;\n"
            "\n"
            "#[test]\n"
            "fn gcd_basic() {\n"
            "    assert_eq!(gcd(12, 8), 4);\n"
            "    assert_eq!(gcd(8, 12), 4);\n"
            "}\n"
            "\n"
            "#[test]\n"
            "fn gcd_coprime() {\n"
            "    assert_eq!(gcd(13, 7), 1);\n"
            "}\n"
            "\n"
            "#[test]\n"
            "fn gcd_zero() {\n"
            "    assert_eq!(gcd(0, 5), 5);\n"
            "    assert_eq!(gcd(5, 0), 5);\n"
            "    assert_eq!(gcd(0, 0), 0);\n"
            "}\n"
            "\n"
            "#[test]\n"
            "fn gcd_equal() {\n"
            "    assert_eq!(gcd(42, 42), 42);\n"
            "}\n"
        ),
        "test_command": "cargo test --quiet",
        "extra_files": {
            "Cargo.toml": (
                "[package]\n"
                "name = \"polyglot_task\"\n"
                "version = \"0.1.0\"\n"
                "edition = \"2021\"\n"
                "\n"
                "[lib]\n"
                "path = \"src/lib.rs\"\n"
            ),
        },
    },
    {
        "id": "rust-factorial",
        "language": "rust",
        "instruction": (
            "src/lib.rs should expose `factorial(n: u64) -> u64` that returns n! "
            "with factorial(0) == 1.  The current implementation has an off-by-one bug. "
            "Run `cargo test`, fix src/lib.rs, and re-run until the tests pass."
        ),
        "source_filename": "src/lib.rs",
        "test_filename": "tests/factorial.rs",
        "workdir": "rust_factorial",
        "broken_code": (
            "pub fn factorial(n: u64) -> u64 {\n"
            "    // BUG: starts at 0\n"
            "    let mut acc: u64 = 0;\n"
            "    for i in 1..=n {\n"
            "        acc *= i;\n"
            "    }\n"
            "    acc\n"
            "}\n"
        ),
        "test_code": (
            "use polyglot_task::factorial;\n"
            "\n"
            "#[test]\n"
            "fn factorial_zero() {\n"
            "    assert_eq!(factorial(0), 1);\n"
            "}\n"
            "\n"
            "#[test]\n"
            "fn factorial_small() {\n"
            "    assert_eq!(factorial(1), 1);\n"
            "    assert_eq!(factorial(5), 120);\n"
            "}\n"
            "\n"
            "#[test]\n"
            "fn factorial_six() {\n"
            "    assert_eq!(factorial(6), 720);\n"
            "}\n"
        ),
        "test_command": "cargo test --quiet",
        "extra_files": {
            "Cargo.toml": (
                "[package]\n"
                "name = \"polyglot_task\"\n"
                "version = \"0.1.0\"\n"
                "edition = \"2021\"\n"
                "\n"
                "[lib]\n"
                "path = \"src/lib.rs\"\n"
            ),
        },
    },
    # ------------------------------------------------------------------
    # Go (2 tasks)
    # ------------------------------------------------------------------
    {
        "id": "go-max",
        "language": "go",
        "instruction": (
            "solution.go should expose a `Max(nums []int) int` function that returns "
            "the largest value in nums, and 0 for an empty slice.  The current "
            "implementation always returns 0.  Run `go test`, fix solution.go, and "
            "re-run until the tests pass."
        ),
        "source_filename": "solution.go",
        "test_filename": "solution_test.go",
        "workdir": "go_max",
        "broken_code": (
            "package solution\n"
            "\n"
            "// Max returns the largest value in nums, or 0 if nums is empty.\n"
            "func Max(nums []int) int {\n"
            "\t// BUG: always returns 0\n"
            "\treturn 0\n"
            "}\n"
        ),
        "test_code": (
            "package solution\n"
            "\n"
            "import \"testing\"\n"
            "\n"
            "func TestMaxBasic(t *testing.T) {\n"
            "\tif got := Max([]int{1, 5, 3}); got != 5 {\n"
            "\t\tt.Fatalf(\"expected 5, got %d\", got)\n"
            "\t}\n"
            "}\n"
            "\n"
            "func TestMaxNegative(t *testing.T) {\n"
            "\tif got := Max([]int{-3, -1, -7}); got != -1 {\n"
            "\t\tt.Fatalf(\"expected -1, got %d\", got)\n"
            "\t}\n"
            "}\n"
            "\n"
            "func TestMaxEmpty(t *testing.T) {\n"
            "\tif got := Max([]int{}); got != 0 {\n"
            "\t\tt.Fatalf(\"expected 0, got %d\", got)\n"
            "\t}\n"
            "}\n"
            "\n"
            "func TestMaxSingle(t *testing.T) {\n"
            "\tif got := Max([]int{42}); got != 42 {\n"
            "\t\tt.Fatalf(\"expected 42, got %d\", got)\n"
            "\t}\n"
            "}\n"
        ),
        "test_command": "go test -v ./...",
    },
    {
        "id": "go-is-prime",
        "language": "go",
        "instruction": (
            "solution.go should expose `IsPrime(n int) bool` that returns true when "
            "n is a prime number (n >= 2 with no positive divisors other than 1 and n). "
            "The current implementation has an inverted condition.  Run `go test`, "
            "fix solution.go, and re-run until the tests pass."
        ),
        "source_filename": "solution.go",
        "test_filename": "solution_test.go",
        "workdir": "go_prime",
        "broken_code": (
            "package solution\n"
            "\n"
            "// IsPrime reports whether n is a prime number.\n"
            "func IsPrime(n int) bool {\n"
            "\tif n < 2 {\n"
            "\t\treturn false\n"
            "\t}\n"
            "\tfor i := 2; i*i <= n; i++ {\n"
            "\t\t// BUG: returns true on first divisor found (should be false)\n"
            "\t\tif n%i == 0 {\n"
            "\t\t\treturn true\n"
            "\t\t}\n"
            "\t}\n"
            "\treturn false\n"
            "}\n"
        ),
        "test_code": (
            "package solution\n"
            "\n"
            "import \"testing\"\n"
            "\n"
            "func TestIsPrimeTrue(t *testing.T) {\n"
            "\tfor _, p := range []int{2, 3, 5, 7, 11, 13, 17, 19, 23, 29} {\n"
            "\t\tif !IsPrime(p) {\n"
            "\t\t\tt.Fatalf(\"expected %d to be prime\", p)\n"
            "\t\t}\n"
            "\t}\n"
            "}\n"
            "\n"
            "func TestIsPrimeFalse(t *testing.T) {\n"
            "\tfor _, c := range []int{0, 1, 4, 6, 8, 9, 10, 12, 15, 21, 100} {\n"
            "\t\tif IsPrime(c) {\n"
            "\t\t\tt.Fatalf(\"expected %d to be composite\", c)\n"
            "\t\t}\n"
            "\t}\n"
            "}\n"
        ),
        "test_command": "go test -v ./...",
    },
    # ------------------------------------------------------------------
    # C++ (2 tasks)
    # ------------------------------------------------------------------
    {
        "id": "cpp-factorial",
        "language": "cpp",
        "instruction": (
            "solution.cpp should define `int factorial(int n)` that returns n! "
            "with factorial(0) == 1.  Compile with `g++ -std=c++17 solution.cpp test_solution.cpp -o test_runner` "
            "and run `./test_runner`.  The current implementation has an off-by-one bug.  "
            "Fix solution.cpp and re-run until the tests pass."
        ),
        "source_filename": "solution.cpp",
        "test_filename": "test_solution.cpp",
        "workdir": "cpp_factorial",
        "broken_code": (
            "int factorial(int n) {\n"
            "    // BUG: acc starts at 0\n"
            "    int acc = 0;\n"
            "    for (int i = 1; i <= n; ++i) {\n"
            "        acc *= i;\n"
            "    }\n"
            "    return acc;\n"
            "}\n"
        ),
        "test_code": (
            "#include <cstdio>\n"
            "#include <cstdlib>\n"
            "\n"
            "int factorial(int n);\n"
            "\n"
            "static int failures = 0;\n"
            "\n"
            "static void check(int got, int want, const char* label) {\n"
            "    if (got != want) {\n"
            "        std::printf(\"FAIL %s: expected %d, got %d\\n\", label, want, got);\n"
            "        ++failures;\n"
            "    } else {\n"
            "        std::printf(\"PASS %s\\n\", label);\n"
            "    }\n"
            "}\n"
            "\n"
            "int main() {\n"
            "    check(factorial(0), 1, \"factorial(0)\");\n"
            "    check(factorial(1), 1, \"factorial(1)\");\n"
            "    check(factorial(5), 120, \"factorial(5)\");\n"
            "    check(factorial(6), 720, \"factorial(6)\");\n"
            "    if (failures != 0) {\n"
            "        std::printf(\"%d test(s) failed.\\n\", failures);\n"
            "        return 1;\n"
            "    }\n"
            "    std::printf(\"All tests passed.\\n\");\n"
            "    return 0;\n"
            "}\n"
        ),
        "test_command": (
            "bash -c 'g++ -std=c++17 solution.cpp test_solution.cpp -o test_runner "
            "&& ./test_runner'"
        ),
    },
    {
        "id": "cpp-vowels",
        "language": "cpp",
        "instruction": (
            "solution.cpp should define `int countVowels(const std::string& s)` that returns "
            "the number of vowels (a, e, i, o, u, case-insensitive) in s.  Compile with "
            "`g++ -std=c++17 solution.cpp test_solution.cpp -o test_runner` and run "
            "`./test_runner`.  The current implementation misses uppercase vowels.  "
            "Fix solution.cpp and re-run until the tests pass."
        ),
        "source_filename": "solution.cpp",
        "test_filename": "test_solution.cpp",
        "workdir": "cpp_vowels",
        "broken_code": (
            "#include <string>\n"
            "\n"
            "int countVowels(const std::string& s) {\n"
            "    // BUG: only counts lowercase vowels\n"
            "    int n = 0;\n"
            "    for (char c : s) {\n"
            "        if (c == 'a' || c == 'e' || c == 'i' || c == 'o' || c == 'u') {\n"
            "            ++n;\n"
            "        }\n"
            "    }\n"
            "    return n;\n"
            "}\n"
        ),
        "test_code": (
            "#include <cstdio>\n"
            "#include <string>\n"
            "\n"
            "int countVowels(const std::string& s);\n"
            "\n"
            "static int failures = 0;\n"
            "\n"
            "static void check(int got, int want, const char* label) {\n"
            "    if (got != want) {\n"
            "        std::printf(\"FAIL %s: expected %d, got %d\\n\", label, want, got);\n"
            "        ++failures;\n"
            "    } else {\n"
            "        std::printf(\"PASS %s\\n\", label);\n"
            "    }\n"
            "}\n"
            "\n"
            "int main() {\n"
            "    check(countVowels(\"hello\"), 2, \"hello\");\n"
            "    check(countVowels(\"HELLO\"), 2, \"HELLO\");\n"
            "    check(countVowels(\"xyz\"), 0, \"xyz\");\n"
            "    check(countVowels(\"AEIOUaeiou\"), 10, \"AEIOUaeiou\");\n"
            "    check(countVowels(\"\"), 0, \"empty\");\n"
            "    if (failures != 0) {\n"
            "        std::printf(\"%d test(s) failed.\\n\", failures);\n"
            "        return 1;\n"
            "    }\n"
            "    std::printf(\"All tests passed.\\n\");\n"
            "    return 0;\n"
            "}\n"
        ),
        "test_command": (
            "bash -c 'g++ -std=c++17 solution.cpp test_solution.cpp -o test_runner "
            "&& ./test_runner'"
        ),
    },
]


# ============================================================================
# Terminal Tool Definition (matches Hermes-Agent format)
# ============================================================================

TERMINAL_TOOL_DEFINITION = {
    "type": "function",
    "function": {
        "name": "terminal",
        "description": """Execute bash commands in a sandboxed environment.

**Environment:**
- Isolated execution environment (local, Docker, or Modal cloud)
- Filesystem persists between tool calls within the same task
- Internet access available

**Command Execution:**
- Provide the command to execute via the 'command' parameter
- Optional 'timeout' parameter in seconds (default: 60)

**Examples:**
- Run command: `{"command": "ls -la"}`
- With timeout: `{"command": "long_task.sh", "timeout": 300}`

**Best Practices:**
- Use non-interactive commands (avoid vim, nano, interactive python)
- Pipe to cat if output might be large
- Install tools with apt-get or pip as needed

**Completion:**
- When task is complete, output: echo "MINI_SWE_AGENT_FINAL_OUTPUT" followed by your result
""",
        "parameters": {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "The bash command to execute"
                },
                "timeout": {
                    "type": "integer",
                    "description": "Command timeout in seconds (default: 60)"
                }
            },
            "required": ["command"]
        }
    }
}


# ============================================================================
# Environment Factory
# ============================================================================

def create_environment(
    env_type: str = "local",
    image: str = "python:3.11-slim",
    cwd: str = "/tmp",
    timeout: int = 60,
    **kwargs
):
    """
    Create an execution environment using Hermes-Agent's built-in backends.

    Args:
        env_type: One of "local", "docker", "modal"
        image: Docker/Modal image name (ignored for local)
        cwd: Working directory
        timeout: Default command timeout
        **kwargs: Additional environment-specific options

    Returns:
        Environment instance with execute() and cleanup() methods
    """
    if env_type == "local":
        from tools.environments.local import LocalEnvironment
        return LocalEnvironment(cwd=cwd, timeout=timeout)

    elif env_type == "docker":
        from tools.environments.docker import DockerEnvironment
        return DockerEnvironment(image=image, cwd=cwd, timeout=timeout, **kwargs)

    elif env_type == "modal":
        from tools.environments.modal import ModalEnvironment
        return ModalEnvironment(image=image, cwd=cwd, timeout=timeout, **kwargs)

    else:
        raise ValueError(f"Unknown environment type: {env_type}. Use 'local', 'docker', or 'modal'")


# ============================================================================
# Polyglot Runner with Hermes Trajectory Format
# ============================================================================

class PolyglotRunner:
    """
    Agent runner that uses Hermes-Agent's built-in execution environments
    and outputs trajectories in Hermes-Agent format, evaluating a polyglot
    code-editing benchmark.
    """

    SUPPORTED_LANGUAGES = ("python", "javascript", "rust", "go", "cpp")

    def __init__(
        self,
        model: str = "anthropic/claude-sonnet-4.6",
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        env_type: str = "local",
        image: str = "python:3.11-slim",
        cwd: str = "/tmp",
        max_iterations: int = 20,
        command_timeout: int = 60,
        verbose: bool = False,
    ):
        """
        Initialize the Polyglot Runner.

        Args:
            model: Model name for OpenAI-compatible API
            base_url: API base URL (optional, uses env vars if not provided)
            api_key: API key (optional, uses env vars if not provided)
            env_type: Environment type - "local", "docker", or "modal"
            image: Docker/Modal image (ignored for local)
            cwd: Working directory for commands
            max_iterations: Maximum tool-calling iterations per task
            command_timeout: Default timeout for commands
            verbose: Enable verbose logging
        """
        self.model = model
        self.max_iterations = max_iterations
        self.command_timeout = command_timeout
        self.verbose = verbose
        self.env_type = env_type
        self.image = image
        self.cwd = cwd

        # Setup logging
        logging.basicConfig(
            level=logging.DEBUG if verbose else logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            datefmt='%H:%M:%S'
        )
        self.logger = logging.getLogger(__name__)

        # Initialize LLM client via centralized provider router.
        # If explicit api_key/base_url are provided (e.g. from CLI args),
        # construct directly.  Otherwise use the router for OpenRouter.
        self.client: Any  # OpenAI-compatible client; every branch below assigns one
        if api_key or base_url:
            from openai import OpenAI
            client_kwargs: Dict[str, Any] = {
                "base_url": base_url or "https://openrouter.ai/api/v1",
                "api_key": api_key or os.getenv(
                    "OPENROUTER_API_KEY",
                    os.getenv("ANTHROPIC_API_KEY",
                              os.getenv("OPENAI_API_KEY", ""))),
            }
            self.client = OpenAI(**client_kwargs)
        else:
            from agent.auxiliary_client import resolve_provider_client
            self.client, _ = resolve_provider_client("openrouter", model=model)
            if self.client is None:
                # Fallback: try auto-detection
                self.client, _ = resolve_provider_client("auto", model=model)
            if self.client is None:
                from openai import OpenAI
                self.client = OpenAI(
                    base_url="https://openrouter.ai/api/v1",
                    api_key=os.getenv("OPENROUTER_API_KEY", ""))

        # Environment will be created per-task
        self.env = None

        # Tool definition
        self.tools: List[Dict[str, Any]] = [TERMINAL_TOOL_DEFINITION]

        # Where to stage per-task source trees
        self.stage_root = Path(self.cwd) / "_polyglot_stage"
        self.stage_root.mkdir(parents=True, exist_ok=True)

        print("🤖 Polyglot Runner initialized")
        print(f"   Model: {self.model}")
        print(f"   Environment: {self.env_type}")
        if self.env_type != "local":
            print(f"   Image: {self.image}")
        print(f"   Max iterations: {self.max_iterations}")
        print(f"   Stage root: {self.stage_root}")

    # ------------------------------------------------------------------
    # Environment lifecycle
    # ------------------------------------------------------------------
    def _create_env(self):
        """Create the execution environment."""
        print(f"🔧 Creating {self.env_type} environment...")
        self.env = create_environment(
            env_type=self.env_type,
            image=self.image,
            cwd=self.cwd,
            timeout=self.command_timeout
        )
        print("✅ Environment ready")

    def _cleanup_env(self):
        """Cleanup the execution environment."""
        if self.env is not None:
            if hasattr(self.env, 'cleanup'):
                self.env.cleanup()
            elif hasattr(self.env, 'stop'):
                self.env.stop()
            self.env = None

    def _execute_command(self, command: str, timeout: Optional[int] = None) -> Dict[str, Any]:
        """
        Execute a command in the environment.

        Args:
            command: Bash command to execute
            timeout: Optional timeout override

        Returns:
            Dict with 'output' and 'exit_code'
        """
        if self.env is None:
            self._create_env()
        assert self.env is not None  # _create_env() either sets self.env or raises

        try:
            result = self.env.execute(command, timeout=timeout or self.command_timeout)
            return {
                "output": result.get("output", ""),
                "exit_code": result.get("returncode", 0),
                "error": None
            }
        except Exception as e:
            return {
                "output": "",
                "exit_code": -1,
                "error": str(e)
            }

    # ------------------------------------------------------------------
    # Task staging
    # ------------------------------------------------------------------
    def _stage_task_in_env(self, task: Dict[str, Any]) -> str:
        """
        Write the broken source + tests for a task INSIDE the agent's environment
        via the terminal, so the agent can see and edit them.

        Returns:
            Absolute path to the per-task workdir (inside the env).
        """
        workdir_posix = f"/tmp/_polyglot_stage/{task['workdir']}"

        def _write_file(relpath: str, contents: str) -> None:
            # Write via pure shell (base64 -d) — python3 on Windows is a native
            # binary that doesn't understand MSYS /tmp paths.
            target = f"{workdir_posix}/{relpath}"
            import base64 as _b64
            encoded = _b64.b64encode(contents.encode("utf-8")).decode("ascii")
            parent = target.rsplit("/", 1)[0] if "/" in target else "."
            mkdir_result = self._execute_command(f"mkdir -p '{parent}'", timeout=10)
            if mkdir_result["exit_code"] != 0:
                raise RuntimeError(f"Failed to mkdir {parent}: {mkdir_result['output']}")
            # Use shell builtin base64 decode, no python needed
            cmd = f"echo '{encoded}' | base64 -d > '{target}'"
            result = self._execute_command(cmd, timeout=30)
            if result["exit_code"] != 0:
                raise RuntimeError(f"Failed to write {target}: {result['output']} {result.get('error')}")

        _write_file(task["source_filename"], task["broken_code"])
        _write_file(task["test_filename"], task["test_code"])
        for relpath, contents in (task.get("extra_files") or {}).items():
            _write_file(relpath, contents)

        return workdir_posix

    def _stage_task(self, task: Dict[str, Any]) -> str:
        """
        Write the broken source + tests for a task into a per-task directory.

        Returns:
            Absolute path to the per-task workdir.
        """
        workdir = self.stage_root / task["workdir"]
        workdir.mkdir(parents=True, exist_ok=True)

        source_path = workdir / task["source_filename"]
        source_path.write_text(task["broken_code"], encoding="utf-8")

        test_path = workdir / task["test_filename"]
        # Ensure parent exists for nested test paths (Rust integration tests)
        test_path.parent.mkdir(parents=True, exist_ok=True)
        test_path.write_text(task["test_code"], encoding="utf-8")

        # Optional extra files (e.g. Cargo.toml, package.json)
        for relpath, contents in (task.get("extra_files") or {}).items():
            extra_path = workdir / relpath
            extra_path.parent.mkdir(parents=True, exist_ok=True)
            extra_path.write_text(contents, encoding="utf-8")

        return str(workdir)

    def _get_initial_failing_output(self, task: Dict[str, Any], workdir: str) -> str:
        """Run the test once before the agent edits, to capture the failing output."""
        cmd = f"cd {workdir} && {task['test_command']}"
        result = self._execute_command(cmd, timeout=self.command_timeout)
        return (
            f"$ {cmd}\n"
            f"[exit_code={result['exit_code']}]\n"
            f"{result['output']}\n"
        )

    # ------------------------------------------------------------------
    # Format helpers
    # ------------------------------------------------------------------
    def _format_tools_for_system_message(self) -> str:
        """Format tool definitions for the system message."""
        formatted_tools = []
        for tool in self.tools:
            func = tool["function"]
            formatted_tools.append({
                "name": func["name"],
                "description": func.get("description", ""),
                "parameters": func.get("parameters", {}),
                "required": None
            })
        return json.dumps(formatted_tools, ensure_ascii=False)

    def _convert_to_hermes_format(
        self,
        messages: List[Dict[str, Any]],
        user_query: str,
        completed: bool
    ) -> List[Dict[str, Any]]:
        """
        Convert internal message format to Hermes trajectory format.

        This produces the exact format used by batch_runner.py.
        """
        trajectory = []

        # System message with tool definitions
        system_msg = (
            "You are a function calling AI model. You are provided with function signatures within <tools> </tools> XML tags. "
            "You may call one or more functions to assist with the user query. If available tools are not relevant in assisting "
            "with user query, just respond in natural conversational language. Don't make assumptions about what values to plug "
            "into functions. After calling & executing the functions, you will be provided with function results within "
            "<tool_response> </tool_response> XML tags. Here are the available tools:\n"
            f"<tools>\n{self._format_tools_for_system_message()}\n</tools>\n"
            "For each function call return a JSON object, with the following pydantic model json schema for each:\n"
            "{'title': 'FunctionCall', 'type': 'object', 'properties': {'name': {'title': 'Name', 'type': 'string'}, "
            "'arguments': {'title': 'Arguments', 'type': 'object'}}, 'required': ['name', 'arguments']}\n"
            "Each function call should be enclosed within <tool_call> </tool_call> XML tags.\n"
            "Example:\n<tool_call>\n{'name': <function-name>,'arguments': <args-dict>}\n</tool_call>"
        )

        trajectory.append({"from": "system", "value": system_msg})
        trajectory.append({"from": "human", "value": user_query})

        # Process messages (skip first user message as we already added it)
        i = 1
        while i < len(messages):
            msg = messages[i]

            if msg["role"] == "assistant":
                if "tool_calls" in msg and msg["tool_calls"]:
                    # Assistant message with tool calls
                    content = ""

                    # Add reasoning if present
                    if msg.get("reasoning"):
                        content = f"<think>{msg['reasoning']}</think>"

                    if msg.get("content"):
                        content += msg["content"] + "\n"

                    # Add tool calls in XML format
                    for tool_call in msg["tool_calls"]:
                        if not tool_call or not isinstance(tool_call, dict): continue
                        try:
                            arguments = json.loads(tool_call["function"]["arguments"]) \
                                if isinstance(tool_call["function"]["arguments"], str) \
                                else tool_call["function"]["arguments"]
                        except json.JSONDecodeError:
                            arguments = {}

                        tool_call_json = {
                            "name": tool_call["function"]["name"],
                            "arguments": arguments
                        }
                        content += f"<tool_call>\n{json.dumps(tool_call_json, ensure_ascii=False)}\n</tool_call>\n"

                    trajectory.append({"from": "gpt", "value": content.rstrip()})

                    # Collect subsequent tool responses
                    tool_responses = []
                    j = i + 1
                    while j < len(messages) and messages[j]["role"] == "tool":
                        tool_msg = messages[j]
                        tool_content = tool_msg["content"]

                        # Try to parse as JSON
                        try:
                            if tool_content.strip().startswith(("{")):
                                tool_content = json.loads(tool_content)
                        except (json.JSONDecodeError, AttributeError):
                            pass

                        tool_response = "<tool_response>\n"
                        tool_response += json.dumps({
                            "tool_call_id": tool_msg.get("tool_call_id", ""),
                            "name": msg["tool_calls"][len(tool_responses)]["function"]["name"] \
                                if len(tool_responses) < len(msg["tool_calls"]) else "unknown",
                            "content": tool_content
                        }, ensure_ascii=False)
                        tool_response += "\n</tool_response>"
                        tool_responses.append(tool_response)
                        j += 1

                    if tool_responses:
                        trajectory.append({"from": "tool", "value": "\n".join(tool_responses)})
                        i = j - 1

                else:
                    # Regular assistant message (no tool calls)
                    content = ""
                    if msg.get("reasoning"):
                        content = f"<think>{msg['reasoning']}</think>"
                    content += msg.get("content") or ""
                    trajectory.append({"from": "gpt", "value": content})

            elif msg["role"] == "user":
                trajectory.append({"from": "human", "value": msg["content"]})

            i += 1

        return trajectory

    # ------------------------------------------------------------------
    # Scoring
    # ------------------------------------------------------------------
    def _score_task(self, task: Dict[str, Any], workdir: str) -> Dict[str, Any]:
        """
        Run the test command for a task and return whether it passed.

        Returns a dict with 'passed' (bool), 'exit_code' (int),
        and 'output' (str, last 2000 chars to keep trajectories compact).
        """
        cmd = f"cd {workdir} && {task['test_command']}"
        result = self._execute_command(cmd, timeout=self.command_timeout)
        return {
            "passed": result["exit_code"] == 0,
            "exit_code": result["exit_code"],
            "command": cmd,
            "output": result["output"][-2000:],
            "error": result.get("error"),
        }

    # ------------------------------------------------------------------
    # Single task driver
    # ------------------------------------------------------------------
    def run_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """
        Run a single polyglot task and return the result with trajectory.

        The flow:
        1. Stage the broken source + tests on disk
        2. Run the test once to capture the failing output
        3. Drive the agent loop: the agent sees the instruction and the failing
           test output, uses the terminal tool to inspect + edit, until it
           declares completion (echo MINI_SWE_AGENT_FINAL_OUTPUT) or hits the
           iteration cap
        4. Re-run the test and score 1/0

        Args:
            task: A task dict from POLYGLOT_TASKS

        Returns:
            Dict with trajectory, pass/fail, score, and metadata
        """
        print(f"\n{'='*70}")
        print(f"📝 Task {task['id']} [{task['language']}]: {task['instruction'][:80]}...")
        print(f"{'='*70}")

        # Initialize environment FIRST so staging lands inside the agent's env
        self._create_env()

        # Stage files INSIDE the env (not on the host) so the agent can see them
        workdir = self._stage_task_in_env(task)
        print(f"📂 Staged at: {workdir}")

        # Initial failing run
        failing_output = self._get_initial_failing_output(task, workdir)
        print(f"💥 Initial test run captured ({len(failing_output)} chars)")

        # Build the user message: instruction + failing test output
        user_query = (
            f"{task['instruction']}\n\n"
            f"Working directory: {workdir}\n"
            f"Source file: {task['source_filename']}\n"
            f"Test file: {task['test_filename']}\n"
            f"Test command: {task['test_command']}\n\n"
            f"--- Initial failing test output ---\n"
            f"{failing_output}\n"
            f"--- End failing test output ---\n\n"
            f"Edit the source file so the test passes, then re-run the test command. "
            f"When done, output `echo MINI_SWE_AGENT_FINAL_OUTPUT` so I know to grade your work."
        )

        # Message history
        messages: List[Dict[str, Any]] = [{"role": "user", "content": user_query}]

        # System prompt for the LLM (ephemeral - not saved to trajectory)
        system_prompt = """You are an AI agent that can execute bash commands to complete tasks.

When you need to run commands, use the 'terminal' tool with your bash command.

**Important:**
- When you have completed the task successfully, run: echo "MINI_SWE_AGENT_FINAL_OUTPUT" followed by a summary
- Be concise and efficient in your approach
- Install any needed tools with apt-get or pip
- Avoid interactive commands (no vim, nano, less, etc.)

Complete the user's task step by step."""

        api_call_count = 0
        completed = False
        final_response = None

        try:
            while api_call_count < self.max_iterations:
                api_call_count += 1
                print(f"\n🔄 API call #{api_call_count}/{self.max_iterations}")

                # Prepare API messages
                api_messages = [{"role": "system", "content": system_prompt}] + messages

                # Make API call
                try:
                    api_kwargs = {
                        "model": self.model,
                        "messages": api_messages,
                        "tools": self.tools,
                        "timeout": 300.0,
                    }
                    fixed_temperature = _effective_temperature_for_model(
                        self.model,
                        str(getattr(self.client, "base_url", "") or ""),
                    )
                    if fixed_temperature is not None:
                        api_kwargs["temperature"] = fixed_temperature

                    response = self.client.chat.completions.create(**api_kwargs)
                except Exception as e:
                    self.logger.error(f"API call failed: {e}")
                    break

                assistant_message = response.choices[0].message

                # Log assistant response
                if assistant_message.content:
                    print(f"🤖 Assistant: {assistant_message.content[:100]}...")

                # Check for tool calls
                if assistant_message.tool_calls:
                    print(f"🔧 Tool calls: {len(assistant_message.tool_calls)}")

                    # Add assistant message with tool calls
                    messages.append({
                        "role": "assistant",
                        "content": assistant_message.content,
                        "tool_calls": [
                            {
                                "id": tc.id,
                                "type": tc.type,
                                "function": {
                                    "name": tc.function.name,
                                    "arguments": tc.function.arguments
                                }
                            }
                            for tc in assistant_message.tool_calls
                        ]
                    })

                    # Execute each tool call
                    for tc in assistant_message.tool_calls:
                        try:
                            args = json.loads(tc.function.arguments)
                        except json.JSONDecodeError:
                            args = {}

                        command = args.get("command", "echo 'No command provided'")
                        timeout = args.get("timeout", self.command_timeout)

                        print(f"   📞 terminal: {command[:60]}...")

                        # Execute command
                        result = self._execute_command(command, timeout)

                        # Format result
                        result_json = json.dumps({
                            "content": {
                                "output": result["output"],
                                "exit_code": result["exit_code"],
                                "error": result["error"]
                            }
                        }, ensure_ascii=False)

                        # Check for task completion signal
                        if "MINI_SWE_AGENT_FINAL_OUTPUT" in result["output"]:
                            print("   ✅ Task completion signal detected!")
                            completed = True

                        # Add tool response
                        messages.append(make_tool_result_message(
                            tc.function.name, result_json, tc.id,
                        ))

                        print(f"   ✅ exit_code={result['exit_code']}, output={len(result['output'])} chars")

                    # If task completed, we can stop
                    if completed:
                        final_response = assistant_message.content
                        break

                else:
                    # No tool calls - final response
                    final_response = assistant_message.content or ""
                    messages.append({
                        "role": "assistant",
                        "content": final_response
                    })
                    completed = True
                    print("🎉 Agent finished (no more tool calls)")
                    break

            if api_call_count >= self.max_iterations:
                print(f"⚠️  Reached max iterations ({self.max_iterations})")

        finally:
            # Cleanup environment
            self._cleanup_env()

        # Score: re-run the test command after the agent is done
        score_result = self._score_task(task, workdir)
        score = 1 if score_result["passed"] else 0
        print(f"🏁 Score: {score} (exit_code={score_result['exit_code']})")

        # Convert to Hermes trajectory format
        trajectory = self._convert_to_hermes_format(messages, user_query, completed)

        return {
            "id": task["id"],
            "language": task["language"],
            "instruction": task["instruction"],
            "workdir": workdir,
            "source_filename": task["source_filename"],
            "test_filename": task["test_filename"],
            "test_command": task["test_command"],
            "score": score,
            "passed": score_result["passed"],
            "exit_code": score_result["exit_code"],
            "score_output": score_result["output"],
            "completed": completed,
            "api_calls": api_call_count,
            "conversations": trajectory,
            "metadata": {
                "model": self.model,
                "env_type": self.env_type,
                "timestamp": datetime.now().isoformat(),
            },
        }

    # ------------------------------------------------------------------
    # Batch driver
    # ------------------------------------------------------------------
    def run_batch(
        self,
        language: Optional[str] = None,
        limit: Optional[int] = None,
        output_file: str = "results.jsonl",
    ) -> Dict[str, Any]:
        """
        Run a batch of polyglot tasks, filterable by language, capped at `limit`.

        Args:
            language: Only run tasks matching this language (case-insensitive).
                      None = all languages.
            limit: Max number of tasks to run.  None = all matching tasks.
            output_file: JSONL file to write per-task results to.

        Returns:
            Dict with 'results' (list), 'per_language_accuracy' (dict), and
            'overall_accuracy' (float).
        """
        # Filter
        tasks = POLYGLOT_TASKS
        if language:
            lang_lower = language.lower()
            if lang_lower not in self.SUPPORTED_LANGUAGES:
                raise ValueError(
                    f"Unknown language '{language}'. "
                    f"Supported: {', '.join(self.SUPPORTED_LANGUAGES)}"
                )
            tasks = [t for t in tasks if t["language"].lower() == lang_lower]

        if limit is not None:
            tasks = tasks[:limit]

        if not tasks:
            print(f"❌ No tasks matched language={language!r} limit={limit!r}")
            return {
                "results": [],
                "per_language_accuracy": {},
                "overall_accuracy": 0.0,
            }

        print(f"\n📦 Running {len(tasks)} polyglot task(s)")
        print(f"   language={language!r}  limit={limit}  model={self.model}")
        print(f"📁 Output: {output_file}")

        results: List[Dict[str, Any]] = []
        per_lang: Dict[str, Dict[str, int]] = {}

        with open(output_file, "w", encoding="utf-8") as f:
            for i, task in enumerate(tasks, 1):
                print(f"\n{'='*70}")
                print(f"📋 Task {i}/{len(tasks)}: {task['id']} [{task['language']}]")
                print(f"{'='*70}")
                t0 = time.time()
                try:
                    result = self.run_task(task)
                except Exception as e:
                    self.logger.error(f"Error on task {task['id']}: {e}")
                    result = {
                        "id": task["id"],
                        "language": task["language"],
                        "instruction": task["instruction"],
                        "score": 0,
                        "passed": False,
                        "error": str(e),
                        "conversations": [],
                        "metadata": {"timestamp": datetime.now().isoformat()},
                    }
                result["duration_s"] = round(time.time() - t0, 2)

                # Per-language accumulators
                lang_stats = per_lang.setdefault(task["language"], {"total": 0, "passed": 0})
                lang_stats["total"] += 1
                if result.get("score") == 1:
                    lang_stats["passed"] += 1

                results.append(result)
                f.write(json.dumps(result, ensure_ascii=False) + "\n")
                f.flush()

                print(
                    f"✅ {task['id']} done — score={result.get('score')} "
                    f"in {result['duration_s']}s"
                )

        # Per-language accuracy
        per_language_accuracy = {
            lang: {
                "total": stats["total"],
                "passed": stats["passed"],
                "accuracy": (stats["passed"] / stats["total"]) if stats["total"] else 0.0,
            }
            for lang, stats in per_lang.items()
        }
        total = sum(s["total"] for s in per_lang.values())
        passed = sum(s["passed"] for s in per_lang.values())
        overall = (passed / total) if total else 0.0

        print("\n" + "=" * 70)
        print("📊 Polyglot benchmark summary")
        print("=" * 70)
        for lang, stats in sorted(per_language_accuracy.items()):
            print(
                f"  {lang:<12}  {stats['passed']}/{stats['total']}  "
                f"({stats['accuracy']:.0%})"
            )
        print(f"  {'OVERALL':<12}  {passed}/{total}  ({overall:.0%})")
        print(f"\n📁 Results written to: {output_file}")

        return {
            "results": results,
            "per_language_accuracy": per_language_accuracy,
            "overall_accuracy": overall,
        }


# ============================================================================
# CLI Interface
# ============================================================================

def main(
    language: Optional[str] = None,
    limit: Optional[int] = None,
    model: str = "kimi-k3",
    base_url: Optional[str] = None,
    api_key: Optional[str] = None,
    output: str = "results.jsonl",
    env: str = "local",
    image: str = "python:3.11-slim",
    cwd: str = "/tmp",
    max_iterations: int = 20,
    timeout: int = 60,
    verbose: bool = False,
):
    """
    Run Aider Polyglot benchmark tasks with Hermes trajectory format.

    Args:
        language: Filter to one of: python, javascript, rust, go, cpp.  None = all.
        limit: Max number of tasks to run (default: all matching).
        model: Model name for the agent (default: kimi-k3).
        base_url: API base URL (optional).
        api_key: API key (optional, uses env vars like KIMI_API_KEY).
        output: Output JSONL file for per-task results.
        env: Environment type - "local", "docker", or "modal".
        image: Docker/Modal image (default: python:3.11-slim).
        cwd: Working directory for staged task files.
        max_iterations: Maximum tool-calling iterations per task.
        timeout: Command timeout in seconds.
        verbose: Enable verbose logging.

    Examples:
        # Run one Python task as a smoke test
        python -m benchmarks.polyglot_runner --language python --limit 1 --model kimi-k3

        # Run 5 Python tasks
        python -m benchmarks.polyglot_runner --language python --limit 5 --model kimi-k3

        # Run all 10 tasks across all 5 languages
        python -m benchmarks.polyglot_runner --model kimi-k3
    """
    print("🚀 Aider Polyglot Runner with Hermes Trajectory Format")
    print("=" * 70)

    # Initialize runner
    runner = PolyglotRunner(
        model=model,
        base_url=base_url,
        api_key=api_key,
        env_type=env,
        image=image,
        cwd=cwd,
        max_iterations=max_iterations,
        command_timeout=timeout,
        verbose=verbose,
    )

    runner.run_batch(
        language=language,
        limit=limit,
        output_file=output,
    )


if __name__ == "__main__":
    fire.Fire(main)
