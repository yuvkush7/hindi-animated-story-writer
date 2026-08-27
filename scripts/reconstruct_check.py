#!/usr/bin/env python3
"""Reconstruct and sanity-check the ordered beat list from a story.json.

Uses only the Python 3 standard library. No external dependencies.

CLI:
    python3 reconstruct_check.py <story.json>

Reconstructs the ordered (scene, sequence, speaker, text) list from the
canonical data, prints the count of scenes and beats plus a per-scene beat
listing. Exits non-zero if any beat lacks a speaker or text.
"""

import json
import sys


def _sorted_beats(scene):
    """Return beats ordered by ascending 'sequence' (missing sorts last)."""
    beats = scene.get("beats") or []

    def key(item):
        idx, beat = item
        seq = beat.get("sequence")
        if isinstance(seq, int) and not isinstance(seq, bool):
            return (0, seq, idx)
        return (1, 0, idx)

    ordered = sorted(enumerate(beats), key=key)
    return [beat for _, beat in ordered]


def reconstruct(story):
    """Build a flat ordered list of (scene_id, sequence, speaker, text) tuples."""
    rows = []
    for scene in (story.get("scenes") or []):
        sid = scene.get("id", "")
        for beat in _sorted_beats(scene):
            rows.append((
                sid,
                beat.get("sequence"),
                beat.get("speaker"),
                beat.get("text"),
                beat.get("id"),
            ))
    return rows


def _load_json(path):
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def main(argv):
    args = argv[1:]
    if len(args) != 1:
        sys.stderr.write("Usage: python3 reconstruct_check.py <story.json>\n")
        return 2

    path = args[0]

    try:
        data = _load_json(path)
    except FileNotFoundError:
        sys.stderr.write("Error: file not found: %s\n" % path)
        return 2
    except json.JSONDecodeError as exc:
        sys.stderr.write("Error: malformed JSON in %s: %s\n" % (path, exc))
        return 2
    except OSError as exc:
        sys.stderr.write("Error: could not read %s: %s\n" % (path, exc))
        return 2

    if not isinstance(data, dict) or not isinstance(data.get("story"), dict):
        sys.stderr.write("Error: missing top-level 'story' object.\n")
        return 2

    story = data["story"]
    scenes = story.get("scenes") or []
    rows = reconstruct(story)

    print("Scenes: %d" % len(scenes))
    print("Beats:  %d" % len(rows))
    print("")

    problems = 0
    for scene in scenes:
        sid = scene.get("id", "")
        stitle = scene.get("title", "")
        ordered = _sorted_beats(scene)
        print("Scene %s — %s (%d beats)" % (sid, stitle, len(ordered)))
        for beat in ordered:
            bid = beat.get("id", "")
            seq = beat.get("sequence")
            speaker = beat.get("speaker")
            text = beat.get("text")

            missing = []
            if not (isinstance(speaker, str) and speaker.strip()):
                missing.append("speaker")
            if not (isinstance(text, str) and text.strip()):
                missing.append("text")

            if missing:
                problems += 1
                print("  [%s] seq=%s MISSING %s" % (bid, seq, ", ".join(missing)))
            else:
                print("  [%s] seq=%s %s: %s" % (bid, seq, speaker, text))
        print("")

    if problems:
        sys.stderr.write("FAIL: %d beat(s) missing speaker or text.\n" % problems)
        return 1

    print("OK: every beat has a speaker and text.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
