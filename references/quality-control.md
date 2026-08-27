# Quality Control

Quality is enforced at two levels: **per-phase checklists** during production, and a **final Quality Audit** before delivery.

## Per-phase validation checklists

### Phase 1 — Story Engine
- [ ] Full skeleton filled (premise → moral).
- [ ] Causal chain holds — every scene creates or answers a problem.
- [ ] Opening is specific and compelling (no generic "एक गाँव में...").
- [ ] 12–18 meaningful scenes; each has a function.
- [ ] Story DNA strands present and organic.

### Phase 2 — Canonical Story Data (`story.json`)
- [ ] Valid JSON; matches the schema.
- [ ] Stable scene/beat IDs (`s01`, `s01_b01`).
- [ ] Every beat has a `type`, `speaker`, and `text`.
- [ ] Every `character_id` referenced by a beat exists in `characters[]`.
- [ ] Sequencing is correct and gap-free.

### Phase 3 — Script Export
- [ ] `script.txt` / `script.md` generated **from** `story.json` only.
- [ ] No independently edited script copies.

### Phase 4 — HTML Studio
- [ ] Studio renders scenes and beats from `story.json`.
- [ ] Each line is individually addressable for highlighting.

### Phase 5 — Gemini TTS
- [ ] `GEMINI_API_KEY` read from environment (never hardcoded).
- [ ] One audio unit per beat; unchanged beats reuse existing audio.

### Phase 6 — Audio + HTML Integration
- [ ] Audio synced to the correct highlighted line.
- [ ] Playback order matches beat sequence.

### Phase 7 — Edit / Regenerate
- [ ] Edits made in `story.json`; downstream regenerated.
- [ ] Only changed beats re-synthesized.

## Final Quality Audit

Run all seven audit categories before declaring the story done:

- **STORY** — skeleton complete, causal chain intact, satisfying reveal and earned moral, correct pacing and length (~2,800–3,300 words).
- **CHARACTERS** — correct cast size, ≥1 important female character, distinct voices, earned arcs, no filler.
- **DIALOGUE** — every spoken line has a bold speaker; narration tagged `**कथावाचक:**`; attribution validated.
- **PRODUCTION DATA** — `story.json` valid, stable IDs, sequencing correct, all `character_id` references resolve.
- **TTS** — audio exists for every beat that needs it, generated via Gemini with the env-var key, unchanged audio reused.
- **HTML** — Studio renders from `story.json`, highlights sync to audio.
- **EDITING** — `story.json` remains the single source of truth; no drift between artifacts.

## The "No fake capabilities" rule

**Never claim something happened unless it was actually verified.** Specifically, do not claim:

- Audio was generated (unless the files exist and were produced by a real TTS call).
- Gemini is connected (unless a real request succeeded).
- The server / Studio is running (unless it was actually started and reachable).
- Tests passed (unless they were actually run and passed).

If a step could not be completed or verified, say so plainly and report what remains.
