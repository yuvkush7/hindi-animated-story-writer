#!/usr/bin/env python3
"""Unified build pipeline for the Hindi animated story writer skill.

Enforces the single-source-of-truth rule: ``story.json`` is canonical, and
every downstream artifact (script.md/script.txt, the Story Studio copy of
``story.json``, and audio) is *generated* from it. Nothing downstream ever runs
on invalid data, and ``story.json`` itself is never modified or destroyed here.

Uses ONLY the Python 3 standard library. Sibling scripts are imported as
modules (the scripts/ directory is added to ``sys.path``) so their logic is
reused rather than duplicated.

CLI:
    python3 scripts/build.py <story.json> \\
        [--studio-dir studio] [--with-audio] \\
        [--dry-run-audio] [--force-audio] [--only BEAT_ID] \\
        [--voices <path>]

Stages, in order:
  a. Validate ``story.json`` (via story_validator.validate_story). ABORT with a
     non-zero exit and the error list if invalid.
  b. Export scripts: regenerate ``script.md`` and ``script.txt`` into a
     ``story/`` directory that sits alongside the source ``story.json`` (i.e.
     ``<dir of story.json>/story/``). This keeps generated read-throughs next
     to the source without touching the studio copy.
  c. Sync HTML data: COPY the canonical ``story.json`` into
     ``<studio-dir>/story.json`` (overwrite) so the Story Studio always
     reflects the source of truth. This copy is the ONLY way the studio copy of
     story.json changes — never hand-edit it.
  d. If --with-audio: run generate_audio.main against the studio dir so the
     Studio can fetch ``audio/*.wav`` and ``audio/metadata.json``. Passes
     through --force-audio -> --force, --only, and --dry-run-audio -> --dry-run.
     If not --with-audio, audio is skipped and a reminder is printed that audio
     is stale / needs generation.
  e. Print a clear final summary of what was validated / exported / copied /
     generated. The API key is never printed.

Robustness: each stage is wrapped. If audio generation fails for some beats the
build still reports partial success (canonical data + script + HTML are fine)
and points to ``<studio-dir>/audio/metadata.json`` for the failed beats.
"""

import argparse
import json
import os
import shutil
import sys

# Make sibling modules importable regardless of the current working directory.
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from story_validator import validate_story  # noqa: E402
import script_exporter  # noqa: E402
import generate_audio  # noqa: E402


def _load_json(path):
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def parse_args(argv):
    p = argparse.ArgumentParser(
        description="Unified build pipeline enforcing story.json as the single source of truth."
    )
    p.add_argument("story", help="Path to the canonical story.json")
    p.add_argument("--studio-dir", default="studio",
                   help="Story Studio directory to sync into (default: studio)")
    p.add_argument("--with-audio", action="store_true",
                   help="Also generate/refresh audio into <studio-dir>/audio/")
    p.add_argument("--dry-run-audio", action="store_true",
                   help="Plan audio only: no network, no writes (implies --with-audio behavior for the audio stage)")
    p.add_argument("--force-audio", action="store_true",
                   help="Regenerate audio even for unchanged beats")
    p.add_argument("--only", default=None,
                   help="Restrict audio generation to just this beat id")
    p.add_argument("--voices", default=None,
                   help="Path to voice_profiles.json (default: <skill>/studio/voice_profiles.json)")
    return p.parse_args(argv)


