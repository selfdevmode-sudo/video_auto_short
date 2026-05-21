"""Stage 3 — Voiceover. Turns the reviewed script into a WAV. Local-first."""
from __future__ import annotations

import re

from ..common import Project, die, ok, say, warn


def _read_script_text(project: Project) -> str:
    """Read script.md, drop the markdown title line, return clean spoken text."""
    raw = project.script_path.read_text()
    lines = [ln for ln in raw.splitlines() if not ln.startswith("#")]
    text = "\n".join(lines).strip()
    # strip any stray markdown emphasis the model may have added
    text = re.sub(r"[*_`]", "", text)
    return text


def _kokoro(text: str, out_path, voice: str, speed: float):
    """Local Kokoro-82M TTS. Fully offline once the model is cached."""
    import numpy as np
    import soundfile as sf
    from kokoro import KPipeline

    pipeline = KPipeline(lang_code="a")  # 'a' = American English
    chunks = []
    for _, _, audio in pipeline(text, voice=voice, speed=speed):
        chunks.append(audio)
    if not chunks:
        die("Kokoro produced no audio — is the script empty?")
    sf.write(str(out_path), np.concatenate(chunks), 24000)


def _edge(text: str, out_path, voice: str, speed: float):
    """Online fallback: Microsoft Edge voices via edge-tts. Free, very natural."""
    import asyncio

    import edge_tts

    rate = f"{int((speed - 1) * 100):+d}%"
    mp3 = str(out_path).replace(".wav", ".mp3")

    async def _go():
        await edge_tts.Communicate(text, voice, rate=rate).save(mp3)

    asyncio.run(_go())
    # convert mp3 -> wav so downstream stages have one format
    import subprocess

    subprocess.run(
        ["ffmpeg", "-y", "-i", mp3, str(out_path)],
        check=True,
        capture_output=True,
    )


def run(cfg: dict, project: Project) -> Project:
    if not project.script_path.exists():
        die("No script.md found. Run the script stage first.")

    text = _read_script_text(project)
    tcfg = cfg["tts"]
    engine = tcfg["engine"]
    say(f"Generating voiceover with {engine} ({len(text.split())} words)…")

    try:
        if engine == "kokoro":
            _kokoro(text, project.audio_path, tcfg["kokoro_voice"], tcfg["speed"])
        elif engine == "edge":
            _edge(text, project.audio_path, tcfg["edge_voice"], tcfg["speed"])
        else:
            die(f"Unknown tts.engine '{engine}'. Use 'kokoro' or 'edge'.")
    except ImportError as e:
        die(
            f"Missing TTS dependency for '{engine}': {e}\n"
            f"   Kokoro: pip install kokoro soundfile\n"
            f"   Edge:   pip install edge-tts"
        )

    project.write_state({"stage": "voiced"})
    ok(f"Voiceover saved to: {project.audio_path}")
    print(f"   Next: faceless build {project.root}")
    return project
