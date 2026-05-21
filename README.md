# faceless

A **$0, local-first** pipeline for making faceless YouTube videos on your own Mac.
Your local LLM writes scripts, local TTS voices them, FFmpeg assembles the video.
Nothing leaves your machine unless *you* choose to upload.

You stay in control: there are **two review gates** (the script, and the final video)
so nothing gets published without your eyes on it. That's also what keeps you on the
right side of YouTube's 2025 "inauthentic content" rules — the pipeline does the
*labor*, you supply the *judgment*.

---

## What it costs: nothing

| Stage      | Tool                                   | Cost |
|------------|----------------------------------------|------|
| Script     | Your local model in **LM Studio**      | $0   |
| Voiceover  | **Kokoro** (local) or edge-tts         | $0   |
| Visuals    | Title slides, or Pexels/Pixabay B-roll | $0   |
| Captions   | **faster-whisper** (local)             | $0   |
| Assembly   | **FFmpeg**                             | $0   |
| Upload     | YouTube Data API (optional)            | $0   |

---

## One-time setup (about 10 minutes)

### 1. Install FFmpeg
```bash
brew install ffmpeg
```

### 2. Install faceless
```bash
cd faceless
pip install -e ".[kokoro,captions]"     # the local-only essentials
```
> Want the online voice option too? `pip install -e ".[kokoro,edge,captions]"`
> Want uploads later? add `,upload` to the brackets.

The first time you run a voiceover or captions, the models download automatically
(a few hundred MB, cached forever after).

### 3. Set up LM Studio
1. Open **LM Studio** → search & download a model. Good picks for your Mac:
   - **Qwen3-30B-A3B** (fast MoE, excellent writer) — top choice
   - **gpt-oss-20b** — also great
2. Go to the **Developer** tab → load the model → click **Start Server**.
3. That's it. The default address (`http://localhost:1234/v1`) is already in `config.yaml`.

You're ready. No API keys, no accounts, no costs.

---

## Make your first video

```bash
# 1. Brainstorm — try any niche, no commitment
faceless ideas "how everyday tech actually works"

# 2. Pick a title you like and write a script
faceless script "Why your home wifi is slower than it should be"
#    → saves script.md in a new project folder and tells you the path

# 3. ★ REVIEW GATE: open script.md, edit anything you want ★

# 4. Voice it
faceless voice ./videos/20260521-1430_why-your-home-wifi...

# 5. Build the final video (captions + assembly)
faceless build ./videos/20260521-1430_why-your-home-wifi...
#    → final.mp4 lands in the same folder
```

Prefer one command? `faceless auto "<title>"` runs script → (pause for review) →
voice → build in a single flow.

See everything you've made and where each one is:
```bash
faceless list
```

---

## Trying different formats (no niche lock)

The whole point: experiment freely. `faceless ideas` works for *any* theme —
"true crime in aviation", "history of weird inventions", "explain X like I'm 5".
Make a few in different styles, see what gets views, then lean into what works.
Because YouTube judges *inauthenticity at the channel level*, the winning move is
**variety + a genuine angle**, which is exactly what manual idea-picking gives you.

---

## Switching the voice

In `config.yaml` under `tts:`
- `engine: kokoro` — fully local. Voices include `af_heart`, `af_bella`,
  `am_michael`, `bf_emma` (a=American f=female, am=American male, bf=British female…).
- `engine: edge` — Microsoft's online voices (very natural, free). e.g.
  `en-US-AriaNeural`, `en-US-GuyNeural`, `en-GB-RyanNeural`.

## Switching video format

In `config.yaml` under `video:`, set `format: normal` for a 16:9 long-form
video or `format: shorts` for a 9:16 short. Each preset controls script length,
render resolution, and stock search orientation. New scripts remember the chosen
format in `state.json`, so changing the config later does not reshape projects
you already scripted.

Shorts require visible burned captions by default. Keep `captions.enabled` and
`captions.burn_in` on; the captions extra installs Pillow so caption overlays can
still render when FFmpeg lacks its `subtitles` text filter.
The Shorts preset also rejects voiceovers over its configured `max_seconds` limit.

## Adding stock visuals (optional)

Slides are the default and need nothing. For free stock visuals:
1. Free key from https://www.pexels.com/api/ and/or https://pixabay.com/api/docs/
2. Paste into `config.yaml` under `visuals:`.
3. Set `source: stock` for B-roll video or `source: images` for stock photos.

---

## Optional: YouTube upload

Off by default — you don't need it to make videos, and your files are saved locally
regardless. When you've found a format worth publishing regularly:

1. `pip install -e ".[upload]"`
2. Google Cloud Console → new project → enable **YouTube Data API v3**.
3. Create an **OAuth client ID** (type: *Desktop app*), download the JSON,
   save it as `client_secrets.json` in this folder.
4. In `config.yaml` set `upload.enabled: true`.
5. `faceless upload <project_folder>` — authorizes once, then uploads as **private**.
   You review in YouTube Studio and hit publish yourself.

Note: the free API quota allows ~6 uploads/day, which is plenty.

---

## How a project folder looks

```
videos/20260521-1430_why-your-home-wifi.../
├── state.json        ← which stage it's at
├── script.md         ← edit this before voicing
├── voiceover.wav
├── captions.srt
├── final.mp4         ← your video
└── assets/           ← intermediate clips/backgrounds
```

## Troubleshooting

- **"Couldn't reach the local LLM"** → LM Studio isn't serving. Developer tab → Start Server.
- **"ffmpeg not found"** → `brew install ffmpeg`.
- **Kokoro import error** → `pip install kokoro soundfile`.
- **Voice sounds robotic** → try `engine: edge` for more natural narration.
