---
name: hindi-animated-story-writer
description: Generate professional ~20-minute family-friendly Hindi (Devanagari) animated stories with strong architecture, mystery, and distinct characters; store them as a canonical story.json single source of truth; export scripts; power a local HTML Story Studio; and generate line-by-line audio with Gemini TTS synced to highlighted lines.
---

# Hindi Animated Story Writer

A production skill for writing and producing **~20-minute, family-friendly Hindi (Devanagari) animated stories** — from story architecture all the way to synced line-by-line audio in a local HTML Story Studio.

## What this skill does

It turns a story idea into a fully produced package:

1. A tightly-architected Hindi story with mystery, distinct characters, and an earned moral.
2. A single canonical **`story.json`** that is the source of truth for everything downstream.
3. Exported scripts (`script.txt`, `script.md`) generated *from* `story.json`.
4. A local **HTML Story Studio** to read/play the story.
5. **Line-by-line audio** generated via **Gemini TTS**, synced to highlighted lines in the Studio.

## When to use it

Use this skill when the user wants to **write, produce, or edit** a Hindi animated story — especially when they need a consistent structure across script, HTML, and audio, or when they want narration/dialogue audio that stays in sync with the on-screen text. Also use it to validate, regenerate, or export an existing story.

## The 8-phase pipeline (overview)

1. **Story Engine** — architect premise, characters, mystery, scenes.
2. **Canonical Story Data** — write the single-source-of-truth `story.json`.
3. **Script Export** — generate `script.txt` / `script.md` from `story.json`.
4. **HTML Studio** — build/refresh the local Story Studio UI.
5. **Gemini TTS** — synthesize audio per spoken/narration line.
6. **Audio + HTML Integration** — sync audio to highlighted lines.
7. **Edit / Regenerate** — edit `story.json`, regenerate only what changed.
8. **Unified Workflow** — `scripts/build.py`, the unified entry point that validates, exports, syncs the studio, and (optionally) generates audio in one command.

See [`references/production-pipeline.md`](references/production-pipeline.md) for the full detail, including the **Unified build & incremental edit workflow**.

## Golden rules

- **Single source of truth = `story.json`.** Scripts, HTML, and audio metadata are *generated* from it. Never maintain independent copies.
- **Every spoken line has an explicit speaker.** Use `**नाम:** "..."` in prose and an explicit `speaker` field in `story.json`. Validate before final output.
- **Stable unit IDs.** Scenes and beats keep stable IDs (e.g. `s01`, `s01_b01`) so audio can be reused when text is unchanged.
- **Gemini via `GEMINI_API_KEY` env var — never hardcoded.** Config stays separate from code.
- **Reuse unchanged audio.** Only regenerate audio for beats whose text/speaker changed.
- **No fake capabilities.** Never claim audio was generated, Gemini connected, the server is running, or tests passed unless it was actually verified.

## Default story parameters

- **Language / script:** Hindi in Devanagari.
- **Duration:** ~20 minutes.
- **Length:** ~2,800–3,300 words.
- **Characters:** 2, 5, or 8 main characters (pick per request).
- **Tone:** family-friendly.
- **Cast rule:** at least one important female character by default.

## Reference files

- [`references/epic-emotional-fantasy.md`](references/epic-emotional-fantasy.md) — **advanced architecture model applied to every story**: outer/inner story, personal-problem opening, gradual world expansion, emotionally escalating multi-stage journey, false belief, layered mysteries, morally complex supernatural forces, secret history, earned sacrifices/payoffs, originality engine, internal blueprint + final editorial test.
- [`references/story-architecture.md`](references/story-architecture.md) — story skeleton, causal chain, pacing, Story DNA.
- [`references/character-design.md`](references/character-design.md) — cast sizes, roles, display format, arcs.
- [`references/mystery-engine.md`](references/mystery-engine.md) — clues, red herrings, fair-play reveal.
- [`references/dialogue-rules.md`](references/dialogue-rules.md) — the absolute speaker-attribution rule.
- [`references/quality-control.md`](references/quality-control.md) — phase checklists + final Quality Audit.
- [`references/production-pipeline.md`](references/production-pipeline.md) — the full 8-phase pipeline.

