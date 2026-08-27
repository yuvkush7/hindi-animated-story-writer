#!/usr/bin/env python3
"""Validate generated audio against its metadata (and optionally the story).

Uses ONLY the Python 3 standard library.

CLI:
    python3 scripts/audio_validator.py <audio_dir_or_metadata.json> [--story story.json]

Checks:
  - Loads metadata.json (accepts an audio dir, a metadata.json path, or a
    directory that contains audio/metadata.json).
  - For each entry with status "ok": confirm the .wav file exists, is
    non-empty, and its filename matches the beat_id (<beat_id>.wav).
  - Flags orphan wav files (wavs on disk with no metadata entry).
  - Flags entries with status "failed" or "pending".
  - If --story is given, cross-checks beat ids: beats missing an audio entry,
    and metadata entries referencing unknown beat ids.
  - Prints a clear report and exits non-zero on ANY inconsistency.
"""

import argparse
import json
import os
import sys


def _load_json(path):
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def _resolve_meta_and_dir(target):
    """Return (metadata_path, audio_dir) from a flexible target argument."""
    if os.path.isdir(target):
        # target is a directory: could be the audio dir itself or a parent.
        cand1 = os.path.join(target, "metadata.json")
        cand2 = os.path.join(target, "audio", "metadata.json")
        if os.path.isfile(cand1):
            return cand1, target
        if os.path.isfile(cand2):
            return cand2, os.path.join(target, "audio")
        # Default to expecting metadata.json inside the given dir.
        return cand1, target
    # target is a file (metadata.json).
    return target, os.path.dirname(os.path.abspath(target))


def _load_entries(meta_path):
    data = _load_json(meta_path)
    if isinstance(data, list):
        return data
    if isinstance(data, dict) and isinstance(data.get("entries"), list):
        return data["entries"]
    raise ValueError("metadata.json must be a list or an object with 'entries'.")


def _story_beat_ids(story_path):
    doc = _load_json(story_path)
    story = doc.get("story") if isinstance(doc, dict) else None
    ids = []
    if isinstance(story, dict):
        for scene in (story.get("scenes") or []):
            for beat in (scene.get("beats") or []):
                bid = beat.get("id")
                if bid:
                    ids.append(bid)
    return ids


def parse_args(argv):
    p = argparse.ArgumentParser(description="Validate generated audio vs metadata")
    p.add_argument("target", help="audio dir or path to metadata.json")
    p.add_argument("--story", default=None, help="Optional story.json to cross-check beat ids")
    return p.parse_args(argv)


def main(argv=None):
    args = parse_args(argv if argv is not None else sys.argv[1:])

    meta_path, audio_dir = _resolve_meta_and_dir(args.target)

    if not os.path.isfile(meta_path):
        sys.stderr.write("Error: metadata.json not found: %s\n" % meta_path)
        return 2

    try:
        entries = _load_entries(meta_path)
    except (ValueError, OSError) as exc:
        sys.stderr.write("Error: could not read metadata %s: %s\n" % (meta_path, exc))
        return 2

    problems = []
    report_lines = []

    entry_beat_ids = set()
    referenced_wavs = set()

    for entry in entries:
        bid = entry.get("beat_id")
        status = entry.get("status")
        if bid:
            entry_beat_ids.add(bid)

        if status == "ok":
            rel = entry.get("audio_path") or ("audio/%s.wav" % bid)
            fname = os.path.basename(rel)
            referenced_wavs.add(fname)
            wav_abs = os.path.join(audio_dir, fname)

            # Filename must match beat_id.
            expected = "%s.wav" % bid
            if fname != expected:
                problems.append("beat '%s': audio filename '%s' does not match expected '%s'."
                                % (bid, fname, expected))

            if not os.path.isfile(wav_abs):
                problems.append("beat '%s': audio file missing: %s" % (bid, wav_abs))
            else:
                try:
                    size = os.path.getsize(wav_abs)
                except OSError as exc:
                    size = 0
                    problems.append("beat '%s': cannot stat %s: %s" % (bid, wav_abs, exc))
                if size == 0:
                    problems.append("beat '%s': audio file is empty: %s" % (bid, wav_abs))
        elif status in ("failed", "pending"):
            problems.append("beat '%s': status is '%s'%s"
                            % (bid, status,
                               (" — " + entry["error"]) if entry.get("error") else ""))
        else:
            problems.append("beat '%s': unknown status '%s'." % (bid, status))

    # Orphan wavs: wavs on disk with no metadata entry.
    if os.path.isdir(audio_dir):
        for name in sorted(os.listdir(audio_dir)):
            if name.lower().endswith(".wav") and name not in referenced_wavs:
                problems.append("orphan audio file (no metadata entry): %s"
                                % os.path.join(audio_dir, name))

    # Cross-check against the story if provided.
    if args.story:
        try:
            story_ids = _story_beat_ids(args.story)
        except (ValueError, OSError) as exc:
            sys.stderr.write("Error: could not read story %s: %s\n" % (args.story, exc))
            return 2
        story_id_set = set(story_ids)
        for sid in story_ids:
            if sid not in entry_beat_ids:
                problems.append("story beat '%s' has no audio metadata entry." % sid)
        for eid in entry_beat_ids:
            if eid not in story_id_set:
                problems.append("metadata entry '%s' does not match any story beat id." % eid)

    # ---------- Report ----------
    ok_count = sum(1 for e in entries if e.get("status") == "ok")
    report_lines.append("Metadata: %s" % meta_path)
    report_lines.append("Audio dir: %s" % audio_dir)
    report_lines.append("Entries: %d (ok=%d)" % (len(entries), ok_count))
    if args.story:
        report_lines.append("Cross-checked against story: %s" % args.story)
    report_lines.append("")

    for line in report_lines:
        print(line)

    if problems:
        print("INCONSISTENT: %d problem%s found:"
              % (len(problems), "" if len(problems) == 1 else "s"))
        for p in problems:
            print("  - %s" % p)
        return 1

    print("OK: audio is consistent with metadata%s." %
          (" and story" if args.story else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
