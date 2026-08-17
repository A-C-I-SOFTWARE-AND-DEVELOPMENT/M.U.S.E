#!/usr/bin/env python3
"""
Terminal-Bench Runner with Hermes Trajectory Format

A runner for Terminal-Bench (https://github.com/laude-institute/terminal-bench)
tasks. Terminal-Bench tests agents on realistic terminal tasks defined in YAML
files with the following schema:

  - instruction:   Natural-language task description given to the agent
  - setup_script:  Bash script run BEFORE the agent to set up the environment
  - test_script:   Bash script run AFTER the agent to verify the solution
  - tags:          Optional list of category tags

For each task the runner:
  1. Runs setup_script in a fresh execution environment
  2. Hands the instruction to the agent (with the 'terminal' tool)
  3. Runs test_script to verify
  4. Scores 1 if test_script exits 0, else 0

This file mirrors mini_swe_runner.py structure (same client init, environment
factory, Hermes trajectory conversion, CLI) and adds:
  - load_terminal_bench_tasks(task_dir) — YAML loader (or built-in samples)
  - TerminalBenchRunner class wrapping the per-task pipeline
  - --task_dir / --limit / --output / --tags CLI flags
  - results.jsonl + summary accuracy output

Usage:
    # Run against the built-in sample tasks (5 of them)
    python -m benchmarks.terminal_bench_runner --limit 1 --model kimi-k3

    # Run against a directory of Terminal-Bench YAML tasks
    python -m benchmarks.terminal_bench_runner --task_dir tasks/ --limit 10 --model kimi-k3

    # Filter by tag
    python -m benchmarks.terminal_bench_runner --task_dir tasks/ --tags easy,safe --model kimi-k3

NOTE ON SCOPE: the built-in ``SAMPLE_TASKS`` are a *runner sanity* fixture.
They are not the canonical Terminal-Bench corpus and nothing this file
produces is an official Terminal-Bench score.


Two recorded defects this module now guards against
===================================================

**D1 — a provider error was recorded as a benchmark score of 0.**
The first recorded Terminal-Bench run (``terminal-bench-test.jsonl``,
2026-07-20T13:24:17) reads ``score 0 / completed false / api_calls 1 /
test_exit_code 1`` and carries *no* ``error`` field at all. Eleven minutes
later the identical task passed (``terminal-bench-results.jsonl``,
13:35:13) with no code change. The cause was structural, not model
quality: ``client.chat.completions.create`` raised, the agent loop hit
``except Exception: ... break``, the exception text went to the logger
(stderr) and was discarded, and the runner then ran ``test_script`` and
recorded the resulting failure as though the *agent* had failed the task.
A transport failure and a genuine task failure were indistinguishable in
the artifact.

Two changes close it:

* transient provider failures are retried with backoff (``api_retries``),
  which is what an eleven-minute-later re-run was doing by hand; and
* a task the agent never got to attempt is **not scored**. Its row carries
  ``score: None``, ``scored: False``, ``status: "provider_error"`` and the
  full exception, and it is written to the ``.unscored.jsonl`` sidecar
  rather than into the scored results file. An unmeasured task is ABSENT,
  never 0 — scoring it 0 would report "the agent tried and failed" about a
  run in which the agent never ran.

**D2 — the ``__summary__`` row was graded as a failed task.**
``run_batch`` used to append ``{"__summary__": {...}}`` to the same
``results.jsonl`` that
``research_fabric.verifier.terminal_bench.verify`` consumes. That verifier
counts every row and treats a row with no ``score`` as a failure, so the
recorded 1/1 (100%) run above grades as **0.5000** — under
``catalog.ABSOLUTE_FLOOR = 0.80``. A perfect Terminal-Bench run therefore
failed the promotion ratchet's floor. The summary now goes to a
``.summary.json`` sidecar and ``results.jsonl`` holds task rows only.
``include_summary_row=True`` restores the old layout for anyone who was
parsing it.

Both are locked by ``tests/characterization/test_terminal_bench_regression.py``.
"""

import json
import logging
import os
import re
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional, Literal

import fire
import yaml
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
# Result status vocabulary
# ============================================================================

# The task ran end to end and ``test_script`` decided it. Only these rows are
# measurements of the agent, and only these rows are written to results.jsonl.
STATUS_SCORED = "scored"
# The provider call raised (connection reset, read timeout, 5xx, auth, rate
# limit) after every retry. The agent never got a turn, so there is nothing to
# score — see D1 in the module docstring.
STATUS_PROVIDER_ERROR = "provider_error"
# ``setup_script`` exited non-zero: the environment was never prepared.
STATUS_SETUP_FAILED = "setup_failed"
# The runner itself raised outside the provider call (environment creation,
# trajectory conversion, ...).
STATUS_RUNNER_ERROR = "runner_error"

