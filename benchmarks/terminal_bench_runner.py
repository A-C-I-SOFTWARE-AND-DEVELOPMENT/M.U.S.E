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
    ):
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
                return {
                    "task_id": task_id,
                    "tags": tags,
                    "instruction": instruction,
                    "setup_exit_code": setup_result["exit_code"],
                    "test_exit_code": -1,
                    "score": 0,
                    "completed": False,
                    "api_calls": 0,
                    "error": f"setup_script failed: {setup_result['output'][:200]}",
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

        try:
            while api_call_count < self.max_iterations:
                api_call_count += 1
                print(f"\n🔄 API call #{api_call_count}/{self.max_iterations}")

                api_messages = [{"role": "system", "content": system_prompt}] + messages
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
            # 3) test_script — ALWAYS run, even if agent errored,
            #    so we get a real score. The environment state is left
            #    intact for the verifier.
            pass

        # Run the verifier
        print("🧪 Running test_script...")
        test_result = self._run_script(test_script, "test")
        score = 1 if test_result["exit_code"] == 0 else 0
        print(f"   test exit_code={test_result['exit_code']}  ->  score={score}")

        # Cleanup
        self._cleanup_env()

        trajectory = self._convert_to_hermes_format(messages, instruction, completed)

        return {
            "task_id": task_id,
            "tags": tags,
            "instruction": instruction,
            "setup_exit_code": 0,
            "test_exit_code": test_result["exit_code"],
            "test_output": test_result["output"][:2000],
            "score": score,
            "completed": completed,
            "api_calls": api_call_count,
            "conversations": trajectory,
            "metadata": {
                "model": self.model,
                "env_type": self.env_type,
                "timestamp": datetime.now().isoformat(),
            },
        }

    # -- batch entrypoint ----------------------------------------------------

    def run_batch(
        self,
        tasks: List[Dict[str, Any]],
        output_file: str = "terminal-bench-results.jsonl",
    ) -> Dict[str, Any]:
        """
        Run all tasks sequentially, write results.jsonl, return a summary dict.
        """
        results: List[Dict[str, Any]] = []
        n = len(tasks)
        print(f"\n📦 Running Terminal-Bench batch: {n} task(s)")
        print(f"📁 Output: {output_file}")

        with open(output_file, "w", encoding="utf-8") as f:
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
                        "score": 0,
                        "completed": False,
                        "api_calls": 0,
                        "error": str(e),
                        "conversations": [],
                        "metadata": {
                            "model": self.model,
                            "env_type": self.env_type,
                            "timestamp": datetime.now().isoformat(),
                        },
                    }
                results.append(result)
                f.write(json.dumps(result, ensure_ascii=False) + "\n")
                f.flush()

        # Summary
        scores = [r.get("score", 0) for r in results]
        passed = sum(scores)
        accuracy = passed / len(results) if results else 0.0
        by_tag: Dict[str, Dict[str, int]] = {}
        for r in results:
            for t in r.get("tags", []) or ["<untagged>"]:
                by_tag.setdefault(t, {"passed": 0, "total": 0})
                by_tag[t]["total"] += 1
                if r.get("score", 0) == 1:
                    by_tag[t]["passed"] += 1

        summary = {
            "total": len(results),
            "passed": passed,
            "accuracy": accuracy,
            "by_tag": {
                t: {**v, "accuracy": v["passed"] / v["total"] if v["total"] else 0.0}
                for t, v in by_tag.items()
            },
            "model": self.model,
            "env_type": self.env_type,
            "timestamp": datetime.now().isoformat(),
        }

        # Append a summary line to the JSONL (read by humans / downstream tools)
        with open(output_file, "a", encoding="utf-8") as f:
            f.write(json.dumps({"__summary__": summary}, ensure_ascii=False) + "\n")

        print(f"\n{'=' * 60}")
        print(f"🏁 Terminal-Bench batch complete")
        print(f"   Total:    {summary['total']}")
        print(f"   Passed:   {summary['passed']}")
        print(f"   Accuracy: {summary['accuracy']:.1%}")
        for tag, stats in summary["by_tag"].items():
            print(f"   - {tag:12s} {stats['passed']}/{stats['total']}  ({stats['accuracy']:.0%})")
        print(f"📁 Results written to: {output_file}")
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
    )

    summary = runner.run_batch(tasks, output_file=output)

    # Final concise accuracy line for easy grepping
    print(f"\n📊 SUMMARY accuracy={summary['accuracy']:.4f}  passed={summary['passed']}/{summary['total']}")


if __name__ == "__main__":
    fire.Fire(main)
