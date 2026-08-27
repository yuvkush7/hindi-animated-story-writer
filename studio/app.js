/* Story Studio — vanilla JS, no frameworks/CDNs, CSP-safe (no eval).
 *
 * Data flow:
 *   story.json          -> canonical story (single source of truth)
 *   audio/metadata.json -> optional manifest: [{ beat_id, path, status, ... }]
 *
 * Sync is ALWAYS by stable beat id (never text matching or position guessing).
 */

"use strict";

/* ---------- App state ---------- */
const state = {
  story: null,          // parsed story.json -> .story
  beats: [],            // ordered flat array of beat objects (+ scene context)
  elByBeatId: new Map(),// beatId -> transcript DOM element
  ordinalByBeatId: new Map(), // beatId -> 0-based ordinal
  audioByBeatId: new Map(),   // beatId -> { path, status }
  currentIndex: 0,
  audio: new Audio(),   // single HTML5 Audio element for playback
};

/* ---------- DOM refs ---------- */
const els = {
  title: document.getElementById("story-title"),
  overview: document.getElementById("story-overview"),
  moral: document.getElementById("story-moral"),
  progress: document.getElementById("progress-indicator"),
  audioState: document.getElementById("audio-state"),
  currentContext: document.getElementById("current-context"),
  errorBanner: document.getElementById("error-banner"),
  sceneList: document.getElementById("scene-list"),
  characterList: document.getElementById("character-list"),
  transcript: document.getElementById("transcript"),
  btnPrev: document.getElementById("btn-prev"),
  btnNext: document.getElementById("btn-next"),
  btnPlay: document.getElementById("btn-play"),
  btnPause: document.getElementById("btn-pause"),
  btnResume: document.getElementById("btn-resume"),
};

/* ---------- Utilities ---------- */

// Show a visible error message and log it.
function showError(message) {
  els.errorBanner.hidden = false;
  els.errorBanner.textContent = message;
  console.error(message);
}

// Set the audio-state indicator (idle / playing / paused / missing-audio).
function setAudioState(stateName, beatId) {
  const labels = {
    idle: "स्थिति: निष्क्रिय (idle)",
    playing: "स्थिति: चल रहा है (playing) — " + (beatId || ""),
    paused: "स्थिति: रुका हुआ (paused)",
    "missing-audio": "स्थिति: ऑडियो अनुपलब्ध (missing-audio)",
  };
  els.audioState.dataset.state = stateName;
  els.audioState.textContent = labels[stateName] || labels.idle;
}

/* ---------- Data loading ---------- */

// Fetch JSON with graceful failure. Returns null if not available.
async function fetchJson(url, { required }) {
  try {
    const res = await fetch(url, { cache: "no-store" });
    if (!res.ok) throw new Error(res.status + " " + res.statusText);
    return await res.json();
  } catch (err) {
    if (required) {
      showError("story.json लोड नहीं हो सका (" + url + "): " + err.message);
    } else {
      // Optional resource missing is fine (e.g. no audio yet).
      console.info("Optional resource not loaded: " + url + " (" + err.message + ")");
    }
    return null;
  }
}

// Flatten scenes -> beats in (scene order, then ascending sequence).
function flattenBeats(story) {
  const beats = [];
  (story.scenes || []).forEach((scene, sceneIndex) => {
    const ordered = (scene.beats || [])
      .slice()
      .sort((a, b) => (a.sequence || 0) - (b.sequence || 0));
    ordered.forEach((beat) => {
      beats.push({
        ...beat,
        _scene: scene,
        _sceneIndex: sceneIndex,
      });
    });
  });
  return beats;
}

// Build beatId -> { path, status } map from an audio manifest (if any).
function indexAudio(manifest) {
  const map = new Map();
  if (!manifest) return map;
  // Accept either a bare array or { entries: [...] }.
  const entries = Array.isArray(manifest) ? manifest : (manifest.entries || []);
  entries.forEach((entry) => {
    if (entry && entry.beat_id) {
      map.set(entry.beat_id, {
        path: entry.path || entry.audio_path || null,
        status: entry.status || "ok",
      });
    }
  });
  return map;
}

