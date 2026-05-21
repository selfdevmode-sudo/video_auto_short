"""Stage 5 (OPTIONAL) — Upload to YouTube as a PRIVATE draft. Off by default."""
from __future__ import annotations

from ..common import Project, die, ok, say, warn
from ..llm import LLM

META_SYSTEM = "You write YouTube metadata that is honest, specific, and avoids clickbait spam."
META_PROMPT = """Video title: {title}

Write YouTube metadata. Return in exactly this format:
DESCRIPTION:
<2-3 paragraph description, with a 1-line hook first>
TAGS:
<10-15 comma-separated tags>"""


def _metadata(cfg: dict, title: str) -> tuple[str, list[str]]:
    llm = LLM(cfg["llm"])
    raw = llm.chat(META_SYSTEM, META_PROMPT.format(title=title))
    desc, tags = title, []
    if "TAGS:" in raw:
        d, t = raw.split("TAGS:", 1)
        desc = d.replace("DESCRIPTION:", "").strip()
        tags = [x.strip() for x in t.split(",") if x.strip()][:15]
    return desc, tags


def run(cfg: dict, project: Project) -> Project:
    ucfg = cfg["upload"]
    if not ucfg.get("enabled"):
        die(
            "Upload is disabled in config.yaml (upload.enabled: false).\n"
            "   Your video is already saved locally — that's the default workflow.\n"
            "   To enable uploads, see the 'Optional: YouTube upload' section of the README."
        )
    if not project.video_path.exists():
        die("No final.mp4 found. Run the build stage first.")

    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaFileUpload
    except ImportError:
        die(
            "Upload deps missing. Install with:\n"
            "   pip install google-api-python-client google-auth-oauthlib"
        )

    import os
    import pickle

    title = project.read_state().get("topic", "Untitled")
    say("Generating metadata…")
    description, tags = _metadata(cfg, title)

    # OAuth — caches a token after first run so you only authorize once
    scopes = ["https://www.googleapis.com/auth/youtube.upload"]
    token_file = "token.pickle"
    creds = None
    if os.path.exists(token_file):
        with open(token_file, "rb") as f:
            creds = pickle.load(f)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(ucfg["client_secrets"], scopes)
            creds = flow.run_local_server(port=0)
        with open(token_file, "wb") as f:
            pickle.dump(creds, f)

    youtube = build("youtube", "v3", credentials=creds)
    body = {
        "snippet": {
            "title": title[:100],
            "description": description,
            "tags": tags,
            "categoryId": str(ucfg.get("category_id", "27")),
        },
        "status": {"privacyStatus": ucfg.get("privacy", "private")},
    }

    say(f"Uploading as {ucfg.get('privacy', 'private')} (costs ~1600 quota units)…")
    media = MediaFileUpload(str(project.video_path), resumable=True)
    req = youtube.videos().insert(part="snippet,status", body=body, media_body=media)
    resp = req.execute()

    vid = resp["id"]
    project.write_state({"stage": "uploaded", "video_id": vid})
    ok(f"Uploaded as PRIVATE: https://studio.youtube.com/video/{vid}/edit")
    warn("Review it in YouTube Studio, then publish manually when you're happy.")
    return project