def main(argv=None):
    args = parse_args(argv if argv is not None else sys.argv[1:])

    story_path = args.story
    story_abspath = os.path.abspath(story_path)
    story_dir = os.path.dirname(story_abspath)
    studio_dir = args.studio_dir

    validated = False
    exported = None      # (md_path, txt_path)
    copied_to = None     # studio story.json path
    audio_result = None  # dict describing audio outcome

    print("=" * 60)
    print("Unified build — story.json is the single source of truth")
    print("=" * 60)
    print("Source story.json : %s" % story_abspath)
    print("Studio dir        : %s" % os.path.abspath(studio_dir))
    print("")

    # ---------------------------------------------------------------
    # Stage a: Load + validate. Nothing downstream runs on invalid data.
    # ---------------------------------------------------------------
    print("[1/4] Validate story.json")
    try:
        doc = _load_json(story_path)
    except FileNotFoundError:
        sys.stderr.write("ABORT: file not found: %s\n" % story_path)
        return 2
    except ValueError as exc:
        sys.stderr.write("ABORT: malformed JSON in %s: %s\n" % (story_path, exc))
        return 2
    except OSError as exc:
        sys.stderr.write("ABORT: could not read %s: %s\n" % (story_path, exc))
        return 2

    errors = validate_story(doc)
    if errors:
        sys.stderr.write("ABORT: story is invalid (%d error%s). Nothing downstream will run.\n"
                         % (len(errors), "" if len(errors) == 1 else "s"))
        for err in errors:
            sys.stderr.write("  - %s\n" % err)
        return 1
    validated = True
    print("      OK — story.json is valid.")
    print("")

    # ---------------------------------------------------------------
    # Stage b: Export scripts into <dir of story.json>/story/.
    # ---------------------------------------------------------------
    print("[2/4] Export scripts (script.md / script.txt)")
    export_outdir = os.path.join(story_dir, "story")
    try:
        rc = script_exporter.main(["script_exporter.py", story_abspath, "--outdir", export_outdir])
        if rc != 0:
            # The exporter validates again and refuses on error; since we already
            # validated, this would only happen on a write/IO problem.
            sys.stderr.write("ABORT: script export failed (exit %d).\n" % rc)
            return 1
        exported = (os.path.join(export_outdir, "script.md"),
                    os.path.join(export_outdir, "script.txt"))
        print("      Wrote %s" % exported[0])
        print("      Wrote %s" % exported[1])
    except OSError as exc:
        sys.stderr.write("ABORT: script export failed: %s\n" % exc)
        return 2
    print("")

    # ---------------------------------------------------------------
    # Stage c: Sync HTML data — copy canonical story.json into studio.
    # This is the ONLY way studio/story.json changes.
    # ---------------------------------------------------------------
    print("[3/4] Sync HTML data (copy story.json -> studio/story.json)")
    studio_story_path = os.path.join(studio_dir, "story.json")
    try:
        os.makedirs(studio_dir, exist_ok=True)
        # Guard: never let source and destination be the same file.
        if os.path.abspath(studio_story_path) == story_abspath:
            print("      Source story.json already lives in the studio dir; no copy needed.")
        else:
            shutil.copyfile(story_abspath, studio_story_path)
            print("      Copied -> %s (overwritten to match the source of truth)"
                  % os.path.abspath(studio_story_path))
        copied_to = studio_story_path
    except OSError as exc:
        sys.stderr.write("ABORT: could not sync studio/story.json: %s\n" % exc)
        return 2
    print("")

    # ---------------------------------------------------------------
    # Stage d: Audio (optional).
    # ---------------------------------------------------------------
    print("[4/4] Audio")
    want_audio = args.with_audio or args.dry_run_audio
    if want_audio:
        audio_argv = [story_abspath, "--outdir", studio_dir]
        if args.voices:
            audio_argv += ["--voices", args.voices]
        if args.only:
            audio_argv += ["--only", args.only]
        if args.force_audio:
            audio_argv += ["--force"]
        if args.dry_run_audio:
            audio_argv += ["--dry-run"]

        mode = "dry-run (no network, no writes)" if args.dry_run_audio else "generate"
        print("      Running audio stage (%s) into %s/audio/ ..."
              % (mode, os.path.abspath(studio_dir)))
        try:
            rc = generate_audio.main(audio_argv)
            if rc == 0:
                audio_result = {"ran": True, "ok": True, "dry_run": args.dry_run_audio, "rc": rc}
                print("      Audio stage completed successfully.")
            else:
                # generate_audio returns non-zero when some beats failed, but
                # prior successes and canonical/script/HTML artifacts are intact.
                audio_result = {"ran": True, "ok": False, "dry_run": args.dry_run_audio, "rc": rc}
                sys.stderr.write(
                    "      NOTE: some beats failed to synthesize (exit %d). "
                    "Canonical data, script, and HTML are fine.\n" % rc)
        except Exception as exc:  # noqa: BLE001 - never let audio crash the whole build
            audio_result = {"ran": True, "ok": False, "dry_run": args.dry_run_audio,
                            "rc": None, "error": str(exc)}
            sys.stderr.write("      NOTE: audio stage raised an error: %s\n" % exc)
            sys.stderr.write("            Canonical data, script, and HTML are still valid.\n")
    else:
        audio_result = {"ran": False}
        print("      Skipped (no --with-audio).")
        print("      REMINDER: audio in %s/audio/ may be STALE relative to the current"
              % studio_dir)
        print("                story.json. Run with --with-audio to (re)generate it.")
    print("")

    # ---------------------------------------------------------------
    # Stage e: Final summary.
    # ---------------------------------------------------------------
    meta_path = os.path.join(studio_dir, "audio", "metadata.json")
    print("=" * 60)
    print("Build summary")
    print("=" * 60)
    print("  Validated : %s" % ("yes" if validated else "no"))
    if exported:
        print("  Exported  : %s" % exported[0])
        print("              %s" % exported[1])
    if copied_to:
        print("  HTML sync : %s" % os.path.abspath(copied_to))

    partial = False
    if audio_result and audio_result.get("ran"):
        if audio_result.get("dry_run"):
            print("  Audio     : dry-run only (no files written)")
        elif audio_result.get("ok"):
            print("  Audio     : generated/refreshed into %s/audio/" % studio_dir)
        else:
            partial = True
            print("  Audio     : PARTIAL — some beats failed.")
            print("              See %s for per-beat 'failed' entries." % meta_path)
    else:
        print("  Audio     : skipped (stale; run with --with-audio)")

    print("")
    print("Next: python3 %s --root %s"
          % (os.path.join(args.studio_dir, "serve.py"), args.studio_dir))
    print("      then open the printed URL to view the Story Studio.")

    # Overall exit: success even on partial audio (canonical/script/HTML are OK).
    if partial:
        print("")
        print("Result: SUCCESS (partial audio) — core artifacts are valid.")
    else:
        print("")
        print("Result: SUCCESS.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
