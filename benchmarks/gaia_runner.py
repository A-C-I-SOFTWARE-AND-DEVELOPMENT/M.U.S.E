#!/usr/bin/env python3
"""
GAIA Runner for MUSE

GAIA is a general-agent benchmark (https://huggingface.co/datasets/gaia-benchmark/GAIA).
3 levels, 466 questions total (165 validation, 301 test). Each question has:
  - task_id            unique id
  - Question           the user-facing prompt
  - Level              1, 2, or 3 (difficulty)
  - Final answer       the gold answer (string)
  - file_name          optional attachment filename
  - Annotator Metadata dict (Steps, Number of steps, Tools, ...)

The runner mirrors mini_swe_runner.py's structure (env factory, MiniSWERunner-style
class, MINI_SWE_AGENT_FINAL_OUTPUT completion detection) and only swaps out the
dataset loader and the scoring rule (exact-match against Final answer,
case-insensitive, whitespace-normalized).

Dataset loading tries the official `gaia-benchmark/GAIA` (gated, needs HF_TOKEN)
first, then falls back to a public mirror so the runner is usable out-of-the-box
when a token isn't available.

Usage:
    python -m benchmarks.gaia_runner --level 1 --limit 10 \
        --model kimi-k3 --base_url https://api.kimi.com/coding/v1

Output:
    results.jsonl with {task_id, question, level, model_answer, gold_answer,
                        correct, api_calls, turns}
    Plus a printed summary: accuracy, avg_api_calls, avg_turns.
"""

import json
import logging
import os
import re
import sys
import time
import uuid
from collections import Counter
from enum import Enum
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import fire
from dotenv import load_dotenv
from agent.tool_dispatch_helpers import make_tool_result_message

# Load environment variables (KIMI_API_KEY, OPENROUTER_API_KEY, HF_TOKEN, ...).
load_dotenv()


# ============================================================================
# Provider Temperature Helper
# ============================================================================

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
        raise ValueError(
            f"Unknown environment type: {env_type}. Use 'local', 'docker', or 'modal'"
        )


# ============================================================================
# GAIA Dataset Loader
# ============================================================================

# Public mirror fallback. The official gaia-benchmark/GAIA is gated; this mirror
# (a community re-upload of the same schema) lets the runner work without a
# HuggingFace token. ~127 validation rows vs 165 in the official set, but
# identical column schema.
PUBLIC_GAIA_MIRROR = "sayan1101/gaia_filtered_text_only"
OFFICIAL_GAIA_REPO = "gaia-benchmark/GAIA"
OFFICIAL_GAIA_CONFIG = "2023_all"


def _coerce_level(level_val: Any) -> Optional[int]:
    """Coerce a GAIA Level field (str/int) to an int in {1,2,3}, else None."""
    if level_val is None:
        return None
    if isinstance(level_val, int):
        return level_val if level_val in (1, 2, 3) else None
    s = str(level_val).strip()
    # GAIA stores it as "1", "2", "3" or sometimes as an int-string.
    m = re.search(r"[123]", s)
    if m:
        try:
            return int(m.group(0))
        except ValueError:
            return None
    return None


def _row_to_task(row: Dict[str, Any], idx: int) -> Dict[str, Any]:
    """Normalize a dataset row (dict) into a GAIA task dict."""
    task_id = str(row.get("task_id") or row.get("Task ID") or f"gaia-{idx}")
    question = (
        row.get("Question")
        or row.get("question")
        or row.get("query")
        or ""
    )
    level = _coerce_level(row.get("Level") or row.get("level"))
    final_answer = (
        row.get("Final answer")
        or row.get("final_answer")
        or row.get("answer")
        or ""
    )
    file_name = row.get("file_name") or row.get("file") or None
    meta = row.get("Annotator Metadata") or row.get("metadata") or {}
    # Attachments live next to the dataset on HF Hub under a `files/` dir; for
    # the runner we just record the filename so callers can fetch separately.
    return {
        "task_id": task_id,
        "question": str(question),
        "level": level,
        "final_answer": str(final_answer),
        "file_name": file_name,
        "annotator_metadata": meta,
    }


def _load_via_datasets(split: str, level: Optional[int]) -> List[Dict[str, Any]]:
    """Load GAIA via the `datasets` library (official gated repo)."""
    from datasets import load_dataset
    ds = load_dataset(OFFICIAL_GAIA_REPO, OFFICIAL_GAIA_CONFIG, split=split)
    tasks = [_row_to_task(dict(ds[i]), i) for i in range(len(ds))]
    if level is not None:
        tasks = [t for t in tasks if t["level"] == level]
    return tasks


