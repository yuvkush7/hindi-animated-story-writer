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

## Set it up with a prompt (any AI agent)

You don't have to install anything by hand — paste a prompt into your AI agent and let **it** do the setup. Two options:

### Option 1 — Claude Code sets itself up

Open Claude Code and paste:

```text
Install the "hindi-animated-story-writer" skill for yourself:

1. Clone https://github.com/yuvkush7/hindi-animated-story-writer.git
   into ~/.claude/skills/hindi-animated-story-writer (create the skills
   directory if it doesn't exist).
2. Verify the install: list the cloned files and confirm SKILL.md,
   scripts/, references/, examples/, and studio/ are all present.
3. Read SKILL.md fully so you understand the 8-phase pipeline, the
   canonical story.json rule, and the golden rules.
4. Check whether python3 is available and report the version.
5. Run the bundled example end-to-end WITHOUT audio to prove the
   pipeline works:
       python3 scripts/story_validator.py studio/story.json
       python3 scripts/build.py studio/story.json
   Show me the validator output.
6. Check if GEMINI_API_KEY is set in my environment (just yes/no —
   never print the key). If it's not set, tell me exactly how to set
   it and stop — do not generate audio without it.
7. If the key IS set, run:
       python3 scripts/build.py studio/story.json --with-audio
   then start the studio with:
       python3 studio/serve.py --root studio
   and give me the URL to open.
8. Finally, confirm the skill is installed and tell me: "Ready — just
   describe the story you want."

Do not hardcode, print, or commit any API key at any step.
```

After that, the skill is live in every new Claude Code session — just describe the story you want (topic, characters, tone) and it will write and produce it.

### Option 2 — any other AI agent (Cursor, Codex, Windsurf, etc.)

This prompt works with any agent that can run shell commands:

```text
You are setting up a local AI "Hindi Animated Story Writer" pipeline
for me. Complete these steps in order and report after each one:

1. Install: clone https://github.com/yuvkush7/hindi-animated-story-writer
   to ~/.claude/skills/hindi-animated-story-writer. If that path isn't
   meaningful for your environment, clone it to
   ~/ai-skills/hindi-animated-story-writer instead and use that path
   for everything below.
2. Read the SKILL.md file in full and adopt its rules as your working
   instructions: story.json is the single source of truth, every spoken
   line has an explicit speaker, stable scene/beat IDs, API key only
   from the GEMINI_API_KEY environment variable.
3. Verify Python 3 is available and run the validator on the example:
       python3 scripts/story_validator.py studio/story.json
   It must print PASS. If it fails, show me the errors.
4. Do a dry run of the whole pipeline without audio:
       python3 scripts/build.py studio/story.json
   Confirm script.md and script.txt were exported and
   studio/story.json is in sync.
5. Check if GEMINI_API_KEY is set (yes/no only, never print it).
   - If set: run "python3 scripts/build.py studio/story.json
     --with-audio", then "python3 scripts/audio_validator.py
     studio/audio", then "python3 studio/serve.py --root studio"
     in the background and give me the URL.
   - If not set: stop after step 4 and tell me how to set the key.
6. Summarize: what's installed, what works, what's pending.

Rules for you at all times: never hardcode, print, or commit any API
key; never edit generated scripts, HTML, or audio metadata directly —
only regenerate them from story.json; never claim audio was generated
or a server is running unless you actually verified it.
```

### Using the skill after setup

Once installed, just ask in natural language, e.g.:

> "Write a 20-minute Hindi animated story about a brave girl who solves the mystery of the disappearing village well, with 5 characters, and produce the full audio."

The agent follows the 8-phase pipeline: story architecture → canonical `story.json` → script export → HTML Studio → Gemini TTS → synced playback.

## Golden rules

- **`story.json` is the single source of truth** — scripts, HTML, and audio metadata are generated from it, never maintained by hand.
- **Every spoken line has an explicit speaker** — validated before every export.
- **Stable scene/beat IDs** (e.g. `s01_b01`) so audio is reused when text is unchanged.
- **API key lives in `GEMINI_API_KEY`** — never hardcoded, committed, or printed.

See [`SKILL.md`](SKILL.md) for the full 8-phase pipeline documentation.
