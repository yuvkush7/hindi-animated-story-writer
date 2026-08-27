#!/usr/bin/env python3
"""Generate line-by-line audio for a canonical story.json via Gemini TTS.

Uses ONLY the Python 3 standard library. The Gemini-specific logic lives in
gemini_tts.py (imported from the same directory); this script orchestrates
selection, incremental reuse, resumable writes, and metadata bookkeeping.

CLI:
    python3 scripts/generate_audio.py <story.json> [--outdir DIR] \\
        [--voices <path>] [--only BEAT_ID] [--force] [--dry-run]

Behavior summary:
  - Validates the story first (via story_validator.validate_story); refuses on
    any error.
  - Default --outdir is the directory containing story.json. Audio is written
    to <outdir>/audio/ and a manifest is kept at <outdir>/audio/metadata.json.
  - Default --voices is <skill>/studio/voice_profiles.json; a given path is
    resolved relative to the current working directory.
  - Beats are processed in canonical order: scene array order, then ascending
    beat 'sequence'.
  - Voice resolution: by_character_id[character_id] -> by_speaker[speaker]
    -> default.
  - text_hash = sha256(text + "|" + voice_name + "|" + language_code).
  - Incremental: a matching prior "ok" entry (same text_hash + voice_name)
    whose wav file exists is reused/skipped unless --force.
  - --only BEAT_ID regenerates just that beat.
  - Resumable: beats are processed one at a time; synthesis failures are
    recorded (status "failed") without discarding prior successes, and
    metadata.json is written after EACH beat.
  - --dry-run performs NO network calls and NO writes; it prints the plan and
    exits, and works even without an API key.
  - The API key is never printed.
"""

import argparse
import datetime
import hashlib
import json
import os
import sys

# Make sibling modules importable regardless of CWD.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from story_validator import validate_story  # noqa: E402
import gemini_tts  # noqa: E402


SAMPLE_RATE = 24000
PROVIDER = "gemini"


def _now_iso():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _load_json(path):
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def _sorted_beats(scene):
    beats = scene.get("beats") or []

    def key(item):
        idx, beat = item
        seq = beat.get("sequence")
        if isinstance(seq, int) and not isinstance(seq, bool):
            return (0, seq, idx)
        return (1, 0, idx)

    ordered = sorted(enumerate(beats), key=key)
    return [beat for _, beat in ordered]


def iter_beats(story):
    """Yield (scene, beat) in canonical order: scene order, then ascending seq."""
    for scene in (story.get("scenes") or []):
        for beat in _sorted_beats(scene):
            yield scene, beat


def resolve_voice(beat, voices):
    """Pick {voice_name, language_code} for a beat.

    Priority: by_character_id[character_id] -> by_speaker[speaker] -> default.
    """
    default = voices.get("default") or {}
    by_char = voices.get("by_character_id") or {}
    by_speaker = voices.get("by_speaker") or {}

    cid = beat.get("character_id")
    if cid and cid in by_char:
        chosen = by_char[cid]
    else:
        speaker = beat.get("speaker")
        if speaker and speaker in by_speaker:
            chosen = by_speaker[speaker]
        else:
            chosen = default

    voice_name = chosen.get("voice_name") or default.get("voice_name") or "Kore"
    language_code = chosen.get("language_code") or default.get("language_code") or "hi-IN"
    return voice_name, language_code


def text_hash(text, voice_name, language_code):
    payload = (text or "") + "|" + voice_name + "|" + language_code
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def load_metadata(meta_path):
    if not os.path.isfile(meta_path):
        return []
    try:
        data = _load_json(meta_path)
    except (ValueError, OSError):
        return []
    if isinstance(data, list):
        return data
    if isinstance(data, dict) and isinstance(data.get("entries"), list):
        return data["entries"]
    return []


def write_metadata(meta_path, entries):
    with open(meta_path, "w", encoding="utf-8") as fh:
        json.dump(entries, fh, ensure_ascii=False, indent=2)
        fh.write("\n")


