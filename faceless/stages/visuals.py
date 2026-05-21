"""Visuals — fetch free stock footage/images, or make clean title slides."""
from __future__ import annotations

import urllib.request
from pathlib import Path

from ..common import Project, ok, say, video_preset, warn


def _download(url: str, dest: Path) -> bool:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "faceless/0.1"})
        with urllib.request.urlopen(req, timeout=30) as r, open(dest, "wb") as f:
            f.write(r.read())
        return True
    except Exception:  # noqa: BLE001
        return False


def _pexels(keyword: str, api_key: str, dest: Path, orientation: str) -> bool:
    import json

    url = (
        "https://api.pexels.com/v1/videos/search?"
        f"query={urllib.parse.quote(keyword)}&per_page=1&orientation={orientation}"
    )
    try:
        req = urllib.request.Request(url, headers={"Authorization": api_key})
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.load(r)
        vids = data.get("videos", [])
        if not vids:
            return False
        # pick an HD-ish file
        files = sorted(
            vids[0]["video_files"],
            key=lambda f: f.get("width", 0),
        )
        target = next((f for f in files if f.get("width", 0) >= 1280), files[-1])
        return _download(target["link"], dest)
    except Exception:  # noqa: BLE001
        return False


def _pixabay(keyword: str, api_key: str, dest: Path) -> bool:
    import json

    url = f"https://pixabay.com/api/videos/?key={api_key}&q={urllib.parse.quote(keyword)}&per_page=3"
    try:
        with urllib.request.urlopen(url, timeout=30) as r:
            data = json.load(r)
        hits = data.get("hits", [])
        if not hits:
            return False
        link = hits[0]["videos"]["medium"]["url"]
        return _download(link, dest)
    except Exception:  # noqa: BLE001
        return False


def _pexels_image(keyword: str, api_key: str, dest: Path, orientation: str) -> bool:
    import json

    url = (
        "https://api.pexels.com/v1/search?"
        f"query={urllib.parse.quote(keyword)}&per_page=1&orientation={orientation}"
    )
    try:
        req = urllib.request.Request(url, headers={"Authorization": api_key})
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.load(r)
        photos = data.get("photos", [])
        if not photos:
            return False
        src = photos[0].get("src", {})
        link = src.get("large2x") or src.get("large") or src.get("original")
        return bool(link) and _download(link, dest)
    except Exception:  # noqa: BLE001
        return False


def _pixabay_image(keyword: str, api_key: str, dest: Path, orientation: str) -> bool:
    import json

    url = (
        "https://pixabay.com/api/?"
        f"key={api_key}&q={urllib.parse.quote(keyword)}"
        f"&image_type=photo&orientation={orientation}&safesearch=true&per_page=3"
    )
    try:
        with urllib.request.urlopen(url, timeout=30) as r:
            data = json.load(r)
        hits = data.get("hits", [])
        if not hits:
            return False
        link = hits[0].get("largeImageURL") or hits[0].get("webformatURL")
        return bool(link) and _download(link, dest)
    except Exception:  # noqa: BLE001
        return False


def _keywords(project: Project) -> list[str]:
    keywords = project.read_state().get("keywords", [])
    if not keywords:
        keywords = [project.read_state().get("topic", "abstract background")]
    return keywords


def fetch_clips(cfg: dict, project: Project) -> list[Path]:
    """Return a list of video clip paths matching the script's keywords."""
    import urllib.parse  # noqa: F401  (used inside helpers)

    vcfg = cfg["visuals"]
    keywords = _keywords(project)
    _, preset = video_preset(cfg, project)
    orientation = preset["stock_orientation"]

    clips: list[Path] = []
    if vcfg["source"] == "stock":
        say(f"Fetching stock B-roll for {len(keywords)} keywords…")
        for i, kw in enumerate(keywords):
            dest = project.assets_dir / f"clip_{i:02d}.mp4"
            got = dest.exists()
            if vcfg.get("pexels_api_key"):
                got = got or _pexels(kw, vcfg["pexels_api_key"], dest, orientation)
            if not got and vcfg.get("pixabay_api_key"):
                got = _pixabay(kw, vcfg["pixabay_api_key"], dest)
            if got:
                clips.append(dest)
            else:
                warn(f"no clip found for '{kw}', will use a slide instead")
        if clips:
            ok(f"Downloaded {len(clips)} clips")

    if not clips:
        # slides fallback — handled in assemble.py (it makes color cards)
        say("Using generated title slides (no stock footage).")
    return clips


def fetch_images(cfg: dict, project: Project) -> list[Path]:
    """Return free stock image paths matching the script's keywords."""
    import urllib.parse  # noqa: F401  (used inside helpers)

    vcfg = cfg["visuals"]
    keywords = _keywords(project)
    _, preset = video_preset(cfg, project)
    orientation = preset["stock_orientation"]
    pixabay_orientation = "vertical" if orientation == "portrait" else "horizontal"
    images: list[Path] = []
    say(f"Fetching free stock images for {len(keywords)} keywords…")
    for i, kw in enumerate(keywords):
        dest = project.assets_dir / f"image_{i:02d}.jpg"
        got = dest.exists()
        if vcfg.get("pexels_api_key"):
            got = got or _pexels_image(kw, vcfg["pexels_api_key"], dest, orientation)
        if not got and vcfg.get("pixabay_api_key"):
            got = _pixabay_image(kw, vcfg["pixabay_api_key"], dest, pixabay_orientation)
        if got:
            images.append(dest)
        else:
            warn(f"no image found for '{kw}', will use the fallback background if needed")
    if images:
        ok(f"Downloaded {len(images)} images")
    else:
        say("Using generated title slides (no stock images).")
    return images