## Examples

- [`examples/good-story.md`](examples/good-story.md) — a short well-structured Hindi excerpt.
- [`examples/dialogue-format.md`](examples/dialogue-format.md) — correct vs incorrect attribution.
- [`examples/structured-story-example.json`](examples/structured-story-example.json) — a small canonical `story.json`.

## Story Studio

The `studio/` directory is a dependency-free, vanilla HTML/CSS/JS local viewer that reads **directly from the canonical `story.json`** (never a duplicated copy of the text). It renders the header (title/overview/moral + progress), a scene list, a characters panel, and a scrollable transcript of all beats. Navigation and audio sync are **by stable beat id** — Prev/Next/Play/Pause/Resume move a `.current` highlight, and (when `studio/audio/metadata.json` is present) drive a single HTML5 audio element; with no audio it still advances the highlight and shows a `missing-audio` state.

Place `story.json` (and an optional `audio/` + `audio/metadata.json`) alongside `studio/index.html`, then start the local server yourself:

```
python3 studio/serve.py [--port 8765] [--root <dir>]
```

Then open `http://127.0.0.1:8765/`. The server must be started by you — this repo does not auto-run it. See [`studio/README.md`](studio/README.md) for details.

## Scripts

The `scripts/` directory holds dependency-free Python 3 (standard library only) tooling that operates on the canonical `story.json`. Run them yourself:

```
python3 scripts/story_validator.py <story.json>
python3 scripts/script_exporter.py <story.json> --outdir story
python3 scripts/reconstruct_check.py <story.json>
```

- `story_validator.py` — validates required fields, unique scene/character/beat IDs, non-empty speaker/text, valid beat `type`, `character_id` references, and positive strictly-increasing per-scene `sequence` values. Exit 0 = valid, non-zero = invalid. `--quiet` prints only `PASS`/`FAIL`. Exposes an importable `validate_story(data) -> list[str]`.
- `script_exporter.py` — validates first (refuses to export on any error), then writes `<outdir>/script.md` and `<outdir>/script.txt` from the canonical data only, preserving scene order then ascending `sequence`.
- `reconstruct_check.py` — reconstructs the ordered beat list, prints scene/beat counts and a per-scene listing; exits non-zero if any beat lacks a speaker or text.
- `story_schema.json` — JSON Schema (draft-07) describing the canonical `story.json` shape.
- `gemini_tts.py` — isolated Gemini TTS adapter (see Audio section). All Gemini-specific logic lives only here.
- `generate_audio.py` — generates per-beat audio via Gemini TTS (see Audio section).
- `audio_validator.py` — validates generated audio against `audio/metadata.json` (see Audio section).

**Always validate before every export / HTML / audio step.** `story.json` is the single source of truth — never edit generated scripts, HTML, or audio metadata directly; regenerate them from `story.json`.

## Build & edit workflow

`scripts/build.py` is the **unified entry point** that runs the whole pipeline off `story.json`: validate → export `script.md`/`script.txt` (into a `story/` dir beside the source) → copy the canonical `story.json` into `studio/story.json` → (optionally) generate audio into `studio/audio/`. It never modifies `story.json` and imports the other scripts as modules (one implementation of each stage).

```
python3 scripts/build.py story.json --with-audio        # full build (validate → export → sync HTML → audio)
python3 scripts/build.py story.json                     # no-audio refresh (prints a reminder audio is stale)
```

Then serve the Studio and open the printed URL:

```
python3 studio/serve.py --root studio
```

To change a line, edit the canonical data and rebuild only that beat's audio:

```
python3 scripts/edit_beat.py story.json --beat s03_b07 --text "..."
python3 scripts/build.py story.json --with-audio --only s03_b07
```

`edit_beat.py` updates the beat's `text` (optionally `--speaker` / `--character-id`), re-validates the whole story, and writes `story.json` back as pretty-printed UTF-8 (Devanagari preserved). Because the text change updates that beat's `text_hash`, only that beat's audio is regenerated while all other beats reuse their existing audio; sync stays correct because it is keyed by the stable `beat_id`. Full detail, including the golden rules, is in [`references/production-pipeline.md`](references/production-pipeline.md#unified-build--incremental-edit-workflow).