def parse_args(argv):
    p = argparse.ArgumentParser(description="Generate Gemini TTS audio for a story.json")
    p.add_argument("story", help="Path to the canonical story.json")
    p.add_argument("--outdir", default=None,
                   help="Output directory (default: directory of story.json)")
    p.add_argument("--voices", default=None,
                   help="Path to voice_profiles.json (default: <skill>/studio/voice_profiles.json)")
    p.add_argument("--only", default=None, help="Regenerate only this beat id")
    p.add_argument("--force", action="store_true", help="Regenerate even if unchanged")
    p.add_argument("--dry-run", action="store_true",
                   help="No network, no writes: print the plan and exit")
    return p.parse_args(argv)


def default_voices_path():
    # scripts/ -> skill root -> studio/voice_profiles.json
    skill_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(skill_root, "studio", "voice_profiles.json")


def main(argv=None):
    args = parse_args(argv if argv is not None else sys.argv[1:])

    story_path = args.story
    try:
        doc = _load_json(story_path)
    except FileNotFoundError:
        sys.stderr.write("Error: file not found: %s\n" % story_path)
        return 2
    except ValueError as exc:
        sys.stderr.write("Error: malformed JSON in %s: %s\n" % (story_path, exc))
        return 2
    except OSError as exc:
        sys.stderr.write("Error: could not read %s: %s\n" % (story_path, exc))
        return 2

    errors = validate_story(doc)
    if errors:
        sys.stderr.write("Refusing to generate audio: story is invalid (%d error%s).\n"
                         % (len(errors), "" if len(errors) == 1 else "s"))
        for err in errors:
            sys.stderr.write("  - %s\n" % err)
        return 1

    story = doc["story"]

    outdir = args.outdir or os.path.dirname(os.path.abspath(story_path))
    audio_dir = os.path.join(outdir, "audio")
    meta_path = os.path.join(audio_dir, "metadata.json")

    voices_path = args.voices if args.voices else default_voices_path()
    try:
        voices = _load_json(voices_path)
    except (FileNotFoundError, OSError):
        sys.stderr.write("Error: voice profiles not found: %s\n" % voices_path)
        return 2
    except ValueError as exc:
        sys.stderr.write("Error: malformed voice profiles %s: %s\n" % (voices_path, exc))
        return 2

    beats = list(iter_beats(story))

    # ---------- Dry run: plan only, no network, no writes. ----------
    if args.dry_run:
        existing = {}
        for e in load_metadata(meta_path):
            if e.get("beat_id"):
                existing[e["beat_id"]] = e
        print("DRY RUN — no network, no writes.")
        print("Story:  %s" % story_path)
        print("Outdir: %s" % outdir)
        print("Audio:  %s" % audio_dir)
        print("Voices: %s" % voices_path)
        print("")
        for scene, beat in beats:
            bid = beat.get("id")
            voice_name, language_code = resolve_voice(beat, voices)
            th = text_hash(beat.get("text", ""), voice_name, language_code)
            if args.only and bid != args.only:
                action = "SKIP (not selected by --only)"
            else:
                prior = existing.get(bid)
                wav_rel = "audio/%s.wav" % bid
                wav_abs = os.path.join(outdir, wav_rel)
                if (not args.force and prior and prior.get("status") == "ok"
                        and prior.get("text_hash") == th
                        and prior.get("voice_name") == voice_name
                        and os.path.isfile(wav_abs)):
                    action = "REUSE (unchanged)"
                else:
                    action = "GENERATE"
            print("  [%s] %s  voice=%s (%s)  speaker=%s"
                  % (bid, action, voice_name, language_code, beat.get("speaker")))
        return 0

    # ---------- Real run. ----------
    try:
        os.makedirs(audio_dir, exist_ok=True)
    except OSError as exc:
        sys.stderr.write("Error: could not create audio dir %s: %s\n" % (audio_dir, exc))
        return 2

    entries = load_metadata(meta_path)
    entry_by_beat = {}
    for e in entries:
        if e.get("beat_id"):
            entry_by_beat[e["beat_id"]] = e

    generated = reused = failed = 0
    total = len(beats)

    for scene, beat in beats:
        bid = beat.get("id")
        text = beat.get("text", "")
        voice_name, language_code = resolve_voice(beat, voices)
        th = text_hash(text, voice_name, language_code)
        wav_rel = "audio/%s.wav" % bid
        wav_abs = os.path.join(outdir, wav_rel)

        # --only: leave other beats' existing entries untouched.
        if args.only and bid != args.only:
            continue

        prior = entry_by_beat.get(bid)
        if (not args.force
                and prior and prior.get("status") == "ok"
                and prior.get("text_hash") == th
                and prior.get("voice_name") == voice_name
                and os.path.isfile(wav_abs)):
            # Unchanged and already synthesized: reuse. --only alone still
            # respects unchanged reuse unless --force is given.
            reused += 1
            print("REUSE [%s] (unchanged)" % bid)
            continue

        entry = {
            "beat_id": bid,
            "scene_id": scene.get("id"),
            "sequence": beat.get("sequence"),
            "speaker": beat.get("speaker"),
            "character_id": beat.get("character_id"),
            "text_hash": th,
            "voice_name": voice_name,
            "language_code": language_code,
            "audio_path": wav_rel,
            "status": "pending",
            "duration_seconds": None,
            "provider": PROVIDER,
            "model": gemini_tts.DEFAULT_MODEL,
            "generated_at": _now_iso(),
        }

        try:
            pcm = gemini_tts.synthesize_line(
                text=text,
                voice_name=voice_name,
                language_code=language_code,
                model=gemini_tts.DEFAULT_MODEL,
            )
            gemini_tts.pcm_to_wav(pcm, wav_abs, rate=SAMPLE_RATE)
            entry["status"] = "ok"
            entry["duration_seconds"] = len(pcm) / 2 / SAMPLE_RATE
            entry["generated_at"] = _now_iso()
            generated += 1
            print("GENERATE [%s] ok (%.2fs, voice=%s)"
                  % (bid, entry["duration_seconds"], voice_name))
        except gemini_tts.GeminiConfigError as exc:
            entry["status"] = "failed"
            entry["error"] = str(exc)
            failed += 1
            sys.stderr.write("FAILED [%s]: %s\n" % (bid, exc))
        except gemini_tts.GeminiAPIError as exc:
            entry["status"] = "failed"
            entry["error"] = str(exc)
            failed += 1
            sys.stderr.write("FAILED [%s]: %s\n" % (bid, exc))
        except OSError as exc:
            entry["status"] = "failed"
            entry["error"] = "write error: %s" % exc
            failed += 1
            sys.stderr.write("FAILED [%s]: write error: %s\n" % (bid, exc))

        # Update manifest after EACH beat (resumable) — keep prior successes.
        entry_by_beat[bid] = entry
        # Preserve manifest order: rebuild in canonical order for known beats,
        # keeping any unknown/extra entries at the end.
        ordered_entries = []
        seen = set()
        for s2, b2 in beats:
            b2id = b2.get("id")
            if b2id in entry_by_beat and b2id not in seen:
                ordered_entries.append(entry_by_beat[b2id])
                seen.add(b2id)
        for e in entries:
            eid = e.get("beat_id")
            if eid and eid not in seen and eid not in {b.get("id") for _, b in beats}:
                ordered_entries.append(entry_by_beat.get(eid, e))
                seen.add(eid)
        entries = ordered_entries
        try:
            write_metadata(meta_path, entries)
        except OSError as exc:
            sys.stderr.write("Error: could not write metadata %s: %s\n" % (meta_path, exc))
            return 2

    print("")
    print("Summary: generated=%d reused=%d failed=%d total=%d"
          % (generated, reused, failed, total))
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
