#!/usr/bin/env python3
"""Incremental edit helper for a canonical story.json.

Edits a single beat's text (and optionally its speaker / character_id) in the
canonical ``story.json``, re-validates the WHOLE story, and writes the file
back (pretty-printed UTF-8 with ``ensure_ascii=False`` so Devanagari stays
readable). It then prints the recommended follow-up commands to rebuild.

This helper NEVER touches the network. Changing a beat's text changes its
``text_hash``, so a subsequent ``build.py ... --with-audio --only BEAT_ID`` will
regenerate ONLY that beat's audio and reuse every other beat's existing audio.

Uses ONLY the Python 3 standard library.

CLI:
    python3 scripts/edit_beat.py <story.json> --beat BEAT_ID \\
        --text "<new text>" [--speaker NAME] [--character-id ID]
"""

import argparse
import json
import os
import sys

# Make sibling modules importable regardless of the current working directory.
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from story_validator import validate_story  # noqa: E402


def _load_json(path):
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def find_beat(doc, beat_id):
    """Return (scene, beat) for the given beat id, or (None, None)."""
    story = doc.get("story") if isinstance(doc, dict) else None
    if not isinstance(story, dict):
        return None, None
    for scene in (story.get("scenes") or []):
        if not isinstance(scene, dict):
            continue
        for beat in (scene.get("beats") or []):
            if isinstance(beat, dict) and beat.get("id") == beat_id:
                return scene, beat
    return None, None


def parse_args(argv):
    p = argparse.ArgumentParser(
        description="Edit one beat in story.json, re-validate, and write it back."
    )
    p.add_argument("story", help="Path to the canonical story.json")
    p.add_argument("--beat", required=True, help="Beat id to edit (e.g. s03_b07)")
    p.add_argument("--text", required=True, help="New text for the beat")
    p.add_argument("--speaker", default=None, help="Optional: new speaker name")
    p.add_argument("--character-id", dest="character_id", default=None,
                   help="Optional: new character_id (must reference an existing character)")
    return p.parse_args(argv)


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

    scene, beat = find_beat(doc, args.beat)
    if beat is None:
        sys.stderr.write("Error: beat id '%s' not found in %s.\n" % (args.beat, story_path))
        return 1

    # Apply edits in memory.
    old_text = beat.get("text")
    beat["text"] = args.text
    if args.speaker is not None:
        beat["speaker"] = args.speaker
    if args.character_id is not None:
        beat["character_id"] = args.character_id

    # Re-validate the WHOLE story before writing anything back.
    errors = validate_story(doc)
    if errors:
        sys.stderr.write("Refusing to write: edit made the story invalid (%d error%s).\n"
                         % (len(errors), "" if len(errors) == 1 else "s"))
        for err in errors:
            sys.stderr.write("  - %s\n" % err)
        sys.stderr.write("No changes were written to %s.\n" % story_path)
        return 1

    # Write story.json back, pretty-printed, Devanagari kept readable.
    try:
        with open(story_path, "w", encoding="utf-8") as fh:
            json.dump(doc, fh, ensure_ascii=False, indent=2)
            fh.write("\n")
    except OSError as exc:
        sys.stderr.write("Error: could not write %s: %s\n" % (story_path, exc))
        return 2

    print("Updated beat '%s' in scene '%s'." % (args.beat, scene.get("id")))
    if old_text != args.text:
        print("  text: changed")
    if args.speaker is not None:
        print("  speaker: -> %s" % args.speaker)
    if args.character_id is not None:
        print("  character_id: -> %s" % args.character_id)
    print("Re-validated whole story: OK.")
    print("Wrote %s (UTF-8, Devanagari preserved)." % story_path)
    print("")
    print("Next steps:")
    print("  Changing this beat's text changes its text_hash, so regenerate ONLY")
    print("  this beat's audio (all other beats reuse their existing audio):")
    print("")
    print("    python3 scripts/build.py %s --with-audio --only %s" % (story_path, args.beat))
    print("")
    print("  Or, to refresh script + studio HTML without touching audio:")
    print("")
    print("    python3 scripts/build.py %s" % story_path)
    print("")
    print("  build.py also re-copies story.json into studio/story.json so the HTML")
    print("  shows the new text; playback sync stays correct because it is keyed by")
    print("  the stable beat_id.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
