"""Stage 4 — Build. Captions (faster-whisper) + FFmpeg assembly into final.mp4."""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

from ..common import Project, die, ok, say, video_preset, warn
from . import visuals


# ---------- audio duration -------------------------------------------------
def _duration(path: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        capture_output=True, text=True, check=True,
    )
    return float(out.stdout.strip())


def _ffmpeg_has_filter(name: str) -> bool:
    out = subprocess.run(
        ["ffmpeg", "-hide_banner", "-filters"],
        capture_output=True, text=True, check=True,
    )
    return any(line.split()[1:2] == [name] for line in out.stdout.splitlines())


# ---------- captions -------------------------------------------------------
def _fmt_ts(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    return f"{h:02d}:{m:02d}:{s:06.3f}".replace(".", ",")


def make_captions(cfg: dict, project: Project) -> None:
    from faster_whisper import WhisperModel

    ccfg = cfg["captions"]
    say(f"Transcribing voiceover for captions ({ccfg['model_size']} model)…")
    model = WhisperModel(ccfg["model_size"], device="cpu", compute_type="int8")
    segments, _ = model.transcribe(str(project.audio_path), word_timestamps=True)

    lines = []
    idx = 1
    for seg in segments:
        lines.append(str(idx))
        lines.append(f"{_fmt_ts(seg.start)} --> {_fmt_ts(seg.end)}")
        lines.append(seg.text.strip())
        lines.append("")
        idx += 1
    project.srt_path.write_text("\n".join(lines))
    ok(f"Captions saved to: {project.srt_path}")


def _srt_seconds(value: str) -> float:
    h, m, seconds = value.replace(",", ".").split(":")
    return int(h) * 3600 + int(m) * 60 + float(seconds)


def _read_srt(project: Project) -> list[tuple[float, float, str]]:
    blocks = re.split(r"\n\s*\n", project.srt_path.read_text().strip())
    captions = []
    for block in blocks:
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        if len(lines) < 3 or " --> " not in lines[1]:
            continue
        start, end = lines[1].split(" --> ", 1)
        captions.append((_srt_seconds(start), _srt_seconds(end), " ".join(lines[2:])))
    return captions


def _caption_pngs(project: Project, cfg: dict) -> list[tuple[float, float, Path]]:
    """Render transparent caption cards for FFmpeg overlay fallback."""
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        die("Burned captions need Pillow with this FFmpeg build. Run: pip install -e \".[captions]\"")

    _, preset = video_preset(cfg, project)
    w, h = preset["resolution"]
    is_portrait = h > w
    font_size = max(38, int(w * (0.06 if is_portrait else 0.025)))
    font_path = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"
    font = ImageFont.truetype(font_path, font_size)
    max_width = int(w * (0.82 if is_portrait else 0.72))
    margin = int(h * (0.22 if is_portrait else 0.08))
    pad_x = int(font_size * 0.7)
    pad_y = int(font_size * 0.45)
    line_gap = int(font_size * 0.22)
    caption_dir = project.assets_dir / "captions"
    caption_dir.mkdir(exist_ok=True)

    def wrap(text: str, draw) -> list[str]:
        words = text.split()
        lines: list[str] = []
        current = ""
        for word in words:
            candidate = f"{current} {word}".strip()
            if draw.textbbox((0, 0), candidate, font=font)[2] <= max_width or not current:
                current = candidate
            else:
                lines.append(current)
                current = word
        if current:
            lines.append(current)
        return lines

    overlays = []
    for i, (start, end, text) in enumerate(_read_srt(project), start=1):
        canvas = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(canvas)
        lines = wrap(text, draw)
        boxes = [draw.textbbox((0, 0), line, font=font, stroke_width=2) for line in lines]
        text_w = max(box[2] - box[0] for box in boxes)
        text_h = sum(box[3] - box[1] for box in boxes) + line_gap * (len(lines) - 1)
        box_w = text_w + pad_x * 2
        box_h = text_h + pad_y * 2
        box_x = (w - box_w) // 2
        box_y = max(0, h - margin - box_h)
        draw.rounded_rectangle(
            (box_x, box_y, box_x + box_w, box_y + box_h),
            radius=max(16, font_size // 3),
            fill=(0, 0, 0, 190),
        )
        y = box_y + pad_y
        for line, box in zip(lines, boxes):
            line_w = box[2] - box[0]
            line_h = box[3] - box[1]
            draw.text(
                ((w - line_w) // 2, y),
                line,
                font=font,
                fill=(255, 255, 255, 255),
                stroke_width=2,
                stroke_fill=(0, 0, 0, 230),
            )
            y += line_h + line_gap
        path = caption_dir / f"caption_{i:03d}.png"
        canvas.save(path)
        overlays.append((start, end, path))
    return overlays


# ---------- visual base (slides or stock) ---------------------------------
def _make_slide_bg(project: Project, duration: float, cfg: dict) -> Path:
    """Generate a clean animated-gradient background sized to the audio."""
    _, preset = video_preset(cfg, project)
    w, h = preset["resolution"]
    fps = cfg["visuals"]["fps"]
    out = project.assets_dir / "background.mp4"
    # subtle dark gradient — easy on the eyes, neutral for any niche
    subprocess.run(
        ["ffmpeg", "-y",
         "-f", "lavfi",
         "-i", f"color=c=0x111317:s={w}x{h}:d={duration}:r={fps}",
         "-vf", "noise=alls=8:allf=t,vignette",
         "-t", str(duration), str(out)],
        check=True, capture_output=True,
    )
    return out


def _concat_clips(project: Project, clips: list[Path], duration: float, cfg: dict) -> Path:
    """Loop/trim downloaded stock clips to fill the full audio duration."""
    _, preset = video_preset(cfg, project)
    w, h = preset["resolution"]
    fps = cfg["visuals"]["fps"]
    per = max(duration / len(clips), 2.0)

    normalized = []
    for i, clip in enumerate(clips):
        norm = project.assets_dir / f"norm_{i:02d}.mp4"
        subprocess.run(
            ["ffmpeg", "-y", "-stream_loop", "-1", "-i", str(clip),
             "-t", f"{per:.2f}",
             "-vf", f"scale={w}:{h}:force_original_aspect_ratio=increase,"
                    f"crop={w}:{h},fps={fps}",
             "-an", str(norm)],
            check=True, capture_output=True,
        )
        normalized.append(norm)

    listfile = project.assets_dir / "concat.txt"
    listfile.write_text("\n".join(f"file '{p.name}'" for p in normalized))
    out = project.assets_dir / "background.mp4"
    subprocess.run(
        ["ffmpeg", "-y", "-f", "concat", "-safe", "0",
         "-i", str(listfile), "-c", "copy", str(out)],
        check=True, capture_output=True,
    )
    return out


def _concat_images(project: Project, images: list[Path], duration: float, cfg: dict) -> Path:
    """Turn still images into equal-length segments that fill the audio."""
    _, preset = video_preset(cfg, project)
    w, h = preset["resolution"]
    fps = cfg["visuals"]["fps"]
    per = max(duration / len(images), 2.0)

    segments = []
    for i, image in enumerate(images):
        segment = project.assets_dir / f"image_seg_{i:02d}.mp4"
        subprocess.run(
            ["ffmpeg", "-y", "-loop", "1", "-i", str(image),
             "-t", f"{per:.2f}",
             "-vf", f"scale={w}:{h}:force_original_aspect_ratio=increase,"
                    f"crop={w}:{h},fps={fps},format=yuv420p",
             "-an", str(segment)],
            check=True, capture_output=True,
        )
        segments.append(segment)

    listfile = project.assets_dir / "image_concat.txt"
    listfile.write_text("\n".join(f"file '{p.name}'" for p in segments))
    out = project.assets_dir / "background.mp4"
    subprocess.run(
        ["ffmpeg", "-y", "-f", "concat", "-safe", "0",
         "-i", str(listfile), "-c", "copy", str(out)],
        check=True, capture_output=True,
    )
    return out


# ---------- final mux ------------------------------------------------------
def run(cfg: dict, project: Project) -> Project:
    if not project.audio_path.exists():
        die("No voiceover.wav found. Run the voice stage first.")

    for tool in ("ffmpeg", "ffprobe"):
        if subprocess.run(["which", tool], capture_output=True).returncode != 0:
            die(f"{tool} not found. Install FFmpeg: brew install ffmpeg")

    format_name, _ = video_preset(cfg, project)
    ccfg = cfg["captions"]
    shorts_need_captions = format_name == "shorts" and ccfg.get("require_burn_in_for_shorts", True)
    if shorts_need_captions and (not ccfg["enabled"] or not ccfg["burn_in"]):
        die("Shorts require visible captions. Set captions.enabled and captions.burn_in to true.")

    dur = _duration(project.audio_path)
    max_seconds = cfg["video"]["formats"][format_name].get("max_seconds")
    if max_seconds and dur > max_seconds:
        die(
            f"{format_name} audio is {dur:.0f}s, above its {max_seconds}s limit. "
            "Shorten the script and regenerate the voiceover."
        )
    say(f"Assembling video ({dur:.0f}s)…")

    # 1. captions
    if ccfg["enabled"]:
        make_captions(cfg, project)

    # 2. visual base
    source = cfg["visuals"]["source"]
    if source == "images":
        images = visuals.fetch_images(cfg, project)
        bg = _concat_images(project, images, dur, cfg) if images else _make_slide_bg(project, dur, cfg)
    else:
        clips = visuals.fetch_clips(cfg, project)
        bg = _concat_clips(project, clips, dur, cfg) if clips else _make_slide_bg(project, dur, cfg)

    # 3. mux audio + (optional burned captions)
    vf = None
    caption_overlays = []
    if ccfg["enabled"] and ccfg["burn_in"]:
        if _ffmpeg_has_filter("subtitles"):
            srt = str(project.srt_path).replace("\\", r"\\").replace(":", r"\:").replace("'", r"\'")
            vf = (
                f"subtitles=filename='{srt}':force_style="
                "'FontName=Arial,FontSize=22,PrimaryColour=&H00FFFFFF,"
                "BackColour=&H80000000,BorderStyle=4,MarginV=60'"
            )
        elif _ffmpeg_has_filter("overlay"):
            say("Rendering caption overlays for this FFmpeg build…")
            caption_overlays = _caption_pngs(project, cfg)
        else:
            msg = "This FFmpeg build cannot burn captions; keeping captions.srt separate."
            if shorts_need_captions:
                die(msg)
            warn(msg)

    cmd = ["ffmpeg", "-y", "-i", str(bg), "-i", str(project.audio_path)]
    for _, _, png in caption_overlays:
        cmd += ["-loop", "1", "-i", str(png)]
    if vf:
        cmd += ["-vf", vf]
    if caption_overlays:
        filters = []
        current = "0:v"
        for i, (start, end, _) in enumerate(caption_overlays, start=2):
            output = f"captioned{i}"
            filters.append(
                f"[{current}][{i}:v]overlay=0:0:"
                f"enable='between(t,{start:.3f},{end:.3f})'[{output}]"
            )
            current = output
        cmd += ["-filter_complex", ";".join(filters)]
    cmd += [
        "-map", f"[{current}]" if caption_overlays else "0:v", "-map", "1:a",
        "-c:v", "libx264", "-preset", "medium", "-crf", "20",
        "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2",
        "-pix_fmt", "yuv420p", "-shortest",
        str(project.video_path),
    ]
    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as e:
        die(f"FFmpeg assembly failed:\n{e.stderr[-1500:]}")

    project.write_state({"stage": "built"})
    ok(f"🎬 Video ready: {project.video_path}")
    print(f"   Watch it, and if you like it: faceless upload {project.root}")
    return project
