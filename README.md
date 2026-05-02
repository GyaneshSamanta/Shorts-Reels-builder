# Shorts & Reels Builder (PodcastClipper Pro)

> **Drop in a 2-hour podcast. Get back a month of vertical Shorts, Reels, and TikToks — fully transcribed, captioned, mastered, and rendered.**

![Banner](https://img.shields.io/badge/PodcastClipper-Pro-blueviolet?style=for-the-badge&logo=python)

![Python](https://img.shields.io/badge/python-3.10%2B-3776AB) ![Whisper](https://img.shields.io/badge/AI-OpenAI%20Whisper-10B981) ![Platform](https://img.shields.io/badge/platform-Windows-0078D6)

---

## About

**Who:** Built and maintained by Gyanesh Samanta — a single-author tool, open for community contributions.
**What:** A Windows desktop app that turns long-form podcast / interview video into ready-to-publish vertical clips, with AI transcription, multi-aspect framing, burned-in captions, and broadcast-grade audio mastering.
**When:** v1 shipped March 2026; actively maintained.
**Where:** Windows 10/11 desktop. Python 3.10+, ships its own `_ffmpeg_bin` for zero-config render.
**Why:** Editing clips by hand is the slowest part of every creator's pipeline. PodcastClipper Pro compresses "load → transcribe → pick → master → render" into a few clicks.

## The Story

A typical 90-minute podcast yields **15–25 sharable moments**. Manually clipping them takes a creator 4–6 hours per episode in Premiere or DaVinci. PodcastClipper Pro collapses that loop:

1. **Load** any `.mp4 / .mkv / .mov`.
2. **Transcribe** locally with **OpenAI Whisper Medium** — no cloud, no API bill.
3. **Click any text segment** to drop it into the render queue with a live WYSIWYG crop overlay.
4. **Master audio** automatically: high-pass at 80Hz, warmth at 150Hz, presence at 3.5kHz, loudness normalized to **-16 LUFS**, optional DeepFilterNet noise suppression.
5. **Burn captions** (bold white + black outline, broadcast-style).
6. **Batch render** — 9:16 crop / 9:16 fit / 1:1 / 16:9 outputs in one go.

The UI is a 3-pane resizable layout (transcription | controls | queue) with a live CPU/RAM/VRAM mini-graph so you know exactly what your machine is doing during a render.

A first-run `start_app.bat` builds the venv, installs deps, and launches — one double-click, no terminal.

## Gallery

The app ships with an `assets/icon.ico` and a clean CustomTkinter UI. Screenshots and a demo reel are on the project's LinkedIn post.

| Feature | What it does |
|---|---|
| Whisper Medium transcription | Industry-leading speech-to-text, fully local |
| WYSIWYG crop overlay | See the vertical crop before you render |
| 4 aspect ratios | 9:16 crop, 9:16 fit (letterbox), 1:1, 16:9 |
| Burned-in captions | Auto-generated from Whisper segments |
| Audio mastering | EQ + loudnorm to -16 LUFS |
| Resource monitor | Live CPU / RAM / VRAM during render |

---

## Tech Stack

- **GUI:** [CustomTkinter](https://github.com/TomSchimansky/CustomTkinter) + `PanedWindow`
- **Transcription:** [OpenAI Whisper](https://github.com/openai/whisper) (Medium)
- **Video:** [MoviePy 1.0.3](https://zulko.github.io/moviepy/) + [FFmpeg](https://ffmpeg.org/) (bundled in `_ffmpeg_bin/`)
- **Computer vision:** OpenCV (preview frame extraction)
- **Audio:** Pure FFmpeg filters — `loudnorm`, `highpass`, `equalizer`
- **Resource monitor:** `psutil`, `GPUtil`
- **Packaging:** PyInstaller, `imageio-ffmpeg`, `winshell`, `pywin32`

## Repo Structure

```
Shorts-Reels-builder/
├── assets/                       # icon.ico
├── backend/
│   ├── audio_util.py             # Loudnorm + EQ pipeline
│   ├── subtitle_util.py          # ASS subtitle generation
│   ├── transcribe_util.py        # Whisper wrapper
│   └── video_util.py             # MoviePy / FFmpeg render pipeline
├── build_scripts/                # PyInstaller / packaging
├── _ffmpeg_bin/                  # Bundled FFmpeg binaries
├── main.py                       # Entry point + UI
├── requirements.txt
├── start_app.bat                 # First-run venv + launch
├── create_shortcut.py            # Optional desktop shortcut
├── Launch PodcastClipper.vbs     # Silent launcher
├── PRD.md / RevisedPRD.md        # Product spec docs
└── SpecDocument.md / techspec2.md
```

## Getting Started

**Users (one-click):**

1. Install [Python 3.10+](https://python.org/downloads/) (check "Add to PATH").
2. Double-click `start_app.bat`. First run takes 2–3 min to build the venv; subsequent runs launch instantly.
3. Optional: `venv\Scripts\python create_shortcut.py` for a desktop icon.

**Developers:**

```bash
git clone https://github.com/GyaneshSamanta/Shorts-Reels-builder.git
cd Shorts-Reels-builder
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

## Contributing

PRs welcome. Fork → branch → PR.

## License

MIT — see [`LICENSE`](./LICENSE).

## Credits

Built by **Gyanesh Samanta** ([LinkedIn](https://www.linkedin.com/in/gyanesh-samanta/)). Support the project: [Buy Me A Chai](https://buymeachai.ezee.li/GyaneshOnProduct).
