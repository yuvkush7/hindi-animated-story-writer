# Production Pipeline

The full production is an 8-phase pipeline. Each phase consumes the output of the previous one, with `story.json` as the hub.

## The 8 phases

### 1. Story Engine
Architect the story: premise, characters, mystery, and 12–18 scenes using the skeleton and causal chain (see `story-architecture.md`, `character-design.md`, `mystery-engine.md`). Output: an approved story design.

### 2. Canonical Story Data
Write the single source of truth **`story.json`**: story metadata, characters, scenes, and beats with stable IDs and explicit speakers. Everything downstream is generated from this file.

### 3. Script Export
Generate `script.txt` (plain read-through) and `script.md` (formatted, with scene headers and `**नाम:**` attribution) **from `story.json`**. Never hand-edit these; regenerate them.

### 4. HTML Studio
Build/refresh the local **Story Studio** (`studio/`): an HTML/JS UI that renders scenes and beats from `story.json`, with each line individually addressable so it can be highlighted during playback.

### 5. Gemini TTS
Synthesize audio for each beat via **Gemini TTS**, using `GEMINI_API_KEY` from the environment. One audio unit per beat, named by beat ID (e.g. `s01_b01.wav`). Reuse existing audio for beats whose text/speaker is unchanged.

### 6. Audio + HTML Integration
Wire audio into the Studio: as each beat plays, highlight its line. Store audio metadata (durations, file paths) so the Studio can sync highlight timing.

### 7. Edit / Regenerate
When the story changes, **edit `story.json`** and regenerate only what changed: re-export scripts, refresh the Studio, and re-synthesize *only* the beats whose text/speaker changed.

### 8. Unified Workflow
A single orchestration entry point that runs phases 2–6 in order (and phase 7 on edits), so producing or updating a story is one command.

## Source-of-truth rule

**`story.json` is the single source of truth.** It generates:

- `script.txt` and `script.md`
- the HTML Studio content
- audio metadata (which beats need audio, file names, sync data)

**Do NOT maintain independent copies** of the story in the script, the HTML, or anywhere else. If they drift, `story.json` wins and the others are regenerated.

## Scripts

The `scripts/` directory provides dependency-free Python 3 (standard library only) tooling for phases 2–3. Run them yourself (no network or external packages needed):

```
python3 scripts/story_validator.py <story.json>
python3 scripts/script_exporter.py <story.json> --outdir story
python3 scripts/reconstruct_check.py <story.json>
```

- `story_validator.py` — schema/ID/sequence/speaker validation. Exit 0 = valid, non-zero = invalid; `--quiet` prints only `PASS`/`FAIL`. Exposes an importable `validate_story(data) -> list[str]` reused by the exporter.
- `script_exporter.py` — validates first, refuses to export on any error, then writes `<outdir>/script.md` and `<outdir>/script.txt` from the canonical data, preserving scene order then ascending `sequence`.
- `reconstruct_check.py` — round-trip check: reconstructs the ordered beat list, prints scene/beat counts and a per-scene listing, exits non-zero if any beat lacks a speaker or text.
- `story_schema.json` — JSON Schema (draft-07) for the canonical `story.json`.
- `gemini_tts.py`, `generate_audio.py`, `audio_validator.py` — Phase 5 audio tooling (see the Audio section below).

**Validate before every export / HTML / audio step.** `story.json` is the single source of truth; generated scripts, HTML, and audio metadata are always regenerated from it, never hand-edited.

## Audio (Gemini TTS)

Phase 5 synthesizes one audio unit per beat via **Gemini TTS**, keyed by stable beat id, so the Studio can sync playback to the highlighted line. All tooling is Python 3 standard-library only.

### API key

Set `GEMINI_API_KEY` in the environment (`export GEMINI_API_KEY=...`). It is read at runtime, never hardcoded, never committed, and never printed — error messages mask it. All Gemini-specific request shaping, endpoint, and response parsing live **only** in `scripts/gemini_tts.py`, keeping the rest of the pipeline provider-agnostic.

### `generate_audio.py`

```
python3 scripts/generate_audio.py <story.json> [--outdir DIR] [--voices <path>] [--only BEAT_ID] [--force] [--dry-run]
```

- Validates `story.json` first and refuses on any error.
- Default `--outdir` is the directory of `story.json`; audio goes to `<outdir>/audio/`, manifest at `<outdir>/audio/metadata.json`.
- Default `--voices` is `studio/voice_profiles.json`.
- `--dry-run` — no network, no writes; prints a per-beat `GENERATE`/`REUSE`/`SKIP` plan with the chosen voice and exits (works without a key).
- `--only BEAT_ID` — (re)generate a single beat. `--force` — regenerate even if unchanged.

### Voices — `studio/voice_profiles.json`

Edit character→voice mappings here. Resolution per beat: `by_character_id[character_id]` → `by_speaker[speaker]` → `default`.

**Valid Gemini voice names (30):** Zephyr, Puck, Charon, Kore, Fenrir, Leda, Orus, Aoede, Callirrhoe, Autonoe, Enceladus, Iapetus, Umbriel, Algieba, Despina, Erinome, Algenib, Rasalgethi, Laomedeia, Achernar, Alnilam, Schedar, Gacrux, Pulcherrima, Achird, Zubenelgenubi, Vindemiatrix, Sadachbia, Sadaltager, Sulafat.

