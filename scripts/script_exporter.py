#!/usr/bin/env python3
"""Export a canonical story.json to human-readable script files.

Uses only the Python 3 standard library. No external dependencies.

CLI:
    python3 script_exporter.py <story.json> [--outdir story]

Writes <outdir>/script.md and <outdir>/script.txt from the canonical data
only. Validation runs first (via story_validator.validate_story); if there are
any errors the export is refused, the errors are printed, and the process exits
non-zero.

Ordering is preserved exactly: scenes in array order, then beats in ascending
'sequence' within each scene. No lines are dropped or duplicated.
"""

import json
import os
import sys

try:
    # Normal import when run from the scripts/ directory.
    from story_validator import validate_story
except ImportError:  # pragma: no cover - fallback when run from elsewhere
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from story_validator import validate_story


def _sorted_beats(scene):
    """Return beats ordered by ascending 'sequence'.

    A missing sequence sorts last but keeps a stable relative order.
    """
    beats = scene.get("beats") or []

    def key(item):
        idx, beat = item
        seq = beat.get("sequence")
        if isinstance(seq, int) and not isinstance(seq, bool):
            return (0, seq, idx)
        return (1, 0, idx)

    ordered = sorted(enumerate(beats), key=key)
    return [beat for _, beat in ordered]


def _is_dialogue(beat):
    btype = beat.get("type")
    if btype == "dialogue":
        return True
    if btype == "narration":
        return False
    # No explicit type: treat as dialogue if it references a character.
    return bool(beat.get("character_id"))


def build_markdown(story):
    lines = []
    title = story.get("title", "")
    lines.append("# %s" % title)
    lines.append("")

    overview = story.get("overview")
    if overview:
        lines.append("## Overview")
        lines.append("")
        lines.append(overview)
        lines.append("")

    characters = story.get("characters") or []
    if characters:
        lines.append("## Characters")
        lines.append("")
        for ch in characters:
            name = ch.get("name", "")
            age = ch.get("age", "")
            gender = ch.get("gender", "")
            role = ch.get("role", "")
            lines.append("- %s — %s — %s — %s" % (name, age, gender, role))
        lines.append("")

    lines.append("## Story")
    lines.append("")
    scenes = story.get("scenes") or []
    for n, scene in enumerate(scenes, start=1):
        location = scene.get("location", "")
        time = scene.get("time", "")
        lines.append("### दृश्य %d — %s / %s" % (n, location, time))
        lines.append("")
        for beat in _sorted_beats(scene):
            speaker = beat.get("speaker", "")
            text = beat.get("text", "")
            if _is_dialogue(beat):
                lines.append('**%s:** "%s"' % (speaker, text))
            else:
                lines.append("**%s:** %s" % (speaker, text))
            lines.append("")

    moral = story.get("moral")
    if moral:
        lines.append("## Moral")
        lines.append("")
        lines.append(moral)
        lines.append("")

    return "\n".join(lines).rstrip("\n") + "\n"


def build_text(story):
    lines = []
    title = story.get("title", "")
    lines.append(title)
    lines.append("=" * max(1, len(title)))
    lines.append("")

    overview = story.get("overview")
    if overview:
        lines.append("Overview")
        lines.append("--------")
        lines.append(overview)
        lines.append("")

    characters = story.get("characters") or []
    if characters:
        lines.append("Characters")
        lines.append("----------")
        for ch in characters:
            name = ch.get("name", "")
            age = ch.get("age", "")
            gender = ch.get("gender", "")
            role = ch.get("role", "")
            lines.append("%s — %s — %s — %s" % (name, age, gender, role))
        lines.append("")

    lines.append("Story")
    lines.append("-----")
    lines.append("")
    scenes = story.get("scenes") or []
    for n, scene in enumerate(scenes, start=1):
        location = scene.get("location", "")
        time = scene.get("time", "")
        lines.append("दृश्य %d — %s / %s" % (n, location, time))
        lines.append("")
        for beat in _sorted_beats(scene):
            speaker = beat.get("speaker", "")
            text = beat.get("text", "")
            lines.append("%s: %s" % (speaker, text))
        lines.append("")

    moral = story.get("moral")
    if moral:
        lines.append("Moral")
        lines.append("-----")
        lines.append(moral)
        lines.append("")

    return "\n".join(lines).rstrip("\n") + "\n"


def _load_json(path):
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def main(argv):
    args = argv[1:]
    outdir = "story"
    positional = []
    i = 0
    while i < len(args):
        a = args[i]
        if a == "--outdir":
            if i + 1 >= len(args):
                sys.stderr.write("Error: --outdir requires a value.\n")
                return 2
            outdir = args[i + 1]
            i += 2
            continue
        if a.startswith("--outdir="):
            outdir = a.split("=", 1)[1]
            i += 1
            continue
        positional.append(a)
        i += 1

    if len(positional) != 1:
        sys.stderr.write("Usage: python3 script_exporter.py <story.json> [--outdir story]\n")
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
    if errors:
        sys.stderr.write("Refusing to export: story is invalid (%d error%s).\n"
                         % (len(errors), "" if len(errors) == 1 else "s"))
        for err in errors:
            sys.stderr.write("  - %s\n" % err)
        return 1

    story = data["story"]

    try:
        os.makedirs(outdir, exist_ok=True)
    except OSError as exc:
        sys.stderr.write("Error: could not create outdir %s: %s\n" % (outdir, exc))
        return 2

    md_path = os.path.join(outdir, "script.md")
    txt_path = os.path.join(outdir, "script.txt")

    md = build_markdown(story)
    txt = build_text(story)

    try:
        with open(md_path, "w", encoding="utf-8") as fh:
            fh.write(md)
        with open(txt_path, "w", encoding="utf-8") as fh:
            fh.write(txt)
    except OSError as exc:
        sys.stderr.write("Error: could not write output: %s\n" % exc)
        return 2

    print("Wrote %s" % md_path)
    print("Wrote %s" % txt_path)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
