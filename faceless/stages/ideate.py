"""Stage 1 — Ideation. Brainstorm video topics + punchy titles for any niche."""
from __future__ import annotations

import json

from ..common import C, ok, say
from ..llm import LLM

SYSTEM = """You are a YouTube content strategist who helps faceless channels find \
ideas that get views WITHOUT being generic AI slop. You favour specific, \
fresh angles over tired formats. You understand that YouTube demonetizes \
mass-produced, templated, low-originality content, so every idea you give \
must have a clear hook and genuine value."""

PROMPT = """Niche / theme: {niche}

Generate {n} video ideas. For EACH idea return:
- "title": a click-worthy but honest title (max ~70 chars)
- "hook": one sentence describing the opening hook that stops the scroll
- "angle": what makes this DIFFERENT from the 100 other videos on this topic

Return ONLY a JSON array of objects with keys title, hook, angle. No markdown, no preamble."""


def _parse(raw: str) -> list[dict]:
    # local models sometimes wrap JSON in fences or add stray text; be forgiving
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    start, end = raw.find("["), raw.rfind("]")
    if start != -1 and end != -1:
        raw = raw[start : end + 1]
    return json.loads(raw)


def run(cfg: dict, niche: str, n: int = 8) -> list[dict]:
    llm = LLM(cfg["llm"])
    say(f"Brainstorming {n} ideas for: {C.BOLD}{niche}{C.END}")
    raw = llm.chat(SYSTEM, PROMPT.format(niche=niche, n=n))
    try:
        ideas = _parse(raw)
    except (json.JSONDecodeError, IndexError):
        # fall back to showing raw text rather than crashing
        print(raw)
        return []

    print()
    for i, idea in enumerate(ideas, 1):
        print(f"  {C.BOLD}{i}.{C.END} {idea.get('title', '???')}")
        print(f"     {C.GREY}hook:{C.END}  {idea.get('hook', '')}")
        print(f"     {C.GREY}angle:{C.END} {idea.get('angle', '')}")
        print()
    ok(f"{len(ideas)} ideas generated. Pick one and run: faceless script \"<title>\"")
    return ideas
