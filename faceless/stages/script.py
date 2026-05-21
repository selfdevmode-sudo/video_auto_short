"""Stage 2 — Scripting. Generates a narration script and saves it for YOUR review."""
from __future__ import annotations

from ..common import C, Project, ok, say, video_preset
from ..llm import LLM

SYSTEM = """You are an expert YouTube scriptwriter for faceless videos. You write \
spoken narration that sounds natural read aloud — short sentences, conversational \
rhythm, no corporate filler. You open with a hook in the first 5 seconds, deliver \
genuine value, and avoid the templated "Welcome back to the channel" sameness that \
gets channels demonetized. Write ORIGINAL takes, not recycled list-bait."""

PROMPT = """Write a complete voiceover script for a faceless YouTube video.

Title: {title}
Target length: about {minutes} minutes spoken (~{words} words)

Rules:
- Write ONLY the words to be spoken. No stage directions, no "[music]", no scene labels.
- Open with a strong hook — a surprising fact, a question, or a bold claim.
- Use short, punchy sentences. Vary rhythm.
- Break into short paragraphs (these become natural pauses).
- End with a specific, non-generic call to action.

After the script, on a NEW line, write exactly "---KEYWORDS---" then a comma-separated
list of 8-12 visual keywords describing imagery for each part of the video (used to
fetch B-roll). Example: city skyline, server room, glowing circuit, ocean waves"""


def run(cfg: dict, project: Project, minutes: float | None = None) -> Project:
    llm = LLM(cfg["llm"])
    title = project.read_state().get("topic", "Untitled")
    format_name, preset = video_preset(cfg, project)
    minutes = minutes if minutes is not None else preset["script_minutes"]
    words = int(minutes * 150)  # ~150 wpm spoken

    say(f"Writing {format_name} script for: {C.BOLD}{title}{C.END}  (~{minutes} min)")
    raw = llm.chat(SYSTEM, PROMPT.format(title=title, minutes=minutes, words=words))

    # split script from keyword block
    if "---KEYWORDS---" in raw:
        script, kw = raw.split("---KEYWORDS---", 1)
        keywords = [k.strip() for k in kw.replace("\n", ",").split(",") if k.strip()]
    else:
        script, keywords = raw, []

    # save as markdown so it's pleasant to read & edit before voiceover
    content = f"# {title}\n\n{script.strip()}\n"
    project.script_path.write_text(content)
    project.write_state({"stage": "scripted", "keywords": keywords, "video_format": format_name})

    ok(f"Script saved to: {C.BOLD}{project.script_path}{C.END}")
    print()
    print(f"  {C.YELLOW}► REVIEW GATE:{C.END} open that file, edit freely, then run:")
    print(f"     faceless voice {project.root}")
    return project
