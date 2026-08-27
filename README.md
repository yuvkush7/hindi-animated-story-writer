# Hindi Animated Story Writer

A Claude Code skill for writing and producing **~20-minute, family-friendly Hindi (Devanagari) animated stories** — from story architecture to synced line-by-line audio in a local HTML Story Studio.

## What it does

1. **Story Engine** — architects premise, characters, mystery, and scenes.
2. **Canonical `story.json`** — the single source of truth for everything downstream.
3. **Script export** — generates `script.txt` / `script.md` from `story.json`.
4. **HTML Story Studio** — a dependency-free local viewer/reader.
5. **Gemini TTS** — per-line audio, synced to highlighted lines in the Studio.

## Quick start

Install as a Claude Code skill:

```bash
git clone https://github.com/yuvkush7/hindi-animated-story-writer.git \
  ~/.claude/skills/hindi-animated-story-writer
```

Then ask Claude to write a story, or run the pipeline directly:

```bash
# Validate the canonical story data
python3 scripts/story_validator.py studio/story.json

# Full build: validate → export scripts → sync studio → audio
export GEMINI_API_KEY=...   # never hardcoded or committed
python3 scripts/build.py studio/story.json --with-audio

# Serve the Story Studio
python3 studio/serve.py --root studio
# → open http://127.0.0.1:8765/
```

## Structure

```
SKILL.md            # skill entry point — full documentation
references/         # story architecture, mystery engine, dialogue rules, QC, pipeline
examples/           # well-structured story excerpts + canonical story.json example
scripts/            # dependency-free Python 3 tooling (validator, exporter, TTS, build)
studio/             # vanilla HTML/CSS/JS Story Studio + local server
```

## Golden rules

- **`story.json` is the single source of truth** — scripts, HTML, and audio metadata are generated from it, never maintained by hand.
- **Every spoken line has an explicit speaker** — validated before every export.
- **Stable scene/beat IDs** (e.g. `s01_b01`) so audio is reused when text is unchanged.
- **API key lives in `GEMINI_API_KEY`** — never hardcoded, committed, or printed.

See [`SKILL.md`](SKILL.md) for the full 8-phase pipeline documentation.