// Is audio available and usable for a given beat id?
function hasUsableAudio(beatId) {
  const a = state.audioByBeatId.get(beatId);
  return !!(a && a.path && a.status === "ok");
}

/* ---------- Rendering ---------- */

function renderHeader(story) {
  els.title.textContent = story.title || "(शीर्षक नहीं)";
  els.overview.textContent = story.overview || "";
  els.moral.textContent = story.moral || "";
}

function renderScenes(story) {
  els.sceneList.innerHTML = "";
  (story.scenes || []).forEach((scene) => {
    const li = document.createElement("li");
    li.className = "scene-item";
    li.dataset.sceneId = scene.id;

    const id = document.createElement("div");
    id.className = "scene-id";
    id.textContent = scene.id;

    const title = document.createElement("div");
    title.className = "scene-title";
    title.textContent = scene.title || "";

    const meta = document.createElement("div");
    meta.className = "scene-meta";
    meta.textContent = [scene.location, scene.time].filter(Boolean).join(" · ");

    li.append(id, title, meta);

    // Clicking a scene jumps to its first beat (by ordinal, id-based).
    li.addEventListener("click", () => {
      const first = state.beats.find((b) => b._scene.id === scene.id);
      if (first) goTo(state.ordinalByBeatId.get(first.id));
    });

    els.sceneList.appendChild(li);
  });
}

function renderCharacters(story) {
  els.characterList.innerHTML = "";
  const genderLabel = { female: "स्त्री", male: "पुरुष", other: "अन्य" };
  (story.characters || []).forEach((c) => {
    const li = document.createElement("li");
    li.className = "character-item";

    const name = document.createElement("span");
    name.className = "char-name";
    name.textContent = c.name || c.id;

    const meta = document.createElement("div");
    meta.className = "char-meta";
    // नाम — उम्र — लिंग — भूमिका
    const parts = [];
    if (c.age != null) parts.push(c.age + " वर्ष");
    if (c.gender) parts.push(genderLabel[c.gender] || c.gender);
    if (c.role) parts.push(c.role);
    meta.textContent = parts.join(" — ");

    li.append(name, meta);
    els.characterList.appendChild(li);
  });
}

// Render the full transcript, grouped by scene headings.
function renderTranscript() {
  els.transcript.innerHTML = "";
  state.elByBeatId.clear();

  let lastSceneId = null;
  state.beats.forEach((beat, ordinal) => {
    // Scene heading whenever the scene changes.
    if (beat._scene.id !== lastSceneId) {
      lastSceneId = beat._scene.id;
      const h = document.createElement("h3");
      h.className = "scene-heading";
      h.textContent = (beat._scene.title || beat._scene.id) + " ";
      const meta = document.createElement("span");
      meta.className = "scene-heading-meta";
      meta.textContent =
        "(" + [beat._scene.location, beat._scene.time].filter(Boolean).join(" · ") + ")";
      h.appendChild(meta);
      els.transcript.appendChild(h);
    }

    const div = document.createElement("div");
    div.className = "beat " + (beat.type === "narration" ? "narration" : "dialogue");
    div.dataset.beatId = beat.id; // stable id anchor for sync

    const ord = document.createElement("span");
    ord.className = "beat-ordinal";
    ord.textContent = "#" + (ordinal + 1);

    const speaker = document.createElement("span");
    speaker.className = "speaker";
    speaker.textContent = beat.speaker || "";

    const text = document.createElement("span");
    text.className = "beat-text";
    text.textContent = beat.text || "";

    div.append(ord, speaker, text);

    // Clicking a beat selects it.
    div.addEventListener("click", () => goTo(ordinal));

    els.transcript.appendChild(div);
    state.elByBeatId.set(beat.id, div);
  });
}

/* ---------- Navigation / highlight ---------- */

function currentBeat() {
  return state.beats[state.currentIndex] || null;
}

