# Story Studio

A dependency-free, vanilla HTML/CSS/JS viewer for the Hindi animated story data.
It reads **directly from the canonical `story.json`** — the story text is never
duplicated in the HTML. `story.json` is the single source of truth.

## Files

| File          | Purpose                                                        |
| ------------- | -------------------------------------------------------------- |
| `index.html`  | Single-page UI (header, scenes, characters, transcript, controls). |
| `styles.css`  | Styling; narration vs dialogue distinction, `.current` highlight.  |
| `app.js`      | Loads data, flattens beats, renders, handles navigation + audio.   |
| `serve.py`    | Python 3 stdlib static server.                                     |
| `story.json`  | Local demo story (canonical shape).                                |

## Data layout

Place these **alongside `index.html`**:

```
studio/
├── index.html
├── styles.css
├── app.js
├── serve.py
├── story.json            # required — the canonical story
└── audio/                # optional (Phase 5)
    ├── metadata.json     # [{ "beat_id": "s01_b01", "path": "audio/s01_b01.mp3", "status": "ok" }, ...]
    ├── s01_b01.mp3
    └── ...
```

- **`story.json`** shape: `story.title / overview / moral /
  characters[{id,name,age,gender,role}] /
  scenes[{id,title,location,time, beats[{id,sequence,type,speaker,character_id,text}]}]`.
  The narrator's `speaker` is `कथावाचक`.
- **`audio/metadata.json`** (optional) maps beats to audio files by **stable
  beat id**. Each entry: `{ "beat_id": "<beat id>", "path": "<relative path>",
  "status": "ok" }`. Sync is always by beat id — never by text or position.
- If no audio is present, the studio still works: Play/Next advance the
  highlight and the audio indicator shows `missing-audio` instead of crashing.

## Running the server

The server does **not** start automatically — **you** must start it.
This repo never auto-runs it.

```
python3 studio/serve.py [--port 8765] [--root <dir>]
```

- `--port` — port to listen on (default: `8765`).
- `--root` — directory to serve (default: the folder containing `serve.py`).
  Point it at any folder that has `index.html` + `story.json` (+ optional `audio/`).

Then open:

```
http://127.0.0.1:8765/
```

The script prints this URL on startup; it does not open a browser for you.
