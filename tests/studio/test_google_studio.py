from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "axiom_google_studio.py"


def run_script(*args: str, env: dict[str, str] | None = None) -> dict:
    merged_env = os.environ.copy()
    merged_env.update(env or {})
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=str(ROOT),
        text=True,
        capture_output=True,
        timeout=120,
        env=merged_env,
    )
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout)


def test_google_studio_check_reports_readiness_without_credentials() -> None:
    data = run_script("check", env={"GOOGLE_CLOUD_PROJECT": "", "GOOGLE_OAUTH_ACCESS_TOKEN": ""})
    assert data["repo"] == str(ROOT)
    assert "google_vertex_available" in data
    assert data["output_root"].endswith("google_theatrical")


def test_google_studio_dry_run_creates_playable_bundle(tmp_path: Path) -> None:
    if not os.environ.get("AXIOM_RUN_FFMPEG_TESTS"):
        # The script itself is covered by check in default CI; full media encode is
        # opt-in because ffmpeg may be absent on minimal runners.
        return
    data = run_script(
        "produce",
        "--title",
        "Tiny Proof",
        "--runtime-min",
        "1",
        "--clips",
        "2",
        "--clip-duration-s",
        "2",
        "--resolution",
        "320x180",
        "--output-dir",
        str(tmp_path / "proof"),
    )
    final_video = Path(data["final_video"])
    assert final_video.exists()
    assert final_video.stat().st_size > 1000
    assert Path(data["review_html"]).exists()
    assert Path(data["plan"]["output_dir"], "veo_clip_prompts.jsonl").exists()
