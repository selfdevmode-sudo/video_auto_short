"""Shared utilities: config, project state, pretty console output."""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime
from pathlib import Path

import yaml


# ----- console output (no dependencies, just ANSI) -----------------------
class C:
    GREY = "\033[90m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    BOLD = "\033[1m"
    END = "\033[0m"


def say(msg: str) -> None:
    print(f"{C.BLUE}▸{C.END} {msg}")


def ok(msg: str) -> None:
    print(f"{C.GREEN}✓{C.END} {msg}")


def warn(msg: str) -> None:
    print(f"{C.YELLOW}!{C.END} {msg}")


def die(msg: str) -> None:
    print(f"\033[91m✗ {msg}{C.END}", file=sys.stderr)
    sys.exit(1)


# ----- config ------------------------------------------------------------
def load_config(path: str = "config.yaml") -> dict:
    p = Path(path)
    if not p.exists():
        die(f"Config not found at {path}. Are you in the project root?")
    with open(p) as f:
        return yaml.safe_load(f)


def video_preset(cfg: dict, project: "Project | None" = None) -> tuple[str, dict]:
    """Return the active or project-pinned video format preset."""
    video_cfg = cfg.get("video", {})
    name = project.read_state().get("video_format") if project else None
    name = name or video_cfg.get("format", "normal")
    presets = video_cfg.get("formats", {})
    preset = presets.get(name)
    if not preset:
        choices = ", ".join(sorted(presets)) or "none configured"
        die(f"Unknown video format '{name}'. Available formats: {choices}")
    return name, preset


# ----- project (one folder per video) ------------------------------------
def slugify(text: str) -> str:
    text = re.sub(r"[^\w\s-]", "", text.lower()).strip()
    return re.sub(r"[\s_-]+", "-", text)[:60] or "untitled"


class Project:
    """A single video's working folder. Holds all intermediate + final files."""

    def __init__(self, root: Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    @classmethod
    def create(cls, output_dir: str, topic: str) -> "Project":
        stamp = datetime.now().strftime("%Y%m%d-%H%M")
        folder = Path(output_dir) / f"{stamp}_{slugify(topic)}"
        proj = cls(folder)
        proj.write_state({"topic": topic, "created": stamp, "stage": "ideated"})
        return proj

    @classmethod
    def open(cls, folder: str) -> "Project":
        p = Path(folder)
        if not p.exists():
            die(f"Project folder not found: {folder}")
        return cls(p)

    # canonical file locations within the project
    @property
    def script_path(self) -> Path:
        return self.root / "script.md"

    @property
    def audio_path(self) -> Path:
        return self.root / "voiceover.wav"

    @property
    def srt_path(self) -> Path:
        return self.root / "captions.srt"

    @property
    def video_path(self) -> Path:
        return self.root / "final.mp4"

    @property
    def assets_dir(self) -> Path:
        d = self.root / "assets"
        d.mkdir(exist_ok=True)
        return d

    @property
    def state_path(self) -> Path:
        return self.root / "state.json"

    def write_state(self, data: dict) -> None:
        existing = self.read_state()
        existing.update(data)
        with open(self.state_path, "w") as f:
            json.dump(existing, f, indent=2)

    def read_state(self) -> dict:
        if not self.state_path.exists():
            return {}
        with open(self.state_path) as f:
            return json.load(f)