def _load_via_mirror(split: str, level: Optional[int]) -> List[Dict[str, Any]]:
    """Load GAIA via a public mirror (no HF_TOKEN required)."""
    from datasets import load_dataset
    ds = load_dataset(PUBLIC_GAIA_MIRROR, split=split)
    tasks = [_row_to_task(dict(ds[i]), i) for i in range(len(ds))]
    if level is not None:
        tasks = [t for t in tasks if t["level"] == level]
    return tasks


def load_gaia_dataset(
    split: str = "validation",
    level: Optional[int] = 1,
) -> List[Dict[str, Any]]:
    """
    Load the GAIA benchmark.

    Args:
        split: "validation" or "test" (test has no gold answers publicly).
        level: 1, 2, or 3 to filter by difficulty, or None for all.

    Returns:
        List of task dicts, each with keys:
            task_id, question, level, final_answer, file_name, annotator_metadata

    Tries the official `gaia-benchmark/GAIA` (gated, needs HF_TOKEN) first, then
    falls back to a public mirror. If `datasets` is not installed, downloads
    the validation JSONL directly from the mirror's raw URL.
    """
    if level is not None and level not in (1, 2, 3):
        raise ValueError(f"level must be 1, 2, 3, or None; got {level!r}")
    if split not in ("validation", "test"):
        raise ValueError(f"split must be 'validation' or 'test'; got {split!r}")

    # 1. Try the official dataset if datasets is installed.
    try:
        return _load_via_datasets(split, level)
    except Exception as official_err:
        official_msg = f"{type(official_err).__name__}: {str(official_err)[:200]}"

    # 2. Try the public mirror via datasets.
    try:
        return _load_via_mirror(split, level)
    except Exception as mirror_err:
        mirror_msg = f"{type(mirror_err).__name__}: {str(mirror_err)[:200]}"

    # 3. Last-resort: download the validation JSONL directly. The mirror only
    #    ships parquet, so this path is rarely hit, but keep it for resilience.
    try:
        import urllib.request
        url = (
            f"https://huggingface.co/datasets/{PUBLIC_GAIA_MIRROR}/resolve/main/"
            f"data/{split}-00000-of-00001.parquet"
        )
        with urllib.request.urlopen(url) as resp:
            raw = resp.read()
        # Write to a temp file and let pyarrow/pandas read it.
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".parquet", delete=False) as tmp:
            tmp.write(raw)
            tmp_path = tmp.name
        try:
            try:
                import pandas as pd
                df = pd.read_parquet(tmp_path)
                rows = df.to_dict(orient="records")
            except ImportError:
                import pyarrow.parquet as pq
                rows = pq.read_table(tmp_path).to_pylist()
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
        tasks = [_row_to_task(r, i) for i, r in enumerate(rows)]
        if level is not None:
            tasks = [t for t in tasks if t["level"] == level]
        return tasks
    except Exception as final_err:
        final_msg = f"{type(final_err).__name__}: {str(final_err)[:200]}"

    # All paths failed.
    raise RuntimeError(
        "Could not load GAIA dataset. Tried:\n"
        f"  1. Official {OFFICIAL_GAIA_REPO}: {official_msg}\n"
        f"  2. Public mirror {PUBLIC_GAIA_MIRROR}: {mirror_msg}\n"
        f"  3. Direct parquet download: {final_msg}\n"
        "Try `uv pip install datasets` and/or set the HF_TOKEN env var."
    )


# ============================================================================
# Scoring
# ============================================================================

_WHITESPACE_RE = re.compile(r"\s+")


def _normalize_answer(ans: Any) -> str:
    """Lowercase, strip, collapse whitespace — the GAIA leaderboard's standard."""
    if ans is None:
        return ""
    s = str(ans)
    s = s.strip()
    s = _WHITESPACE_RE.sub(" ", s)
    return s.lower()


def exact_match_score(model_answer: Any, gold_answer: Any) -> bool:
    """Exact-match against Final answer (case-insensitive, whitespace-normalized).

    Kept byte-for-byte as the GAIA leaderboard's own rule. Do not widen it: a
    leaderboard number computed with a friendlier comparison is not comparable to
    anyone else's. `grade_answer` is the wrapper that adds unit interpretation.
    """
    return _normalize_answer(model_answer) == _normalize_answer(gold_answer)