### Model and format

- Model: `gemini-2.5-flash-preview-tts`.
- WAV output: **24 kHz mono 16-bit PCM**.

### `audio/metadata.json` schema

A JSON array; one entry per beat with: `beat_id`, `scene_id`, `sequence`, `speaker`, `character_id`, `text_hash`, `voice_name`, `language_code`, `audio_path` (`audio/<beat_id>.wav`), `status`, `duration_seconds`, `provider` (`gemini`), `model`, `generated_at` (ISO 8601).

### Incremental + resumable

- **Incremental:** `text_hash = sha256(text + "|" + voice_name + "|" + language_code)`. A beat is reused when a prior `ok` entry has the same `text_hash` and `voice_name` and its `.wav` exists — unless `--force`.
- **Resumable:** beats are processed one at a time; a failure marks the entry `failed` (keeping prior successes) and `metadata.json` is rewritten after each beat, so re-runs continue where they left off.

### `audio_validator.py`

```
python3 scripts/audio_validator.py <audio_dir_or_metadata.json> [--story story.json]
```

Confirms each `ok` entry's `.wav` exists, is non-empty, and matches its `beat_id`; flags orphan wavs, `failed`/`pending` entries, and (with `--story`) beats missing audio / metadata entries not in the story. Exits non-zero on any inconsistency.

## Unified build & incremental edit workflow

`scripts/build.py` is the **unified entry point** (phase 8). It enforces the source-of-truth rule end to end: nothing downstream runs unless `story.json` validates, and the only way generated artifacts change is by (re)running the build.

### The full flow

`story.json` (single source of truth) → **validate** → **export** `story/script.md` + `story/script.txt` (into a `story/` dir beside the source) → **copy** the canonical `story.json` into `studio/story.json` → *(optional)* **Gemini audio** into `studio/audio/` (with `studio/audio/metadata.json`) → **open the Story Studio**.

`build.py` imports the sibling scripts as modules (`validate_story`, `script_exporter`, `generate_audio`) — the scripts dir is added to `sys.path` — so there is one implementation of each stage, not a copy.

### Exact commands

Full build (validate → export → sync HTML → generate audio):

```
python3 scripts/build.py story.json --with-audio
```

No-audio refresh (validate → export → sync HTML; prints a reminder that audio is stale):

```
python3 scripts/build.py story.json
```

Then serve the Studio and open the printed URL:

```
python3 studio/serve.py --root studio
```

Useful audio flags on `build.py`: `--dry-run-audio` (plan only, no network/writes), `--force-audio` (regenerate even unchanged beats), `--only BEAT_ID` (restrict audio to one beat), `--studio-dir <dir>` (target a different studio dir), `--voices <path>`.

Robustness: each stage is wrapped. If some beats fail to synthesize, the build still reports **partial success** — canonical data, `script.*`, and `studio/story.json` are all fine — and points to `studio/audio/metadata.json` for the `failed` entries. `story.json` is never modified or destroyed by the build.

### The edit / regenerate loop

To change a line, edit the canonical data with `scripts/edit_beat.py`, then rebuild only what changed:

```
python3 scripts/edit_beat.py story.json --beat s03_b07 --text "..."
python3 scripts/build.py story.json --with-audio --only s03_b07
```

`edit_beat.py` loads `story.json`, updates that beat's `text` (and optionally `--speaker` / `--character-id`), re-validates the **whole** story, and writes `story.json` back pretty-printed UTF-8 (`ensure_ascii=false`, so Devanagari stays readable). It never touches the network.

Because the edit changes that beat's `text` (and therefore its `text_hash`), the `--only s03_b07` build regenerates **only that beat's audio**, while **every other beat's audio is reused** unchanged. The build re-copies `story.json` into `studio/story.json` so the HTML shows the new text, and playback **sync stays correct because it is keyed by the stable `beat_id`** — not by array position or text.

### Golden rules (restated)

- **Never hand-edit** `studio/story.json`, `story/script.md`, `story/script.txt`, or the audio ordering — they are **all generated** from `story.json`.
- `studio/story.json` only ever changes via the build's copy step.
- Edit content only in the canonical `story.json` (directly or via `edit_beat.py`), then rebuild.

## Planned project structure

```
hindi-animated-story-writer/
├── SKILL.md
├── references/          # the design/rules docs (this folder)
├── examples/            # style exemplars
├── scripts/             # export, HTML gen, Gemini TTS, unified workflow (added later)
└── studio/              # generated local HTML Story Studio (built by the pipeline)
```

A given story's produced artifacts (`story.json`, `script.*`, audio files) live in that story's own output directory, kept separate from the skill's tooling.

## Configuration approach

- **Config is separate from code.** Model names, voices, paths, and defaults live in a config file or environment, not inline in scripts.
- **`GEMINI_API_KEY` lives in the environment** and is read at runtime. It is never hardcoded, never committed, and never printed.

## Robustness expectations

- **Idempotent regeneration** — running the pipeline twice on an unchanged `story.json` produces the same artifacts and reuses audio.
- **Graceful failure** — if Gemini or the Studio server is unreachable, fail clearly; do not claim success (see the "No fake capabilities" rule).
- **Validation first** — validate `story.json` (schema, ID sequencing, speaker attribution, `character_id` resolution) before export or synthesis.
- **Incremental** — only regenerate what changed, keyed on stable beat IDs.