## Audio (Gemini TTS)

Phase 5 turns each beat into a spoken audio line via **Gemini TTS**, keyed by stable beat id so the Story Studio can sync playback to the highlighted line. All tooling is Python 3 **standard library only**.

### Set your API key (never committed)

The key is read from the environment at runtime and is **never hardcoded, committed, or printed** (error messages mask it, e.g. `abcd…yz`):

```
export GEMINI_API_KEY=...
```

### Generate audio

```
python3 scripts/generate_audio.py <story.json> [--outdir DIR] [--voices <path>] [--only BEAT_ID] [--force] [--dry-run]
```

- Validates `story.json` first and refuses on any error.
- Default `--outdir` is the directory containing `story.json`; audio is written to `<outdir>/audio/` with a manifest at `<outdir>/audio/metadata.json`.
- Default `--voices` is `studio/voice_profiles.json` (a given path is resolved relative to the current directory).
- `--dry-run` — no network and no writes: prints a per-beat plan (`GENERATE` / `REUSE` / `SKIP` + chosen voice) and exits. Works even without an API key.
- `--only BEAT_ID` — (re)generate just that one beat.
- `--force` — regenerate even when a beat is unchanged.

### Editing voices — `studio/voice_profiles.json`

Map characters/speakers to voices here (no code changes needed):

```json
{
  "default": { "voice_name": "Kore", "language_code": "hi-IN" },
  "by_character_id": { "titli": { "voice_name": "Leda", "language_code": "hi-IN" } },
  "by_speaker": { "कथावाचक": { "voice_name": "Kore", "language_code": "hi-IN" } }
}
```

Voice resolution priority per beat: `by_character_id[character_id]` → `by_speaker[speaker]` → `default`.

**Valid Gemini voice names (30):** Zephyr, Puck, Charon, Kore, Fenrir, Leda, Orus, Aoede, Callirrhoe, Autonoe, Enceladus, Iapetus, Umbriel, Algieba, Despina, Erinome, Algenib, Rasalgethi, Laomedeia, Achernar, Alnilam, Schedar, Gacrux, Pulcherrima, Achird, Zubenelgenubi, Vindemiatrix, Sadachbia, Sadaltager, Sulafat.

### Model and audio format

- Model: `gemini-2.5-flash-preview-tts`.
- WAV output: **24 kHz, mono, 16-bit PCM** (signed little-endian).

### `audio/metadata.json` schema

A JSON array; one entry per beat:

```json
{
  "beat_id": "s01_b01",
  "scene_id": "s01",
  "sequence": 1,
  "speaker": "कथावाचक",
  "character_id": null,
  "text_hash": "<sha256 of text|voice_name|language_code>",
  "voice_name": "Kore",
  "language_code": "hi-IN",
  "audio_path": "audio/s01_b01.wav",
  "status": "ok",
  "duration_seconds": 3.21,
  "provider": "gemini",
  "model": "gemini-2.5-flash-preview-tts",
  "generated_at": "2024-01-01T00:00:00Z"
}
```

### Incremental + resumable rules

- **Incremental:** a beat is reused/skipped when a prior `ok` entry has the same `text_hash` and `voice_name` and its `.wav` still exists — unless `--force`.
- **text_hash** = `sha256(text + "|" + voice_name + "|" + language_code)`, so any text or voice change forces regeneration.
- **Resumable:** beats are processed one at a time; on failure the entry is marked `failed` (prior successes are kept) and `metadata.json` is rewritten after **each** beat, so a re-run continues where it left off.

### Validate the audio

```
python3 scripts/audio_validator.py <audio_dir_or_metadata.json> [--story story.json]
```

Confirms every `ok` entry's `.wav` exists, is non-empty, and matches its `beat_id`; flags orphan wavs, `failed`/`pending` entries, and (with `--story`) beats missing audio or metadata entries not in the story. Exits non-zero on any inconsistency.

### Isolation

All Gemini-specific request shaping, endpoint details, and response parsing live **only** in `scripts/gemini_tts.py`; the rest of the pipeline stays provider-agnostic.