def grade_answer(model_answer: Any, gold_answer: Any, *, context: Any = None):
    """Grade with unit interpretation applied BEFORE the comparison (§1 p4, §11, §12).

    The driving failure: a Level-1 answer of ``17000`` was graded wrong against a
    gold field of ``17`` after six correct turns. The work was right and the
    grader was unit-blind. `exact_match_score` alone cannot tell a unit
    convention from a wrong answer — and, in the other direction, it reports that
    ``17 M`` equals ``17 m``.

    Returns the validator's three-way :class:`Verdict`. ``AMBIGUOUS_UNIT`` is not
    a pass and not a fail: it is a grading defect to surface, because deciding it
    silently in either direction is how the original bug happened. Callers that
    need a bool should treat only ``MATCH`` as correct and report the ambiguous
    count separately rather than folding it into either bucket.

    Falls back to the strict leaderboard rule if the grading tools are absent, so
    a missing optional dependency degrades to today's behaviour rather than
    crashing a benchmark run.
    """
    try:
        from tools.grading.validator import Verdict, validate_answer
    except ImportError:
        return (
            _GradeShim.MATCH
            if exact_match_score(model_answer, gold_answer)
            else _GradeShim.MISMATCH
        )
    result = validate_answer(model_answer, gold_answer, context)
    return result.verdict if not isinstance(result, tuple) else result[0]


class _GradeShim(str, Enum):
    """Mirrors tools.grading.validator.Verdict when that module is unavailable."""

    MATCH = "match"
    MISMATCH = "mismatch"
    AMBIGUOUS_UNIT = "ambiguous_unit"


def extract_final_answer(text: str) -> str:
    """Best-effort extraction of the final answer from the agent's final output.

    Prefers text that follows MINI_SWE_AGENT_FINAL_OUTPUT, falling back to the
    last non-empty line of ``text``.
    """
    if not text:
        return ""
    # Prefer text after the final-output marker.
    if "MINI_SWE_AGENT_FINAL_OUTPUT" in text:
        tail = text.split("MINI_SWE_AGENT_FINAL_OUTPUT", 1)[1]
        return tail.strip()
    # Otherwise: last non-empty line.
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    return lines[-1] if lines else text.strip()


# ============================================================================
# GAIA Runner
# ============================================================================