#: Statuses that mean "this row is not a measurement of the agent".
UNSCORED_STATUSES = frozenset(
    {STATUS_PROVIDER_ERROR, STATUS_SETUP_FAILED, STATUS_RUNNER_ERROR}
)


def _error_payload(exc: BaseException, attempts: int = 1) -> Dict[str, Any]:
    """Describe an exception in a form that survives into the JSONL row.

    The recorded 2026-07-20 failure lost exactly this: the message went to
    ``logging.error`` (stderr) and the artifact kept nothing.
    """
    return {
        "type": type(exc).__name__,
        "message": str(exc)[:1000],
        "attempts": attempts,
    }


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
- When task is complete, output: echo "TERMINAL_BENCH_FINAL_OUTPUT" followed by your result
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
# Built-in Sample Tasks (5 self-contained tasks, no external download needed)
# ============================================================================

SAMPLE_TASKS: List[Dict[str, Any]] = [
    {
        "id": "sample_create_file",
        "instruction": (
            "Create a file at /tmp/bench_hello.txt that contains exactly the text "
            "'hello terminal-bench' (no quotes, single line, newline at end)."
        ),
        "setup_script": "mkdir -p /tmp && rm -f /tmp/bench_hello.txt",
        "test_script": (
            "test -f /tmp/bench_hello.txt && "
            "grep -qx 'hello terminal-bench' /tmp/bench_hello.txt"
        ),
        "tags": ["easy", "file"],
    },
    {
        "id": "sample_echo_count",
        "instruction": (
            "Write a file at /tmp/bench_count.txt whose contents are the line "
            "'42' repeated exactly 10 times, each on its own line (no trailing "
            "blank line)."
        ),
        "setup_script": "mkdir -p /tmp && rm -f /tmp/bench_count.txt",
        "test_script": (
            "test -f /tmp/bench_count.txt && "
            "[ \"$(wc -l < /tmp/bench_count.txt)\" = \"10\" ] && "
            "grep -qx 42 /tmp/bench_count.txt"
        ),
        "tags": ["easy", "file"],
    },
    {
        "id": "sample_python_import",
        "instruction": (
            "Use the terminal to verify that the Python 'json' standard library "
            "module is importable and can parse a JSON string. Print the parsed "
            "result of the JSON string '{\"ok\": 7}' as a single line containing "
            "the dictionary's 'ok' value (just the number 7) when you finish."
        ),
        "setup_script": "echo ready",
        "test_script": (
            "python -c \"import json; d=json.loads('{\\\"ok\\\": 7}'); "
            "assert d['ok']==7; print('ok')\" | grep -qx ok"
        ),
        "tags": ["easy", "python"],
    },
    {
        "id": "sample_grep_count",
        "instruction": (
            "Count the number of lines in /tmp/bench_data.txt that contain the "
            "word 'apple' (case-sensitive). Write the integer count to "
            "/tmp/bench_apple_count.txt as a single line."
        ),
        "setup_script": (
            "printf 'apple pie\\norange juice\\napple sauce\\nbanana split\\n"
            "Apple turnover\\n' > /tmp/bench_data.txt"
        ),
        "test_script": (
            "test -f /tmp/bench_apple_count.txt && "
            "[ \"$(cat /tmp/bench_apple_count.txt)\" = \"2\" ]"
        ),
        "tags": ["easy", "shell"],
    },
    {
        "id": "sample_make_executable",
        "instruction": (
            "Create a shell script at /tmp/bench_greet.sh that prints exactly "
            "'Greetings from MUSE' and make it executable."
        ),
        "setup_script": "rm -f /tmp/bench_greet.sh",
        "test_script": (
            "test -x /tmp/bench_greet.sh && "
            "[ \"$(/tmp/bench_greet.sh)\" = 'Greetings from MUSE' ]"
        ),
        "tags": ["easy", "script"],
    },
]