// Update highlight, scroll, progress, and context displays.
function refreshCurrent() {
  const beat = currentBeat();
  if (!beat) return;

  // Move .current highlight.
  state.elByBeatId.forEach((el) => el.classList.remove("current"));
  const el = state.elByBeatId.get(beat.id);
  if (el) {
    el.classList.add("current");
    el.scrollIntoView({ block: "center", behavior: "smooth" });
  }

  // Active scene in sidebar.
  els.sceneList.querySelectorAll(".scene-item").forEach((item) => {
    item.classList.toggle("active-scene", item.dataset.sceneId === beat._scene.id);
  });

  // Header progress + context.
  els.progress.textContent = "बीट " + (state.currentIndex + 1) + " / " + state.beats.length;
  els.currentContext.textContent =
    "वक्ता: " + (beat.speaker || "—") + " · दृश्य: " + (beat._scene.title || beat._scene.id);
}

function goTo(index) {
  if (index == null || index < 0 || index >= state.beats.length) return;
  state.currentIndex = index;
  refreshCurrent();
}

function next() { goTo(state.currentIndex + 1); }
function prev() { goTo(state.currentIndex - 1); }

/* ---------- Playback (single Audio element) ---------- */

// Load and play the current beat's audio if usable; else show missing-audio.
function play() {
  const beat = currentBeat();
  if (!beat) return;

  if (!hasUsableAudio(beat.id)) {
    // No audio: still keep highlight/selection; allow skip via Next.
    setAudioState("missing-audio", beat.id);
    return;
  }

  const info = state.audioByBeatId.get(beat.id);
  // Only reset src when switching to a different file.
  if (state.audio.getAttribute("data-beat-id") !== beat.id) {
    state.audio.src = info.path;
    state.audio.setAttribute("data-beat-id", beat.id);
  }
  state.audio.play().then(
    () => setAudioState("playing", beat.id),
    (err) => showError("ऑडियो नहीं चला: " + err.message)
  );
}

function pause() {
  if (!state.audio.paused) {
    state.audio.pause();
    setAudioState("paused");
  }
}

function resume() {
  // If nothing is loaded yet, resume behaves like play.
  if (!state.audio.src) { play(); return; }
  state.audio.play().then(
    () => setAudioState("playing", currentBeat() && currentBeat().id),
    (err) => showError("ऑडियो resume नहीं हुआ: " + err.message)
  );
}

// On end, advance to the NEXT beat that has usable audio and play it.
function onAudioEnded() {
  for (let i = state.currentIndex + 1; i < state.beats.length; i++) {
    if (hasUsableAudio(state.beats[i].id)) {
      goTo(i);
      play();
      return;
    }
  }
  // No further playable audio.
  setAudioState("idle");
}

/* ---------- Wiring ---------- */

function wireControls() {
  els.btnPrev.addEventListener("click", prev);
  els.btnNext.addEventListener("click", next);
  els.btnPlay.addEventListener("click", play);
  els.btnPause.addEventListener("click", pause);
  els.btnResume.addEventListener("click", resume);
  state.audio.addEventListener("ended", onAudioEnded);

  // Keyboard convenience: ← / → to navigate.
  document.addEventListener("keydown", (e) => {
    if (e.key === "ArrowRight") next();
    else if (e.key === "ArrowLeft") prev();
  });
}

/* ---------- Init ---------- */

async function init() {
  wireControls();

  const storyDoc = await fetchJson("story.json", { required: true });
  if (!storyDoc || !storyDoc.story) {
    showError("story.json में मान्य 'story' ऑब्जेक्ट नहीं मिला।");
    return;
  }
  state.story = storyDoc.story;

  // Optional audio manifest (Phase 5). Absence is not an error.
  const manifest = await fetchJson("audio/metadata.json", { required: false });
  state.audioByBeatId = indexAudio(manifest);

  // Build ordered beats + indexes (id-based).
  state.beats = flattenBeats(state.story);
  state.ordinalByBeatId.clear();
  state.beats.forEach((b, i) => state.ordinalByBeatId.set(b.id, i));

  // Render everything from the data.
  renderHeader(state.story);
  renderScenes(state.story);
  renderCharacters(state.story);
  renderTranscript();

  if (state.beats.length === 0) {
    showError("कहानी में कोई बीट नहीं मिली।");
    return;
  }

  setAudioState("idle");
  goTo(0);
}

// Kick off once the DOM is ready.
document.addEventListener("DOMContentLoaded", init);