class GAIARunner:
    """
    Agent runner that solves GAIA questions using Hermes-Agent's execution
    environments and scores answers with exact-match against the gold answer.
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

        # Initialize LLM client (OpenAI-compatible).
        self.client: Any
        if api_key or base_url:
            from openai import OpenAI
            client_kwargs: Dict[str, Any] = {
                "base_url": base_url or "https://openrouter.ai/api/v1",
                "api_key": api_key or os.getenv(
                    "KIMI_API_KEY",
                    os.getenv("OPENROUTER_API_KEY",
                              os.getenv("ANTHROPIC_API_KEY",
                                        os.getenv("OPENAI_API_KEY", ""))),
                ),
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
                    api_key=os.getenv("OPENROUTER_API_KEY", ""),
                )

        # Environment will be created per-task.
        self.env = None
        # Tool definition.
        self.tools: List[Dict[str, Any]] = [TERMINAL_TOOL_DEFINITION]

        print("🤖 GAIA Runner initialized")
        print(f"   Model: {self.model}")
        print(f"   Environment: {self.env_type}")
        if self.env_type != "local":
            print(f"   Image: {self.image}")
        print(f"   Max iterations: {self.max_iterations}")

    # ---- environment plumbing (mirrors MiniSWERunner) --------------------

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

    # ---- task execution -------------------------------------------------

    def run_task(
        self,
        task_id: str,
        question: str,
        level: Optional[int] = None,
        gold_answer: str = "",
        file_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Run a single GAIA task and return a result dict.

        Returns:
            {
                "task_id", "question", "level", "model_answer", "gold_answer",
                "correct", "api_calls", "turns", "completed", "elapsed_s",
                "trajectory" (list[dict])
            }
        """
        # If a file attachment is referenced, mention it in the prompt so the
        # agent can try to download/use it. The HuggingFace dataset stores
        # attachments under <repo>/2023_all/<split>/<task_id>/<file_name>.
        attachment_note = ""
        if file_name:
            attachment_note = (
                f"\n\nThis task has an attachment: {file_name}. "
                "If the file is available locally in your working directory, "
                "use it; otherwise try to download it from "
                f"https://huggingface.co/datasets/{OFFICIAL_GAIA_REPO}/resolve/main/"
                f"2023_all/validation/{task_id}/{file_name}."
            )

        user_query = (
            f"GAIA task (level {level}, id {task_id}):\n\n{question}{attachment_note}\n\n"
            "Solve the task using the terminal tool. When you have the final answer, "
            "run a command like:\n"
            "    echo \"MINI_SWE_AGENT_FINAL_OUTPUT: <your final answer>\"\n"
            "so the harness can pick it up."
        )

        print(f"\n{'='*60}")
        print(f"📝 Task {task_id} (level {level})")
        snippet = question[:80].replace("\n", " ")
        print(f"   Q: {snippet}{'...' if len(question) > 80 else ''}")
        print(f"{'='*60}")

        self._create_env()
        start_ts = time.time()
        messages: List[Dict[str, Any]] = [{"role": "user", "content": user_query}]

        system_prompt = """You are an AI agent that can execute bash commands to complete tasks.

When you need to run commands, use the 'terminal' tool with your bash command.

**Important:**
- When you have completed the task and are ready to give your final answer, run a command like:
    echo "MINI_SWE_AGENT_FINAL_OUTPUT: <your final answer>"
- Be concise and efficient in your approach
- Install any needed tools with apt-get or pip
- Avoid interactive commands (no vim, nano, less, etc.)
- For numeric answers, output just the number; for names, output just the name; for lists, comma-separate.

Complete the user's task step by step."""

        api_call_count = 0
        completed = False
        final_text = ""
        turns = 0  # number of assistant messages generated

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
                turns += 1

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

                        # Track the running final-output string for scoring.
                        if "MINI_SWE_AGENT_FINAL_OUTPUT" in result["output"]:
                            print("   ✅ Task completion signal detected!")
                            # Append the marker line to the running final text.
                            for ln in result["output"].splitlines():
                                if "MINI_SWE_AGENT_FINAL_OUTPUT" in ln:
                                    final_text += ln + "\n"
                                    break
                            completed = True

                        messages.append(make_tool_result_message(
                            tc.function.name, result_json, tc.id,
                        ))

                        print(
                            f"   ✅ exit_code={result['exit_code']}, "
                            f"output={len(result['output'])} chars"
                        )

                    if completed:
                        break
                else:
                    # No tool calls — final assistant message.
                    final_text += (assistant_message.content or "") + "\n"
                    messages.append({
                        "role": "assistant",
                        "content": assistant_message.content or "",
                    })
                    completed = True
                    print("🎉 Agent finished (no more tool calls)")
                    break

            if api_call_count >= self.max_iterations and not completed:
                print(f"⚠️  Reached max iterations ({self.max_iterations})")
        finally:
            self._cleanup_env()

        # Score: pull the answer out of `final_text` (prefers the marker line,
        # falls back to the last non-empty line).
        model_answer = extract_final_answer(final_text)
        # If we never got any text from the agent, leave a clear empty string
        # so the score is `False` rather than raising.
        correct = exact_match_score(model_answer, gold_answer)

        return {
            "task_id": task_id,
            "question": question,
            "level": level,
            "model_answer": model_answer,
            "gold_answer": gold_answer,
            "correct": bool(correct),
            "api_calls": api_call_count,
            "turns": turns,
            "completed": completed,
            "elapsed_s": round(time.time() - start_ts, 2),
        }

    # ---- batch driver ----------------------------------------------------

    def run_batch(
        self,
        tasks: List[Dict[str, Any]],
        output_file: str = "results.jsonl",
    ) -> List[Dict[str, Any]]:
        """
        Run a batch of GAIA tasks, write per-task results to JSONL, and return
        the list of result dicts.
        """
        results: List[Dict[str, Any]] = []

        print(f"\n📦 GAIA batch: {len(tasks)} task(s)")
        print(f"📁 Output: {output_file}")

        with open(output_file, "w", encoding="utf-8") as f:
            for i, t in enumerate(tasks, 1):
                print(f"\n{'='*60}")
                print(f"📋 Task {i}/{len(tasks)}: {t.get('task_id', '?')}")
                print(f"{'='*60}")
                try:
                    result = self.run_task(
                        task_id=t["task_id"],
                        question=t["question"],
                        level=t.get("level"),
                        gold_answer=t.get("final_answer", ""),
                        file_name=t.get("file_name"),
                    )
                except Exception as e:
                    self.logger.error(f"Error on task {i}: {e}")
                    result = {
                        "task_id": t.get("task_id", f"gaia-{i}"),
                        "question": t.get("question", ""),
                        "level": t.get("level"),
                        "model_answer": "",
                        "gold_answer": t.get("final_answer", ""),
                        "correct": False,
                        "api_calls": 0,
                        "turns": 0,
                        "completed": False,
                        "error": str(e),
                    }

                results.append(result)
                f.write(json.dumps(result, ensure_ascii=False) + "\n")
                f.flush()
                status = "✅" if result["correct"] else "❌"
                print(
                    f"{status} Task {i}: correct={result['correct']} "
                    f"api_calls={result['api_calls']} turns={result['turns']}"
                )

        self._print_summary(results)
        return results

    # ---- summary ---------------------------------------------------------

    @staticmethod
    def _print_summary(results: List[Dict[str, Any]]) -> None:
        if not results:
            print("\n📊 No results to summarize.")
            return
        n = len(results)
        correct = sum(1 for r in results if r.get("correct"))
        accuracy = correct / n if n else 0.0
        api_calls = [r.get("api_calls", 0) for r in results]
        turns = [r.get("turns", 0) for r in results]
        avg_api = sum(api_calls) / n if n else 0.0
        avg_turns = sum(turns) / n if n else 0.0
        by_level = Counter(r.get("level") for r in results)
        per_level_correct = Counter(
            r.get("level") for r in results if r.get("correct")
        )
        print("\n" + "=" * 60)
        print("📊 GAIA SUMMARY")
        print("=" * 60)
        print(f"  Total tasks      : {n}")
        print(f"  Correct          : {correct}")
        print(f"  Accuracy         : {accuracy:.3f} ({accuracy*100:.1f}%)")
        print(f"  Avg api_calls    : {avg_api:.2f}")
        print(f"  Avg turns        : {avg_turns:.2f}")
        if by_level:
            print("  Per-level accuracy:")
            for lvl in sorted(k for k in by_level if k is not None):
                lvl_total = by_level[lvl]
                lvl_correct = per_level_correct.get(lvl, 0)
                acc = lvl_correct / lvl_total if lvl_total else 0.0
                print(
                    f"    Level {lvl}: {lvl_correct}/{lvl_total} "
                    f"({acc*100:.1f}%)"
                )
        print("=" * 60)