def load_terminal_bench_tasks(task_dir: Optional[str] = None) -> List[Dict[str, Any]]:
    """Load Terminal-Bench task definitions from a directory of YAML files.

    Each task file is expected to define:
        instruction:   str  (required) — natural-language task for the agent
        setup_script:  str  (required) — bash run BEFORE the agent
        test_script:   str  (required) — bash run AFTER the agent
        tags:          list (optional) — category tags

    Args:
        task_dir: Path to a directory of *.yaml / *.yml files. If None or
                  the directory does not exist, the built-in SAMPLE_TASKS
                  are returned (5 self-contained tasks). A future version
                  can also download the canonical Terminal-Bench corpus
                  from https://github.com/laude-institute/terminal-bench.

    Returns:
        List of task dicts, each with at least
        {id, instruction, setup_script, test_script, tags}.
    """
    if task_dir is None:
        print("📦 No --task_dir provided; using built-in SAMPLE_TASKS (5 tasks).")
        return list(SAMPLE_TASKS)

    task_path = Path(task_dir)
    if not task_path.is_dir():
        print(f"⚠️  task_dir '{task_dir}' is not a directory; falling back to SAMPLE_TASKS.")
        return list(SAMPLE_TASKS)

    tasks: List[Dict[str, Any]] = []
    yaml_files = sorted(
        list(task_path.glob("*.yaml")) + list(task_path.glob("*.yml"))
    )
    if not yaml_files:
        print(f"⚠️  No YAML files found in '{task_dir}'; using SAMPLE_TASKS.")
        return list(SAMPLE_TASKS)

    for yf in yaml_files:
        try:
            with open(yf, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
        except yaml.YAMLError as e:
            print(f"❌ Failed to parse {yf}: {e}")
            continue

        if not isinstance(data, dict):
            print(f"❌ Skipping {yf}: top-level YAML must be a mapping.")
            continue

        instruction = data.get("instruction")
        setup_script = data.get("setup_script", "")
        test_script = data.get("test_script")
        tags = data.get("tags") or []

        if not instruction or not test_script:
            print(f"❌ Skipping {yf}: missing required 'instruction' or 'test_script'.")
            continue

        task_id = data.get("id") or yf.stem
        tasks.append({
            "id": str(task_id),
            "instruction": str(instruction),
            "setup_script": str(setup_script),
            "test_script": str(test_script),
            "tags": list(tags) if isinstance(tags, list) else [str(tags)],
        })

    print(f"📂 Loaded {len(tasks)} task(s) from {task_dir}")
    return tasks


# ============================================================================
# Environment Factory (identical to mini_swe_runner.py)
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
# Terminal-Bench Runner
# ============================================================================

class TerminalBenchRunner:
    """
    Runner for Terminal-Bench YAML-defined tasks.

    Mirrors MiniSWERunner's structure (init / env / trajectory conversion /
    CLI) but adds the per-task setup -> agent -> test_script verification
    pipeline and writes results.jsonl + a summary line.
    """

    def __init__(
        self,
        model: str = "anthropic/claude-sonnet-4.6",
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        env_type: str = "local",
        image: str = "python:3.11-slim",
        cwd: str = "/tmp",
        max_iterations: int = 15,
        command_timeout: int = 60,
        verbose: bool = False,
        api_retries: int = 2,
        retry_backoff_seconds: float = 2.0,
    ):
        self.model = model
        self.max_iterations = max_iterations
        self.command_timeout = command_timeout
        self.verbose = verbose
        self.env_type = env_type
        self.image = image
        self.cwd = cwd
        # Extra attempts after the first for a failed provider call. The
        # recorded 2026-07-20 failure was a transient transport error that
        # passed on a manual re-run eleven minutes later; retrying is what that
        # re-run was doing by hand. 0 disables retrying (used by the
        # characterization tests so they stay fast and offline).
        self.api_retries = max(0, int(api_retries))
        self.retry_backoff_seconds = max(0.0, float(retry_backoff_seconds))

        # Setup logging
        logging.basicConfig(
            level=logging.DEBUG if verbose else logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            datefmt='%H:%M:%S'
        )
        self.logger = logging.getLogger(__name__)

        # Initialize LLM client via centralized provider router.
        self.client: Any
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
                self.client, _ = resolve_provider_client("auto", model=model)
            if self.client is None:
                from openai import OpenAI
                self.client = OpenAI(
                    base_url="https://openrouter.ai/api/v1",
                    api_key=os.getenv("OPENROUTER_API_KEY", ""))

        self.env = None
        self.tools: List[Dict[str, Any]] = [TERMINAL_TOOL_DEFINITION]

        print("🤖 Terminal-Bench Runner initialized")
        print(f"   Model: {self.model}")
        print(f"   Environment: {self.env_type}")
        if self.env_type != "local":
            print(f"   Image: {self.image}")
        print(f"   Max iterations: {self.max_iterations}")

    # -- environment management ----------------------------------------------

    def _create_env(self):
        print(f"🔧 Creating {self.env_type} environment...")
        self.env = create_environment(
            env_type=self.env_type,
            image=self.image,
            cwd=self.cwd,
            timeout=self.command_timeout,
        )
        print("✅ Environment ready")

    def _cleanup_env(self):
        if self.env is not None:
            if hasattr(self.env, 'cleanup'):
                self.env.cleanup()
            elif hasattr(self.env, 'stop'):
                self.env.stop()
            self.env = None

    def _execute_command(self, command: str, timeout: Optional[int] = None) -> Dict[str, Any]:
        if self.env is None:
            self._create_env()
        assert self.env is not None

        try:
            result = self.env.execute(command, timeout=timeout or self.command_timeout)
            return {
                "output": result.get("output", ""),
                "exit_code": result.get("returncode", 0),
                "error": None,
            }
        except Exception as e:
            return {
                "output": "",
                "exit_code": -1,
                "error": str(e),
            }

    def _run_script(self, script: str, label: str, timeout: Optional[int] = None) -> Dict[str, Any]:
        """Run a multi-line bash script via the environment.

        Writes the script to a tmp file on the host (or inside the container
        if we can), then executes it. For local environments we just write
        to /tmp and `bash` it; for containerised envs we fall back to a
        single `bash -c` invocation.
        """
        if not script or not script.strip():
            return {"output": "", "exit_code": 0, "error": None}

        # Use bash -c with the literal script. Escape single quotes safely.
        # For multi-line scripts this is robust on local and Docker (sh -c
        # multi-line works fine).
        safe = script.replace("'", "'\\''")
        cmd = f"bash -lc '{safe}'"
        return self._execute_command(cmd, timeout=timeout or self.command_timeout)

    # -- provider call -------------------------------------------------------

    def _call_model(self, api_messages: List[Dict[str, Any]]):
        """Call the provider, retrying transient failures with backoff.

        Returns ``(response, error)``. Exactly one of the two is ``None``.
        ``error`` is the :func:`_error_payload` dict describing the last
        exception after ``1 + api_retries`` attempts.

        This is the seam that closes D1: the caller can no longer confuse
        "the provider was unreachable" with "the agent failed the task",
        because the exception is *returned* rather than logged and dropped.
        """
        api_kwargs: Dict[str, Any] = {
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

        attempts = 1 + self.api_retries
        last_exc: Optional[BaseException] = None
        for attempt in range(1, attempts + 1):
            try:
                return self.client.chat.completions.create(**api_kwargs), None
            except Exception as e:  # noqa: BLE001 — any provider failure
                last_exc = e
                self.logger.warning(
                    "provider call failed (attempt %d/%d): %s: %s",
                    attempt, attempts, type(e).__name__, e,
                )
                if attempt < attempts and self.retry_backoff_seconds > 0:
                    time.sleep(self.retry_backoff_seconds * (2 ** (attempt - 1)))

        assert last_exc is not None
        return None, _error_payload(last_exc, attempts=attempts)

    # -- trajectory formatting (mirrors mini_swe_runner.py) ------------------

    def _format_tools_for_system_message(self) -> str:
        formatted_tools = []
        for tool in self.tools:
            func = tool["function"]
            formatted_tools.append({
                "name": func["name"],
                "description": func.get("description", ""),
                "parameters": func.get("parameters", {}),
                "required": None,
            })
        return json.dumps(formatted_tools, ensure_ascii=False)

    def _convert_to_hermes_format(
        self,
        messages: List[Dict[str, Any]],
        user_query: str,
        completed: bool,
    ) -> List[Dict[str, Any]]:
        trajectory = []

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

        i = 1
        while i < len(messages):
            msg = messages[i]

            if msg["role"] == "assistant":
                if "tool_calls" in msg and msg["tool_calls"]:
                    content = ""
                    if msg.get("reasoning"):
                        content = f"<think>{msg['reasoning']}</think>"
                    if msg.get("content"):
                        content += msg["content"] + "\n"

                    for tool_call in msg["tool_calls"]:
                        if not tool_call or not isinstance(tool_call, dict):
                            continue
                        try:
                            arguments = json.loads(tool_call["function"]["arguments"]) \
                                if isinstance(tool_call["function"]["arguments"], str) \
                                else tool_call["function"]["arguments"]
                        except json.JSONDecodeError:
                            arguments = {}

                        tool_call_json = {
                            "name": tool_call["function"]["name"],
                            "arguments": arguments,
                        }
                        content += f"<tool_call>\n{json.dumps(tool_call_json, ensure_ascii=False)}\n</tool_call>\n"

                    trajectory.append({"from": "gpt", "value": content.rstrip()})

                    tool_responses = []
                    j = i + 1
                    while j < len(messages) and messages[j]["role"] == "tool":
                        tool_msg = messages[j]
                        tool_content = tool_msg["content"]
                        try:
                            if tool_content.strip().startswith(("{", "[")):
                                tool_content = json.loads(tool_content)
                        except (json.JSONDecodeError, AttributeError):
                            pass

                        tool_response = "<tool_response>\n"
                        tool_response += json.dumps({
                            "tool_call_id": tool_msg.get("tool_call_id", ""),
                            "name": msg["tool_calls"][len(tool_responses)]["function"]["name"]
                                if len(tool_responses) < len(msg["tool_calls"]) else "unknown",
                            "content": tool_content,
                        }, ensure_ascii=False)
                        tool_response += "\n</tool_response>"
                        tool_responses.append(tool_response)
                        j += 1

                    if tool_responses:
                        trajectory.append({"from": "tool", "value": "\n".join(tool_responses)})
                        i = j - 1
                else:
                    content = ""
                    if msg.get("reasoning"):
                        content = f"<think>{msg['reasoning']}</think>"
                    content += msg.get("content") or ""
                    trajectory.append({"from": "gpt", "value": content})
            elif msg["role"] == "user":
                trajectory.append({"from": "human", "value": msg["content"]})
            i += 1

        return trajectory

    # -- per-task pipeline ---------------------------------------------------

    def run_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """
        Run a single Terminal-Bench task dict and score it.

        Pipeline:
          1. setup_script  (prepares the environment)
          2. agent loop on `instruction` (until completion signal or max iters)
          3. test_script   (verifies the agent's work; exit 0 == pass)

        Every returned row carries ``status`` and ``scored``. ``scored`` is
        True only when the agent actually got its turn and ``test_script``
        decided the outcome; in that case ``score`` is 0 or 1. When the run
        could not be attempted (``setup_failed``, ``provider_error``) the row
        keeps ``score: None`` and the diagnostic, because an unmeasured task
        is ABSENT, not a zero.
        """
        task_id = task.get("id", str(uuid.uuid4())[:8])
        instruction = task["instruction"]
        setup_script = task.get("setup_script", "")
        test_script = task["test_script"]
        tags = task.get("tags", [])

        print(f"\n{'=' * 60}")
        print(f"📝 Task: {task_id}  (tags={tags})")
        print(f"   Instruction: {instruction[:100]}{'...' if len(instruction) > 100 else ''}")
        print(f"{'=' * 60}")

        self._create_env()

        # 1) setup
        if setup_script.strip():
            print("⚙️  Running setup_script...")
            setup_result = self._run_script(setup_script, "setup")
            print(f"   setup exit_code={setup_result['exit_code']}")
            if setup_result["exit_code"] != 0:
                self._cleanup_env()
                # The environment was never prepared, so the agent never had a
                # fair attempt. Not a score — an unrunnable task.
                return {
                    "task_id": task_id,
                    "tags": tags,
                    "instruction": instruction,
                    "setup_exit_code": setup_result["exit_code"],
                    "test_exit_code": -1,
                    "score": None,
                    "scored": False,
                    "status": STATUS_SETUP_FAILED,
                    "completed": False,
                    "api_calls": 0,
                    "error": {
                        "type": "SetupScriptFailed",
                        "message": (
                            f"setup_script exited {setup_result['exit_code']}: "
                            f"{setup_result['output'][:500]}"
                        ),
                        "attempts": 1,
                    },
                    "conversations": [],
                    "metadata": {
                        "model": self.model,
                        "env_type": self.env_type,
                        "timestamp": datetime.now().isoformat(),
                    },
                }

        # 2) agent
        messages: List[Dict[str, Any]] = [{"role": "user", "content": instruction}]
        system_prompt = """You are an AI agent that can execute bash commands to complete tasks.

When you need to run commands, use the 'terminal' tool with your bash command.

**Important:**
- When you have completed the task successfully, run: echo "TERMINAL_BENCH_FINAL_OUTPUT" followed by a summary
- Be concise and efficient in your approach
- Install any needed tools with apt-get or pip
- Avoid interactive commands (no vim, nano, less, etc.)

Complete the user's task step by step."""

        api_call_count = 0
        completed = False
        provider_error: Optional[Dict[str, Any]] = None

        try:
            while api_call_count < self.max_iterations:
                api_call_count += 1
                print(f"\n🔄 API call #{api_call_count}/{self.max_iterations}")

                api_messages = [{"role": "system", "content": system_prompt}] + messages
                response, call_error = self._call_model(api_messages)
                if call_error is not None:
                    # D1: keep the reason. A provider failure is an
                    # infrastructure fact about the run, not evidence about the
                    # agent, and the artifact has to say which one it was.
                    self.logger.error(
                        "API call failed after %d attempt(s): %s: %s",
                        call_error["attempts"], call_error["type"], call_error["message"],
                    )
                    print(
                        f"   ❌ provider error after {call_error['attempts']} attempt(s): "
                        f"{call_error['type']}: {call_error['message'][:160]}"
                    )
                    provider_error = call_error
                    break

                assistant_message = response.choices[0].message

                if assistant_message.content:
                    print(f"🤖 Assistant: {assistant_message.content[:100]}...")

                if assistant_message.tool_calls:
                    print(f"🔧 Tool calls: {len(assistant_message.tool_calls)}")
                    messages.append({
                        "role": "assistant",
                        "content": assistant_message.content,
                        "tool_calls": [
                            {
                                "id": tc.id,
                                "type": tc.type,
                                "function": {
                                    "name": tc.function.name,
                                    "arguments": tc.function.arguments,
                                },
                            }
                            for tc in assistant_message.tool_calls
                        ],
                    })

                    for tc in assistant_message.tool_calls:
                        try:
                            args = json.loads(tc.function.arguments)
                        except json.JSONDecodeError:
                            args = {}
                        command = args.get("command", "echo 'No command provided'")
                        timeout = args.get("timeout", self.command_timeout)

                        print(f"   📞 terminal: {command[:60]}...")
                        result = self._execute_command(command, timeout)

                        result_json = json.dumps({
                            "content": {
                                "output": result["output"],
                                "exit_code": result["exit_code"],
                                "error": result["error"],
                            }
                        }, ensure_ascii=False)

                        if "TERMINAL_BENCH_FINAL_OUTPUT" in result["output"]:
                            print("   ✅ Task completion signal detected!")
                            completed = True

                        messages.append(make_tool_result_message(
                            tc.function.name, result_json, tc.id,
                        ))

                        print(f"   ✅ exit_code={result['exit_code']}, output={len(result['output'])} chars")

                    if completed:
                        break
                else:
                    final_response = assistant_message.content or ""
                    messages.append({
                        "role": "assistant",
                        "content": final_response,
                    })
                    completed = True
                    print("🎉 Agent finished (no more tool calls)")
                    break

            if api_call_count >= self.max_iterations and not completed:
                print(f"⚠️  Reached max iterations ({self.max_iterations})")
        finally:
            # 3) test_script — ALWAYS run, even when the provider errored.
            #    Its exit code is kept as a diagnostic either way; what the
            #    provider error changes is whether that exit code is allowed
            #    to become a *score*.
            pass

        # Run the verifier
        print("🧪 Running test_script...")
        test_result = self._run_script(test_script, "test")
        test_exit_code = test_result["exit_code"]

        if provider_error is not None:
            # D1: the agent never completed its turn, so test_script is
            # measuring an unfinished run. Record it, refuse to score it.
            status = STATUS_PROVIDER_ERROR
            scored = False
            score: Optional[int] = None
            print(
                f"   test exit_code={test_exit_code}  ->  UNSCORED "
                f"({STATUS_PROVIDER_ERROR}); an unmeasured task is ABSENT, not 0"
            )
        else:
            status = STATUS_SCORED
            scored = True
            score = 1 if test_exit_code == 0 else 0
            print(f"   test exit_code={test_exit_code}  ->  score={score}")

        # Cleanup
        self._cleanup_env()

        trajectory = self._convert_to_hermes_format(messages, instruction, completed)

        return {
            "task_id": task_id,
            "tags": tags,
            "instruction": instruction,
            "setup_exit_code": 0,
            "test_exit_code": test_exit_code,
            "test_output": test_result["output"][:2000],
            "score": score,
            "scored": scored,
            "status": status,
            "completed": completed,
            "api_calls": api_call_count,
            "error": provider_error,
            "conversations": trajectory,
            "metadata": {
                "model": self.model,
                "env_type": self.env_type,
                "timestamp": datetime.now().isoformat(),
            },
        }

    # -- batch entrypoint ----------------------------------------------------

    @staticmethod
    def sidecar_paths(output_file: str) -> Dict[str, str]:
        """Return the sidecar paths derived from ``output_file``.

        * ``unscored`` — rows that are not measurements of the agent.
        * ``summary`` — the batch summary that used to be appended to the
          results JSONL as a ``__summary__`` row (see D2).
        """
        p = Path(output_file)
        stem = p.name[: -len(p.suffix)] if p.suffix else p.name
        return {
            "unscored": str(p.with_name(f"{stem}.unscored.jsonl")),
            "summary": str(p.with_name(f"{stem}.summary.json")),
        }

    def run_batch(
        self,
        tasks: List[Dict[str, Any]],
        output_file: str = "terminal-bench-results.jsonl",
        include_summary_row: bool = False,
    ) -> Dict[str, Any]:
        """Run all tasks sequentially, write the artifacts, return a summary.

        Artifacts written next to ``output_file``:

        * ``output_file`` — **scored task rows only**, one JSON object per
          line. This is the file
          ``research_fabric.verifier.terminal_bench.verify`` grades, so it
          must contain nothing but measurements: that verifier counts every
          row and treats a row without a ``score`` as a failure (D2).
        * ``<stem>.unscored.jsonl`` — every task that could not be scored
          (provider error, setup failure, runner exception), with its full
          diagnostic. Failures are preserved, never counted.
        * ``<stem>.summary.json`` — the batch summary.

        ``include_summary_row=True`` also appends the legacy
        ``{"__summary__": ...}`` row to ``output_file``. It is off by default
        because that row is what made a recorded 1/1 run grade as 0.5000
        against ``ABSOLUTE_FLOOR = 0.80``.
        """
        scored_rows: List[Dict[str, Any]] = []
        unscored_rows: List[Dict[str, Any]] = []
        n = len(tasks)
        sidecars = self.sidecar_paths(output_file)
        print(f"\n📦 Running Terminal-Bench batch: {n} task(s)")
        print(f"📁 Scored results: {output_file}")
        print(f"📁 Unscored rows:  {sidecars['unscored']}")

        with open(output_file, "w", encoding="utf-8") as scored_f, \
                open(sidecars["unscored"], "w", encoding="utf-8") as unscored_f:
            for i, task in enumerate(tasks, 1):
                print(f"\n{'=' * 60}")
                print(f"📋 Task {i}/{n}: {task.get('id', '?')}")
                print(f"{'=' * 60}")
                try:
                    result = self.run_task(task)
                except Exception as e:
                    self.logger.error(f"Error on task {i}: {e}")
                    result = {
                        "task_id": task.get("id", f"task_{i}"),
                        "tags": task.get("tags", []),
                        "instruction": task.get("instruction", ""),
                        "score": None,
                        "scored": False,
                        "status": STATUS_RUNNER_ERROR,
                        "completed": False,
                        "api_calls": 0,
                        "error": _error_payload(e),
                        "conversations": [],
                        "metadata": {
                            "model": self.model,
                            "env_type": self.env_type,
                            "timestamp": datetime.now().isoformat(),
                        },
                    }
                line = json.dumps(result, ensure_ascii=False) + "\n"
                if result.get("scored"):
                    scored_rows.append(result)
                    scored_f.write(line)
                    scored_f.flush()
                else:
                    unscored_rows.append(result)
                    unscored_f.write(line)
                    unscored_f.flush()

        # Summary — computed over SCORED rows only. Unscored tasks are
        # reported separately and never enter the denominator.
        passed = sum(1 for r in scored_rows if r.get("score") == 1)
        n_scored = len(scored_rows)
        # ABSENT, never zero: with nothing scored there is no accuracy to
        # report, and 0.0 would read as "everything was tried and failed".
        accuracy: Optional[float] = (passed / n_scored) if n_scored else None

        by_tag: Dict[str, Dict[str, int]] = {}
        for r in scored_rows:
            for t in r.get("tags", []) or ["<untagged>"]:
                by_tag.setdefault(t, {"passed": 0, "total": 0})
                by_tag[t]["total"] += 1
                if r.get("score") == 1:
                    by_tag[t]["passed"] += 1

        unscored_by_status: Dict[str, int] = {}
        for r in unscored_rows:
            key = str(r.get("status", STATUS_RUNNER_ERROR))
            unscored_by_status[key] = unscored_by_status.get(key, 0) + 1

        summary = {
            "tasks_attempted": n,
            "scored": n_scored,
            "unscored": len(unscored_rows),
            "unscored_by_status": unscored_by_status,
            "passed": passed,
            "accuracy": accuracy,
            "accuracy_basis": "scored_tasks_only",
            # ``total`` is retained for readers of the old summary shape and
            # now means "tasks that produced a score", matching ``accuracy``.
            "total": n_scored,
            "by_tag": {
                t: {**v, "accuracy": v["passed"] / v["total"] if v["total"] else None}
                for t, v in by_tag.items()
            },
            "model": self.model,
            "env_type": self.env_type,
            "results_path": str(output_file),
            "unscored_path": sidecars["unscored"],
            "timestamp": datetime.now().isoformat(),
            "note": (
                "Runner sanity fixture unless --task_dir pointed at the "
                "canonical Terminal-Bench corpus; not an official score."
            ),
        }

        with open(sidecars["summary"], "w", encoding="utf-8") as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)

        if include_summary_row:
            with open(output_file, "a", encoding="utf-8") as f:
                f.write(json.dumps({"__summary__": summary}, ensure_ascii=False) + "\n")

        acc_text = "ABSENT (nothing scored)" if accuracy is None else f"{accuracy:.1%}"
        print(f"\n{'=' * 60}")
        print("🏁 Terminal-Bench batch complete")
        print(f"   Attempted: {summary['tasks_attempted']}")
        print(f"   Scored:    {summary['scored']}")
        print(f"   Unscored:  {summary['unscored']}  {unscored_by_status or ''}")
        print(f"   Passed:    {summary['passed']}")
        print(f"   Accuracy:  {acc_text}  (over scored tasks only)")
        for tag, stats in summary["by_tag"].items():
            tag_acc = stats["accuracy"]
            tag_text = "ABSENT" if tag_acc is None else f"{tag_acc:.0%}"
            print(f"   - {tag:12s} {stats['passed']}/{stats['total']}  ({tag_text})")
        print(f"📁 Results written to: {output_file}")
        print(f"📁 Summary written to: {sidecars['summary']}")
        print(f"{'=' * 60}")
        return summary


# ============================================================================
# CLI Interface
# ============================================================================

def main(
    task_dir: Optional[str] = None,
    limit: Optional[int] = None,
    tags: Optional[str] = None,
    output: str = "terminal-bench-results.jsonl",
    model: str = "kimi-k3",
    base_url: Optional[str] = None,
    api_key: Optional[str] = None,
    env: str = "local",
    image: str = "python:3.11-slim",
    cwd: str = "/tmp",
    max_iterations: int = 10,
    timeout: int = 60,
    verbose: bool = False,
    api_retries: int = 2,
    retry_backoff_seconds: float = 2.0,
    include_summary_row: bool = False,
):
    """
    Run Terminal-Bench tasks with Hermes trajectory format output.

    Args:
        task_dir:   Directory of Terminal-Bench YAML files. If omitted, the
                    built-in SAMPLE_TASKS are used.
        limit:      Cap the number of tasks run.
        tags:       Comma-separated list of tags to include (e.g. "easy,file").
        output:     Output JSONL path (default terminal-bench-results.jsonl).
        model:      Model name (default kimi-k3).
        base_url:   API base URL (optional, uses env vars if not provided).
        api_key:    API key (optional, uses env vars).
        env:        Environment type — local, docker, or modal.
        image:      Docker/Modal image (ignored for local).
        cwd:        Working directory.
        max_iterations: Max tool-calling iterations per task.
        timeout:    Per-command timeout in seconds.
        verbose:    Verbose logging.
        api_retries: Extra attempts after the first for a failed provider
                    call (default 2). 0 disables retrying.
        retry_backoff_seconds: Base delay between provider retries; doubles
                    per attempt.
        include_summary_row: Also append the legacy ``{"__summary__": ...}``
                    row to the results JSONL. Off by default — that row is
                    graded as a failed task by the ratchet verifier (D2).

    Exit code:
        2 when tasks were attempted but none could be scored, so a run in
        which the provider was unreachable cannot be mistaken for a run in
        which the agent scored 0.

    Examples:
        # Quick sanity check (1 built-in task, Kimi K3, local env)
        python -m benchmarks.terminal_bench_runner --limit 1 --model kimi-k3

        # Run against a directory of YAML tasks
        python -m benchmarks.terminal_bench_runner --task_dir tasks/ --limit 10 --model kimi-k3

        # Filter by tag
        python -m benchmarks.terminal_bench_runner --task_dir tasks/ --tags easy --model kimi-k3
    """
    print("🚀 Terminal-Bench Runner with Hermes Trajectory Format")
    print("=" * 60)

    # Load tasks
    tasks = load_terminal_bench_tasks(task_dir)

    # Filter by tags if requested
    if tags:
        wanted = {t.strip() for t in tags.split(",") if t.strip()}
        tasks = [t for t in tasks if wanted.intersection(t.get("tags") or [])]
        print(f"🔎 After tag filter {sorted(wanted)}: {len(tasks)} task(s)")

    # Apply limit
    if limit is not None and limit >= 0:
        tasks = tasks[:limit]
        print(f"🔢 Limited to first {len(tasks)} task(s)")

    if not tasks:
        print("❌ No tasks to run after filtering/limiting. Exiting.")
        return

    # Initialize runner
    runner = TerminalBenchRunner(
        model=model,
        base_url=base_url,
        api_key=api_key,
        env_type=env,
        image=image,
        cwd=cwd,
        max_iterations=max_iterations,
        command_timeout=timeout,
        verbose=verbose,
        api_retries=api_retries,
        retry_backoff_seconds=retry_backoff_seconds,
    )

    summary = runner.run_batch(
        tasks, output_file=output, include_summary_row=include_summary_row
    )

    # Final concise accuracy line for easy grepping. ABSENT rather than
    # 0.0000 when nothing was scored (see D1).
    accuracy = summary["accuracy"]
    acc_text = "ABSENT" if accuracy is None else f"{accuracy:.4f}"
    print(
        f"\n📊 SUMMARY accuracy={acc_text}  passed={summary['passed']}/{summary['scored']}"
        f"  unscored={summary['unscored']} {summary['unscored_by_status'] or ''}"
    )

    if summary["scored"] == 0 and summary["tasks_attempted"] > 0:
        print(
            "❌ No task produced a score — this run measured nothing. "
            f"See {summary['unscored_path']} for why."
        )
        sys.exit(2)


if __name__ == "__main__":
    fire.Fire(main)
