#!/usr/bin/env python3
"""Validate a canonical story.json for the Hindi animated story writer skill.

Uses only the Python 3 standard library. No external dependencies.

CLI:
    python3 story_validator.py <story.json> [--quiet]

Exit code 0 means valid, non-zero means invalid or an error occurred.
`--quiet` prints only PASS or FAIL.

Reusable API:
    validate_story(data) -> list[str]
        Returns a list of human-readable error strings. An empty list means
        the story is valid. Other scripts can import this function.
"""

import json
import sys


VALID_BEAT_TYPES = {"narration", "dialogue"}


def validate_story(data):
    """Validate a parsed story document.

    Args:
        data: the parsed JSON (a dict) representing the whole document with a
            top-level "story" key.

    Returns:
        A list of error strings. Empty list means the document is valid.
    """
    errors = []

    if not isinstance(data, dict):
        return ["Top-level JSON must be an object with a 'story' key."]

    story = data.get("story")
    if story is None:
        return ["Missing required top-level key: 'story'."]
    if not isinstance(story, dict):
        return ["'story' must be an object."]

    # Required top-level (story-level) fields.
    title = story.get("title")
    if not isinstance(title, str) or not title.strip():
        errors.append("story.title: required non-empty string is missing.")

    characters = story.get("characters")
    if not isinstance(characters, list):
        errors.append("story.characters: required array is missing.")
        characters = []

    scenes = story.get("scenes")
    if not isinstance(scenes, list):
        errors.append("story.scenes: required array is missing.")
        scenes = []

    # ---- Characters: collect ids, detect duplicates. ----
    character_ids = set()
    seen_char_ids = set()
    for idx, ch in enumerate(characters):
        if not isinstance(ch, dict):
            errors.append("character[%d]: must be an object." % idx)
            continue
        cid = ch.get("id")
        if not isinstance(cid, str) or not cid.strip():
            errors.append("character[%d]: missing non-empty 'id'." % idx)
            continue
        if cid in seen_char_ids:
            errors.append("character id '%s': duplicate character id." % cid)
        else:
            seen_char_ids.add(cid)
        character_ids.add(cid)

    # ---- Scenes and beats. ----
    seen_scene_ids = set()
    seen_beat_ids = set()  # duplicate beat ids across the whole story

    for s_idx, scene in enumerate(scenes):
        if not isinstance(scene, dict):
            errors.append("scene[%d]: must be an object." % s_idx)
            continue

        sid = scene.get("id")
        scene_label = sid if isinstance(sid, str) and sid.strip() else ("scene[%d]" % s_idx)

        if not isinstance(sid, str) or not sid.strip():
            errors.append("%s: missing non-empty 'id'." % scene_label)
        else:
            if sid in seen_scene_ids:
                errors.append("scene id '%s': duplicate scene id." % sid)
            else:
                seen_scene_ids.add(sid)

        stitle = scene.get("title")
        if not isinstance(stitle, str) or not stitle.strip():
            errors.append("%s: missing non-empty 'title'." % scene_label)

        beats = scene.get("beats")
        if beats is None:
            beats = []
        if not isinstance(beats, list):
            errors.append("%s: 'beats' must be an array." % scene_label)
            continue

        prev_sequence = None
        for b_idx, beat in enumerate(beats):
            if not isinstance(beat, dict):
                errors.append("%s beat[%d]: must be an object." % (scene_label, b_idx))
                continue

            bid = beat.get("id")
            beat_label = bid if isinstance(bid, str) and bid.strip() else ("%s beat[%d]" % (scene_label, b_idx))

            # Non-empty id.
            if not isinstance(bid, str) or not bid.strip():
                errors.append("%s: missing non-empty beat 'id'." % beat_label)
            else:
                if bid in seen_beat_ids:
                    errors.append("beat id '%s': duplicate beat id." % bid)
                else:
                    seen_beat_ids.add(bid)

            # Non-empty speaker.
            speaker = beat.get("speaker")
            if not isinstance(speaker, str) or not speaker.strip():
                errors.append("%s: missing non-empty 'speaker'." % beat_label)

            # Non-empty text.
            text = beat.get("text")
            if not isinstance(text, str) or not text.strip():
                errors.append("%s: missing non-empty 'text'." % beat_label)

            # Type in allowed set (when present).
            btype = beat.get("type")
            if btype is not None and btype not in VALID_BEAT_TYPES:
                errors.append(
                    "%s: invalid type '%s' (must be one of %s)."
                    % (beat_label, btype, ", ".join(sorted(VALID_BEAT_TYPES)))
                )

            # character_id (when present) must reference an existing character.
            char_id = beat.get("character_id")
            if char_id is not None:
                if not isinstance(char_id, str) or not char_id.strip():
                    errors.append("%s: 'character_id' must be a non-empty string when present." % beat_label)
                elif char_id not in character_ids:
                    errors.append(
                        "%s: character_id '%s' does not reference any character id."
                        % (beat_label, char_id)
                    )

            # Sequence: positive int, strictly increasing in array order.
            seq = beat.get("sequence")
            if seq is None:
                errors.append("%s: missing 'sequence'." % beat_label)
            elif not isinstance(seq, int) or isinstance(seq, bool):
                errors.append("%s: 'sequence' must be an integer." % beat_label)
            elif seq < 1:
                errors.append("%s: 'sequence' must be a positive integer (got %r)." % (beat_label, seq))
            else:
                if prev_sequence is not None:
                    if seq == prev_sequence:
                        errors.append(
                            "%s: duplicate 'sequence' value %d within scene '%s'."
                            % (beat_label, seq, scene_label)
                        )
                    elif seq < prev_sequence:
                        errors.append(
                            "%s: 'sequence' %d is not increasing (previous was %d) within scene '%s'."
                            % (beat_label, seq, prev_sequence, scene_label)
                        )
                    elif seq > prev_sequence + 1:
                        errors.append(
                            "%s: 'sequence' gap in scene '%s' (jumped from %d to %d)."
                            % (beat_label, scene_label, prev_sequence, seq)
                        )
                prev_sequence = seq

    return errors


def _load_json(path):
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def main(argv):
    args = [a for a in argv[1:]]
    quiet = False
    positional = []
    for a in args:
        if a == "--quiet":
            quiet = True
        else:
            positional.append(a)

    if len(positional) != 1:
        sys.stderr.write("Usage: python3 story_validator.py <story.json> [--quiet]\n")
        return 2

    path = positional[0]

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

    errors = validate_story(data)

    if quiet:
        print("PASS" if not errors else "FAIL")
        return 0 if not errors else 1

    if not errors:
        print("VALID: %s passed all checks." % path)
        return 0

    print("INVALID: %s (%d error%s)" % (path, len(errors), "" if len(errors) == 1 else "s"))
    for err in errors:
        print("  - %s" % err)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