# ============================================================================
# CLI
# ============================================================================

def main(
    level: Optional[int] = 1,
    limit: Optional[int] = 10,
    split: str = "validation",
    model: str = "kimi-k3",
    base_url: Optional[str] = "https://api.kimi.com/coding/v1",
    api_key: Optional[str] = None,
    env: str = "local",
    image: str = "python:3.11-slim",
    cwd: str = "/tmp",
    max_iterations: int = 15,
    timeout: int = 60,
    output_file: str = "results.jsonl",
    verbose: bool = False,
):
    """
    Run GAIA benchmark questions against an OpenAI-compatible model.

    Args:
        level: 1, 2, 3, or None for all levels.
        limit: Cap on number of tasks to run (None = all).
        split: Dataset split — "validation" (default) or "test".
        model: Model name for the OpenAI-compatible API.
        base_url: API base URL (defaults to Kimi).
        api_key: API key (defaults to KIMI_API_KEY / OPENROUTER_API_KEY / ...).
        env: Environment type — "local", "docker", or "modal".
        image: Docker/Modal image.
        cwd: Working directory.
        max_iterations: Max tool-calling iterations per task.
        timeout: Default command timeout (seconds).
        output_file: Path to JSONL results file.
        verbose: Verbose logging.

    Examples:
        python -m benchmarks.gaia_runner --level 1 --limit 10
        python -m benchmarks.gaia_runner --level 2 --model kimi-k3 \\
            --base_url https://api.kimi.com/coding/v1
    """
    print("🚀 GAIA Runner for MUSE")
    print("=" * 60)

    # 1. Load the dataset.
    print(f"📚 Loading GAIA split={split!r}, level={level!r} ...")
    try:
        tasks = load_gaia_dataset(split=split, level=level)
    except Exception as e:
        print(f"❌ Failed to load GAIA dataset: {e}")
        sys.exit(1)
    print(f"   Loaded {len(tasks)} task(s).")
    if limit is not None and limit > 0:
        tasks = tasks[:limit]
        print(f"   Limited to {len(tasks)} task(s).")

    if not tasks:
        print("❌ No tasks to run after filtering/limiting.")
        sys.exit(1)

    # 2. Initialize the runner.
    runner = GAIARunner(
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

    # 3. Run.
    runner.run_batch(tasks, output_file=output_file)
    print(f"\n📁 Results written to: {output_file}")


if __name__ == "__main__":
    fire.Fire(main)
