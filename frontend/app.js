// ---------- pixel art ('#' = pixel on) ----------
const S = {
  egg: [
    "...####...",
    "..#....#..",
    ".#.##...#.",
    ".#......#.",
    "#.....##.#",
    "#.##.....#",
    "#........#",
    "#...##...#",
    ".#......#.",
    "..######..",
  ],
  baby: [
    "..######..",
    ".########.",
    "##########",
    "##.####.##",
    "##########",
    "###.##.###",
    "####..####",
    ".########.",
    "..#....#..",
  ],
  child: [
    ".#........#.",
    ".##########.",
    "############",
    "##..####..##",
    "############",
    "####.##.####",
    "#####..#####",
    ".##########.",
    ".##########.",
    "..###..###..",
    "..##....##..",
  ],
  adult: [
    ".##........##.",
    ".###......###.",
    ".############.",
    "##############",
    "###..####..###",
    "###..####..###",
    "##############",
    "#####.##.#####",
    "######..######",
    ".############.",
    ".############.",
    "..##########..",
    "..###....###..",
    "..##......##..",
  ],
  ghost: [
    "...####...",
    "..######..",
    ".##.##.##.",
    ".########.",
    ".########.",
    ".##....##.",
    ".########.",
    ".########.",
    ".#.##.##.#",
    ".#..#..#..",
  ],
  food: [
    "...#...",
    "..###..",
    ".#####.",
    "##...##",
    "#.....#",
    "#######",
    "#######",
  ],
  poop: [
    "...#..",
    "..##..",
    ".####.",
    "##.###",
    "######",
  ],
  heart: [
    ".#.#.",
    "#####",
    ".###.",
    "..#..",
  ],
  z: ["###", ".#.", "###"],
  skull: [".###.", "#.#.#", "#####", ".#.#."],
  thought: ["#......", ".......", ".#.....", "...###.", "..#####", "...###."], // dots + rice ball
  stink: ["#.", ".#", "#."],
  question: [".##.", "#..#", "..#.", ".#..", "....", ".#.."],
};

// Per-stage tweaks (row index -> replacement row): closed eyes for sleeping, alternate feet for
// walking, and a face for each mood.
const VARIANTS = {
  baby: {
    sleep: { 3: "#..####..#" },
    step: { 8: ".#......#." },
    happy: { 2: "##.####.##", 3: "#.#.##.#.#", 5: "##.####.##", 6: "###....###" },
    sad: { 5: "####..####", 6: "###.##.###" },
    hungry: { 5: "####..####", 6: "####..####" },
    tired: { 3: "#..####..#", 6: "####..####" },
    sick: { 2: "#.#.##.#.#", 3: "##.####.##", 4: "#.#.##.#.#", 5: "##########", 6: "##.#..#.##" },
    thinking: { 2: "##.####.##", 3: "##########", 5: "##########", 6: "###....###" },
    curious: { 2: "##.#######", 3: "#######.##", 5: "####..####", 6: "##########" },
  },
  child: {
    sleep: { 3: "#...####...#" },
    step: { 10: ".##......##." },
    happy: { 2: "##..####..##", 3: "#.##.##.##.#", 5: "###.####.###", 6: "####....####" },
    sad: { 5: "#####..#####", 6: "####.##.####" },
    hungry: { 5: "#####..#####", 6: "#####..#####" },
    tired: { 3: "#...####...#" },
    sick: { 2: "#.#.####.#.#", 3: "##.######.##", 4: "#.#.####.#.#", 5: "############", 6: "###.#..#.###" },
    thinking: { 2: "##..####..##", 3: "############", 5: "############", 6: "####....####" },
    curious: { 2: "##..########", 3: "########..##", 5: "#####..#####", 6: "############" },
  },
  adult: {
    sleep: { 4: "##############", 5: "##...####...##" },
    step: { 13: ".##........##." },
    happy: { 5: "##.##.##.##.##", 7: "####.####.####", 8: "#####....#####" },
    sad: { 7: "######..######", 8: "#####.##.#####" },
    hungry: { 7: "#####....#####", 8: "#####....#####" },
    tired: { 4: "##############", 5: "##...####...##", 7: "##############" },
    sick: { 3: "##.#.####.#.##", 4: "###.######.###", 5: "##.#.####.#.##", 7: "##############", 8: "####.#..#.####" },
    thinking: { 3: "###..####..###", 4: "###..####..###", 5: "##############", 7: "##############", 8: "#####....#####" },
    curious: { 3: "###..#########", 4: "###..####..###", 5: "#########..###", 7: "######..######", 8: "##############" },
  },
};

// Where the left eye sits in each stage's sprite (for the tear).
const EYE = { baby: { x: 2, y: 3 }, child: { x: 2, y: 3 }, adult: { x: 3, y: 5 } };

// How each mood moves: ms between steps, chance to step, bounce/shake.
const MOOD_STYLE = {
  happy: { every: 500, move: 0.85, bounce: true },
  ok: { every: 900, move: 0.75 },
  hungry: { every: 900, move: 0.6 },
  tired: { every: 1800, move: 0.3 },
  sad: { every: 2000, move: 0.25 },
  sick: { every: 1500, move: 0.2, shake: true },
  thinking: { every: 1600, move: 0.2 },
  curious: { every: 700, move: 0.6 },
};

// What the pet says on the LCD when its mood changes.
const MOOD_TEXT = {
  happy: "YAY!",
  hungry: "HUNGRY!",
  tired: "SO SLEEPY",
  sad: "PLAY W/ ME",
  sick: "I FEEL SICK",
  thinking: "HMM...",
  curious: "OOH?",
};

const ICON_ART = {
  feed: ["...##...", "..####..", ".######.", "##....##", "#......#", "########", "########", ".######."],
  light: ["..####..", ".#....#.", "#......#", "#......#", ".#....#.", "..####..", "..####..", "...##..."],
  play: ["..####..", ".#.##.#.", "#..##..#", "########", "########", "#..##..#", ".#.##.#.", "..####.."],
  clean: ["..##....", ".###....", "####....", "..#....#", ".#######", "########", ".######.", "..####.."],
  stats: ["........", "......#.", "......#.", "....#.#.", "....#.#.", "..#.#.#.", "..#.#.#.", "########"],
  chat: [".######.", "#......#", "#.#.#..#", "#......#", ".######.", "..#.....", ".#......", "........"],
  outfit: ["...##...", "..#..#..", ".....#..", "....#...", "...##...", ".##..##.", "#......#", "########"],
  mirror: ["..####..", ".#....#.", ".#.#..#.", ".#....#.", "..####..", "...##...", "...##...", "...##..."],
  calendar: [".#....#.", "########", "########", "#......#", "#.##.#.#", "#......#", "#.#.##.#", "########"],
  attention: ["...##...", "..####..", "..####..", "..####..", "...##...", "........", "...##...", "...##..."],
};

const ICONS = [
  { id: "feed", row: "top" },
  { id: "light", row: "top" },
  { id: "play", row: "top" },
  { id: "clean", row: "top" },
  { id: "stats", row: "bottom" },
  { id: "chat", row: "bottom" },
  { id: "outfit", row: "bottom" },
  { id: "mirror", row: "bottom" },
  { id: "calendar", row: "bottom", soon: true },
  { id: "attention", row: "bottom", passive: true },
];
const SELECTABLE = ICONS.filter((i) => !i.passive);

// ---------- canvas helpers ----------
const W = 48, H = 32, GROUND = 30;
const canvas = document.getElementById("screen");
const ctx = canvas.getContext("2d");
const lcd = document.getElementById("lcd");
const overlay = document.getElementById("overlay");
const bubble = document.getElementById("bubble");

function cssVar(name) {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

function drawSprite(target, rows, x, y, { flip = false, maxCols = Infinity } = {}) {
  rows.forEach((row, j) => {
    const cells = flip ? [...row].reverse() : [...row];
    cells.forEach((c, i) => {
      if (c === "#" && i < maxCols) target.fillRect(Math.round(x + i), Math.round(y + j), 1, 1);
    });
  });
}

function variant(stage, ...kinds) {
  const changes = Object.assign({}, ...kinds.map((k) => VARIANTS[stage]?.[k] || {}));
  return S[stage].map((row, i) => changes[i] ?? row);
}

// ---------- icons ----------
function buildIcons() {
  ICONS.forEach((icon) => {
    const c = document.createElement("canvas");
    c.width = c.height = 8;
    c.className = "icon" + (icon.soon ? " soon" : "");
    c.title = icon.soon ? `${icon.id} (coming soon)` : icon.id;
    const g = c.getContext("2d");
    g.fillStyle = cssVar("--lcd-px");
    drawSprite(g, ICON_ART[icon.id], 0, 0);
    if (!icon.passive) {
      c.addEventListener("click", () => {
        state.selected = SELECTABLE.indexOf(icon);
        press("B");
      });
    }
    icon.el = c;
    document.getElementById(`icons-${icon.row}`).appendChild(c);
  });
}

function updateIcons() {
  ICONS.forEach((icon) => {
    icon.el.classList.toggle("selected", SELECTABLE[state.selected] === icon);
    if (icon.passive) icon.el.classList.toggle("lit", !!state.pet?.needs_attention);
  });
}

// ---------- state ----------
const state = {
  pet: null,
  selected: -1,
  view: "main", // main | stats
  anim: null, // { type, start, duration }
  x: 20,
  dir: 1,
  mood: null, // last mood we reacted to
  transform: null, // { start } while a new look is being applied
};

async function api(path, options = {}) {
  const res = await fetch("/api" + path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || "ERROR");
  return data;
}

async function refresh() {
  try {
    setPet(await api("/pet"));
  } catch {
    say("NO SIGNAL");
  }
  updateIcons();
  if (state.view === "stats") showStats();
}

let bubbleTimer;
function say(text, ms = 1800) {
  bubble.textContent = text;
  bubble.hidden = false;
  clearTimeout(bubbleTimer);
  bubbleTimer = setTimeout(() => (bubble.hidden = true), ms);
}

// ---------- sound: 90s piezo buzzer ----------
// Old virtual pets had a tiny piezo speaker: one square-wave tone at a time, high pitched,
// switching hard on/off with no fade. Each sound is a list of [frequency Hz, ms] notes;
// frequency 0 is a rest.
let audio;
const SOUNDS = {
  click: [[4000, 30]],
  confirm: [[3136, 50], [0, 30], [4186, 70]],
  error: [[880, 90], [0, 50], [880, 140]],
  happy: [[2093, 70], [2637, 70], [3136, 70], [4186, 160]],
  hungry: [[3136, 80], [0, 60], [3136, 80], [0, 60], [3136, 80]],
  sad: [[2637, 150], [2349, 150], [2093, 150], [1760, 320]],
  tired: [[1568, 220], [0, 80], [1397, 380]],
  sick: [[2093, 60], [1976, 60], [2093, 60], [1976, 60], [2093, 60], [1976, 160]],
  thinking: [[1760, 120], [0, 60], [1976, 120], [0, 60], [2093, 220]],
  curious: [[2093, 70], [0, 30], [3136, 160]],
  sleeping: [[2637, 260], [2093, 260], [1568, 420]],
  transform: [[1568, 40], [2093, 40], [2637, 40], [3136, 40], [4186, 40], [0, 40], [1568, 40], [2093, 40], [2637, 40], [3136, 40], [4186, 40], [5274, 160]],
  hatch: [[2093, 80], [2637, 80], [3136, 80], [2637, 80], [3136, 80], [4186, 240]],
};

function play(name) {
  try {
    audio ||= new AudioContext();
    if (audio.state === "suspended") audio.resume();
    const osc = audio.createOscillator();
    const gain = audio.createGain();
    osc.type = "square";
    gain.gain.value = 0;
    osc.connect(gain).connect(audio.destination);
    let t = audio.currentTime + 0.01;
    for (const [freq, ms] of SOUNDS[name]) {
      // setValueAtTime = instant switch, which gives the hard "buzzer" edge
      gain.gain.setValueAtTime(freq ? 0.035 : 0, t);
      if (freq) osc.frequency.setValueAtTime(freq, t);
      t += ms / 1000;
    }
    gain.gain.setValueAtTime(0, t);
    osc.start();
    osc.stop(t + 0.02);
  } catch {
    /* audio is optional */
  }
}

// ---------- mood ----------
// Called whenever fresh pet data arrives; reacts once per mood change (not on page load).
function setPet(pet) {
  const before = state.mood;
  state.pet = pet;
  state.mood = pet.mood;
  if (!before || before === pet.mood) return;
  if (before === "egg") return play("hatch"), say("HELLO!");
  if (SOUNDS[pet.mood]) play(pet.mood);
  if (MOOD_TEXT[pet.mood]) say(MOOD_TEXT[pet.mood], 2500);
}

// ---------- actions ----------
const ACTION_FOR = { feed: "feed", light: "sleep", play: "play", clean: "clean" };
const ANIM_FOR = { feed: "eat", play: "play", clean: "clean" };

async function runIcon(icon) {
  if (icon.soon) return say("SOON!");
  if (icon.id === "stats") return showStats();
  if (icon.id === "chat") return openChat();
  if (icon.id === "outfit") return openOutfits();
  if (icon.id === "mirror") return openMirror();

  try {
    const { pet, message } = await api(`/pet/${ACTION_FOR[icon.id]}`, { method: "POST" });
    const moodBefore = state.mood;
    setPet(pet);
    if (ANIM_FOR[icon.id]) state.anim = { type: ANIM_FOR[icon.id], start: performance.now(), duration: 2000 };
    say(message);
    if (moodBefore === pet.mood) play("confirm"); // a mood change already played its own tune
  } catch (e) {
    say(e.message);
    play("error");
  }
  updateIcons();
}

function meter(value) {
  const on = Math.round(value / 25);
  return `<span class="meter">${[0, 1, 2, 3].map((i) => `<i class="${i < on ? "on" : ""}"></i>`).join("")}</span>`;
}

function formatAge(min) {
  if (min < 60) return `${min}m`;
  if (min < 1440) return `${Math.floor(min / 60)}h`;
  return `${Math.floor(min / 1440)}d`;
}

function showStats() {
  const p = state.pet;
  if (!p) return;
  state.view = "stats";
  bubble.hidden = true;
  overlay.className = "overlay";
  overlay.innerHTML = `
    <h2><span>${p.name.toUpperCase()}</span><span>${formatAge(p.age_minutes)}</span></h2>
    <div class="stat">FOOD ${meter(p.hunger)}</div>
    <div class="stat">HAPPY ${meter(p.happiness)}</div>
    <div class="stat">ENERGY ${meter(p.energy)}</div>
    <div class="stat">HEALTH ${meter(p.health)}</div>
    <div class="stat">MOOD <span>${p.mood.toUpperCase()}</span></div>`;
  overlay.hidden = false;
}

function closeOverlay() {
  state.view = "main";
  overlay.hidden = true;
}

async function press(btn) {
  const el = document.querySelector(`[data-btn="${btn}"]`);
  el.classList.add("pressed");
  setTimeout(() => el.classList.remove("pressed"), 120);
  play("click");

  if (state.pet && !state.pet.alive) {
    if (btn === "B") {
      setPet(await api("/reset", { method: "POST", body: JSON.stringify({ name: state.pet.name }) }));
      say("NEW EGG!");
    }
    return updateIcons();
  }

  if (btn === "A") {
    if (state.view !== "main") closeOverlay();
    state.selected = (state.selected + 1) % SELECTABLE.length;
  } else if (btn === "B") {
    if (state.selected >= 0) await runIcon(SELECTABLE[state.selected]);
  } else if (btn === "C") {
    if (state.view !== "main") closeOverlay();
    else state.selected = -1;
  }
  updateIcons();
}

document.querySelectorAll("[data-btn]").forEach((el) => el.addEventListener("click", () => press(el.dataset.btn)));
document.addEventListener("keydown", (e) => {
  // While typing in the chat, keys belong to the input (Esc still closes the chat).
  if (e.target.closest?.(".chat, .window")) {
    if (e.key === "Escape") {
      closeChat();
      closeOutfits();
      closeMirror();
    }
    return;
  }
  const map = { ArrowLeft: "A", ArrowRight: "A", a: "A", Enter: "B", " ": "B", b: "B", Escape: "C", c: "C" };
  if (map[e.key]) {
    e.preventDefault();
    press(map[e.key]);
  }
});

// ---------- chat ----------
const chatEl = document.getElementById("chat");
const chatLog = document.getElementById("chat-log");
const chatForm = document.getElementById("chat-form");
const chatInput = document.getElementById("chat-input");
const sendBtn = chatForm.querySelector(".chat-send");
const micBtn = document.getElementById("chat-mic");
const voiceBtn = document.getElementById("chat-voice");
const chatHistory = []; // { role: "user" | "assistant", content }

function addMessage(kind, text) {
  const el = document.createElement("div");
  el.className = `msg ${kind}`;
  el.textContent = text;
  chatLog.appendChild(el);
  chatLog.scrollTop = chatLog.scrollHeight;
  return el;
}

async function openChat() {
  unlockSpeech();
  closeOutfits();
  closeMirror();
  chatEl.hidden = false;
  chatInput.focus();
  if (chatHistory.length) return;
  try {
    const { message } = await api("/chat/greeting");
    chatHistory.push({ role: "assistant", content: message });
    addMessage("pet", message);
    speak(message);
    say("HI GIRL!");
  } catch (e) {
    addMessage("error", e.message);
  }
}

function closeChat() {
  chatEl.hidden = true;
  stopListening();
  window.speechSynthesis?.cancel();
}

async function sendMessage(text) {
  chatHistory.push({ role: "user", content: text });
  addMessage("user", text);

  const typing = addMessage("pet typing", "...");
  sendBtn.disabled = true;
  try {
    const { message, changes, theme } = await api("/chat", { method: "POST", body: JSON.stringify({ messages: chatHistory }) });
    if (theme) {
      // The backend recognized a theme request: play the transformation, then show the reply.
      typing.textContent = "✨ ...";
      await transformTo(Promise.resolve(theme));
    }
    chatHistory.push({ role: "assistant", content: message });
    typing.remove();
    addMessage("pet", message);
    changes.forEach((change) => addMessage("note", `✓ ${change}`));
    speak(message);
    state.anim = { type: "play", start: performance.now(), duration: 1500 };
  } catch (err) {
    chatHistory.pop(); // drop the unanswered message so the history stays user/assistant
    typing.remove();
    addMessage("error", err.message);
  } finally {
    sendBtn.disabled = false;
  }
}

chatForm.addEventListener("submit", (e) => {
  e.preventDefault();
  unlockSpeech();
  const text = chatInput.value.trim();
  if (!text || sendBtn.disabled) return;
  chatInput.value = "";
  sendMessage(text);
  chatInput.focus();
});

document.getElementById("chat-close").addEventListener("click", closeChat);

// ---------- new look: outfit picker + "transformation" effect ----------
const TRANSFORM_MS = 1300;
const outfitsEl = document.getElementById("outfits");
const outfitList = document.getElementById("outfit-list");
const deviceWrap = document.querySelector(".device-wrap");
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

// Pixel sparkles flying out of the device (pure CSS animation, removed afterwards).
function burstSparkles() {
  const burst = document.createElement("div");
  burst.className = "burst";
  for (let i = 0; i < 14; i++) {
    const s = document.createElement("i");
    s.className = "px sparkle";
    const angle = (i / 14) * Math.PI * 2;
    const dist = 140 + Math.random() * 80;
    s.style.left = "50%";
    s.style.top = "45%";
    s.style.setProperty("--dx", `${Math.cos(angle) * dist}px`);
    s.style.setProperty("--dy", `${Math.sin(angle) * dist}px`);
    burst.appendChild(s);
  }
  deviceWrap.appendChild(burst);
  setTimeout(() => burst.remove(), 1000);
}

// Plays the transformation (shake, shine, sparkles, LCD swirl, jingle) while `themePromise`
// resolves, then morphs the colors into the new theme. Starts instantly, so the user sees
// something happen from the moment they ask.
async function transformTo(themePromise) {
  if (state.transform) return;
  state.transform = { start: performance.now() };
  deviceWrap.classList.add("transforming");
  burstSparkles();
  play("transform");
  say("MAGIC...", TRANSFORM_MS);
  try {
    const [theme] = await Promise.all([themePromise, sleep(TRANSFORM_MS)]);
    Themes.apply(theme); // colors + wallpaper morph smoothly from here (CSS transitions)
    play("happy");
    say("NEW LOOK!");
  } catch (e) {
    play("error");
    say("OOPS");
  } finally {
    deviceWrap.classList.remove("transforming");
    state.transform = null;
  }
}

// Draws the LCD part of the transformation: a few inverse flashes, then sparkles spiralling
// in toward the pet.
function drawTransform(now, cx, cy) {
  const t = (now - state.transform.start) / TRANSFORM_MS;
  if (t < 0.3) {
    if (Math.floor(now / 90) % 2) ctx.fillRect(0, 0, W, H);
    return;
  }
  const radius = 3 + 16 * (1 - t);
  for (let i = 0; i < 8; i++) {
    const a = now / 110 + (i * Math.PI) / 4;
    const sx = Math.round(cx + Math.cos(a) * radius);
    const sy = Math.round(cy + Math.sin(a) * radius * 0.7);
    ctx.fillRect(sx, sy, 1, 1);
    if (i % 2) ctx.fillRect(sx - 1, sy, 3, 1); // every other sparkle is a little cross
    if (i % 2) ctx.fillRect(sx, sy - 1, 1, 3);
  }
}

async function openOutfits() {
  closeChat();
  closeMirror();
  outfitsEl.hidden = false;
  try {
    const [presets, current] = await Promise.all([api("/theme/presets"), api("/theme")]);
    outfitList.innerHTML = "";
    for (const preset of presets) {
      const btn = document.createElement("button");
      btn.className = "outfit" + (preset.motif === current.motif ? " active" : "");
      const swatches = document.createElement("span");
      swatches.className = "swatches";
      preset.colors.forEach((c) => {
        const sw = document.createElement("i");
        sw.style.background = c;
        swatches.appendChild(sw);
      });
      const label = document.createElement("span");
      label.textContent = preset.label;
      btn.append(swatches, label);
      btn.addEventListener("click", () => pickOutfit(preset, btn));
      outfitList.appendChild(btn);
    }
  } catch (e) {
    outfitList.textContent = e.message;
  }
}

function closeOutfits() {
  outfitsEl.hidden = true;
}

function pickOutfit(preset, btn) {
  if (state.transform) return;
  unlockSpeech();
  outfitList.querySelectorAll(".outfit").forEach((el) => el.classList.toggle("active", el === btn));
  // save and transform in parallel: the effect starts on the click, not after the request
  transformTo(api("/theme", { method: "PUT", body: JSON.stringify({ motif: preset.motif }) }));
}

document.getElementById("outfits-close").addEventListener("click", closeOutfits);

// ---------- Mirror mode: photo of today's outfit -> the pet compares it with its suggestion ----------
// Camera via getUserMedia (needs HTTPS or localhost; Tailscale serve provides HTTPS). If that's
// unavailable or denied, a file input opens the phone's camera or photo library instead.
// Photos stay in this page's memory only; the backend doesn't store them either.
const MIRROR_MAX_SIDE = 1024; // resize before upload (the backend resizes again, authoritatively)
const mirrorEl = document.getElementById("mirror");
const mirrorVideo = document.getElementById("mirror-video");
const mirrorStill = document.getElementById("mirror-still");
const mirrorNote = document.getElementById("mirror-note");
const mirrorBtns = {
  flip: document.getElementById("mirror-flip"),
  snap: document.getElementById("mirror-snap"),
  retake: document.getElementById("mirror-retake"),
  send: document.getElementById("mirror-send"),
  file: document.getElementById("mirror-file-label"),
};
const mirrorFile = document.getElementById("mirror-file");
const mirror = { stream: null, facing: "user", photo: null, photoUrl: null, useFile: false };

function showMirrorButtons(...names) {
  Object.entries(mirrorBtns).forEach(([name, el]) => (el.hidden = !names.includes(name)));
}

function mirrorSay(text) {
  mirrorNote.textContent = text;
  mirrorNote.hidden = !text;
}

function stopCamera() {
  mirror.stream?.getTracks().forEach((t) => t.stop());
  mirror.stream = null;
  mirrorVideo.srcObject = null;
}

// Fallback: let the phone open its own camera or the photo library.
function useFileInput(reason) {
  mirror.useFile = true;
  stopCamera();
  mirrorVideo.hidden = true;
  showMirrorButtons("file");
  // keep an earlier note (e.g. "no suggestion today") and add the reason after it
  if (reason) mirrorSay([mirrorNote.textContent, reason].filter(Boolean).join(" "));
}

async function startCamera() {
  if (!navigator.mediaDevices?.getUserMedia) {
    return useFileInput("Η live κάμερα δεν είναι διαθέσιμη εδώ, πάτα PICK PHOTO.");
  }
  try {
    mirror.stream = await navigator.mediaDevices.getUserMedia({
      video: { facingMode: mirror.facing, width: { ideal: 1280 }, height: { ideal: 1280 } },
      audio: false,
    });
  } catch (e) {
    const denied = e.name === "NotAllowedError";
    return useFileInput(denied ? "Δεν έδωσες άδεια για κάμερα, πάτα PICK PHOTO." : "Η κάμερα δεν άνοιξε, πάτα PICK PHOTO.");
  }
  mirrorVideo.srcObject = mirror.stream;
  mirrorVideo.classList.toggle("selfie", mirror.facing === "user");
  mirrorVideo.hidden = false;
  mirrorStill.hidden = true;
  // FLIP only makes sense with more than one camera (phones)
  const cams = (await navigator.mediaDevices.enumerateDevices()).filter((d) => d.kind === "videoinput");
  showMirrorButtons("snap", ...(cams.length > 1 ? ["flip"] : []));
}

// Draw an image source onto a canvas no bigger than MIRROR_MAX_SIDE and return a JPEG blob.
function toJpeg(source, width, height) {
  const scale = Math.min(1, MIRROR_MAX_SIDE / Math.max(width, height));
  const canvas = document.createElement("canvas");
  canvas.width = Math.round(width * scale);
  canvas.height = Math.round(height * scale);
  canvas.getContext("2d").drawImage(source, 0, 0, canvas.width, canvas.height);
  return new Promise((resolve) => canvas.toBlob(resolve, "image/jpeg", 0.85));
}

function showPhoto(blob) {
  mirror.photo = blob;
  if (mirror.photoUrl) URL.revokeObjectURL(mirror.photoUrl);
  mirror.photoUrl = URL.createObjectURL(blob);
  mirrorStill.src = mirror.photoUrl;
  mirrorStill.hidden = false;
  mirrorVideo.hidden = true;
  showMirrorButtons("retake", "send");
}

async function snap() {
  if (!mirror.stream || !mirrorVideo.videoWidth) return;
  play("click");
  showPhoto(await toJpeg(mirrorVideo, mirrorVideo.videoWidth, mirrorVideo.videoHeight));
  stopCamera(); // the preview is frozen on the photo; free the camera meanwhile
}

async function retake() {
  mirror.photo = null;
  mirrorStill.hidden = true;
  if (mirror.useFile) {
    showMirrorButtons("file");
    mirrorFile.click();
  } else {
    await startCamera();
  }
}

async function openMirror() {
  closeChat();
  closeOutfits();
  mirrorEl.hidden = false;
  mirror.useFile = false;
  mirror.photo = null;
  mirrorSay("");
  try {
    const { has_suggestion } = await api("/mirror/status");
    if (!has_suggestion) {
      mirrorSay("Δεν μου ζήτησες outfit σήμερα, bestie! Στείλε μου φωτό και θα σου πω ελεύθερα τη γνώμη μου.");
    }
  } catch {
    /* the note is optional */
  }
  await startCamera();
}

function closeMirror() {
  stopCamera();
  mirrorEl.hidden = true;
}

// Upload the photo; the pet answers in the chat and reacts through its mood.
async function sendPhoto() {
  if (!mirror.photo) return;
  unlockSpeech();
  const photo = mirror.photo;
  const thumbUrl = URL.createObjectURL(photo); // shown in the chat, in-memory only
  closeMirror();
  await openChat();

  const userMsg = addMessage("user", "Πώς σου φαίνεται το σημερινό μου outfit;");
  const thumb = document.createElement("img");
  thumb.className = "thumb";
  thumb.alt = "Outfit photo";
  thumb.src = thumbUrl;
  userMsg.prepend(thumb);
  const typing = addMessage("pet typing", "👀 ...");

  const form = new FormData();
  form.append("photo", photo, "outfit.jpg");
  try {
    const res = await fetch("/api/mirror", { method: "POST", body: form });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.detail || "Κάτι πήγε στραβά, ξαναδοκίμασε!");
    typing.remove();
    addMessage("pet", data.comment);
    if (data.match_level) addMessage("note", `match: ${data.match_level}`);
    speak(data.comment);
    setPet(data.pet); // the reaction shows up as a mood: face, sound, LCD bubble
    // keep the chat history coherent for follow-up questions
    chatHistory.push({ role: "user", content: "(I sent you a photo of my outfit today.)" });
    chatHistory.push({ role: "assistant", content: data.comment });
  } catch (e) {
    typing.remove();
    addMessage("error", e.message || "Κάτι πήγε στραβά, ξαναδοκίμασε!");
  }
}

mirrorBtns.snap.addEventListener("click", snap);
mirrorBtns.retake.addEventListener("click", retake);
mirrorBtns.send.addEventListener("click", sendPhoto);
mirrorBtns.flip.addEventListener("click", async () => {
  mirror.facing = mirror.facing === "user" ? "environment" : "user";
  stopCamera();
  await startCamera();
});
mirrorFile.addEventListener("change", async () => {
  const file = mirrorFile.files[0];
  mirrorFile.value = ""; // allow picking the same file again
  if (!file) return;
  try {
    const bitmap = await createImageBitmap(file);
    showPhoto(await toJpeg(bitmap, bitmap.width, bitmap.height));
    bitmap.close();
  } catch {
    mirrorSay("Δεν μπόρεσα να ανοίξω αυτή τη φωτογραφία, δοκίμασε άλλη.");
  }
});
document.getElementById("mirror-close").addEventListener("click", closeMirror);

// ---------- voice: speech-to-text in, text-to-speech out (all in the browser) ----------
const VOICE_LANG = "el-GR";
const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
let recognition = null;
let voiceOn = true;
try {
  voiceOn = localStorage.getItem("voiceOn") !== "false";
} catch {
  /* storage may be blocked; default to on */
}

function setVoice(on) {
  voiceOn = on;
  voiceBtn.textContent = on ? "♪ ON" : "♪ OFF";
  voiceBtn.setAttribute("aria-pressed", String(on));
  if (!on) window.speechSynthesis?.cancel();
  try {
    localStorage.setItem("voiceOn", String(on));
  } catch {
    /* ignore */
  }
}
setVoice(voiceOn);
voiceBtn.addEventListener("click", () => setVoice(!voiceOn));

// iOS only lets a page speak after a user gesture; a silent utterance during a tap unlocks it.
let speechUnlocked = false;
function unlockSpeech() {
  if (speechUnlocked || !window.speechSynthesis) return;
  speechUnlocked = true;
  window.speechSynthesis.speak(new SpeechSynthesisUtterance(""));
}

// Browsers (Chrome especially) load their voice list asynchronously: right after page load it's
// empty, and speaking then falls back to the default English voice, which spells Greek letter by
// letter. So wait for the list before picking a Greek voice.
function loadVoices() {
  const voices = window.speechSynthesis.getVoices();
  if (voices.length) return Promise.resolve(voices);
  return new Promise((resolve) => {
    const done = () => resolve(window.speechSynthesis.getVoices());
    window.speechSynthesis.addEventListener("voiceschanged", done, { once: true });
    setTimeout(done, 2000); // some browsers never fire the event
  });
}

async function pickVoice() {
  const voices = (await loadVoices()).filter((v) => v.lang.toLowerCase().replace("_", "-").startsWith("el"));
  return voices.find((v) => /premium|enhanced/i.test(v.name)) || voices[0] || null;
}

async function speak(text) {
  if (!voiceOn || !window.speechSynthesis) return;
  const clean = text.replace(/[\p{Extended_Pictographic}\uFE0F]/gu, "").trim();
  if (!clean) return;
  const voice = await pickVoice();
  if (!voice) {
    console.warn("No Greek voice installed; not reading the reply aloud.");
    return;
  }
  window.speechSynthesis.cancel();
  const utterance = new SpeechSynthesisUtterance(clean);
  utterance.voice = voice;
  utterance.lang = voice.lang;
  utterance.pitch = 1.3; // a little higher: cute pet voice
  utterance.rate = 1.05;
  window.speechSynthesis.speak(utterance);
}

function stopListening() {
  recognition?.stop();
}

function startListening() {
  window.speechSynthesis?.cancel(); // don't let the pet hear itself
  recognition = new SpeechRecognition();
  recognition.lang = VOICE_LANG;
  recognition.interimResults = true;
  recognition.onresult = (e) => {
    chatInput.value = Array.from(e.results).map((r) => r[0].transcript).join("");
  };
  recognition.onerror = (e) => {
    if (e.error === "not-allowed") addMessage("error", "Please allow microphone access in your browser.");
    else if (e.error !== "no-speech" && e.error !== "aborted") addMessage("error", `Mic error: ${e.error}`);
  };
  recognition.onend = () => {
    recognition = null;
    micBtn.classList.remove("listening");
    micBtn.textContent = "MIC";
    const text = chatInput.value.trim();
    if (text && !sendBtn.disabled) {
      chatInput.value = "";
      sendMessage(text);
    }
  };
  micBtn.classList.add("listening");
  micBtn.textContent = "STOP";
  chatInput.value = "";
  recognition.start();
}

micBtn.hidden = !SpeechRecognition;
micBtn.addEventListener("click", () => {
  unlockSpeech();
  if (recognition) stopListening();
  else startListening();
});

// ---------- rendering ----------
let lastWander = 0;

function wander(now, spriteW, style) {
  if (now - lastWander < style.every) return;
  lastWander = now;
  const r = Math.random();
  if (r < 0.2) state.dir *= -1;
  if (r < style.move) state.x += state.dir * 2;
  const maxX = W - spriteW - 2 - (state.pet.poops ? 9 : 0);
  if (state.x <= 1 || state.x >= maxX) {
    state.x = Math.max(1, Math.min(state.x, maxX));
    state.dir *= -1;
  }
}

// Little extras drawn around the pet to show how it feels.
function drawMoodEffects(mood, stage, x, y, w, now, frame) {
  if (mood === "sad") {
    const drop = Math.floor(now / 250) % 4; // tear rolling down
    const eye = EYE[stage];
    const ex = state.dir < 0 ? x + w - 1 - eye.x : x + eye.x;
    ctx.clearRect(ex, y + eye.y + 1 + drop, 1, 2); // drawn as "unlit" pixels so it shows on the face
  } else if (mood === "hungry") {
    drawSprite(ctx, S.thought, Math.min(x + w, W - 8), Math.max(0, y - 7));
  } else if (mood === "sick" && frame) {
    drawSprite(ctx, S.skull, x + Math.floor(w / 2) - 2, Math.max(0, y - 6));
  } else if (mood === "tired") {
    drawSprite(ctx, S.z, x + w + 1, y - 2 - (Math.floor(now / 700) % 3));
  } else if (mood === "thinking") {
    const dots = Math.floor(now / 400) % 4; // "..." appearing one dot at a time
    for (let i = 0; i < dots; i++) ctx.fillRect(x + w + 1 + i * 2, Math.max(0, y - 2), 1, 1);
  } else if (mood === "curious" && frame) {
    drawSprite(ctx, S.question, x + w + 1, Math.max(0, y - 6));
  } else if (mood === "happy" && Math.floor(now / 1000) % 3 === 0) {
    drawSprite(ctx, S.heart, x + w + 1, Math.max(0, y - 4 + frame));
  }
}

function render(now) {
  requestAnimationFrame(render);
  ctx.clearRect(0, 0, W, H);
  const p = state.pet;
  if (!p) return;

  const sleeping = p.alive && p.sleeping;
  lcd.classList.toggle("lights-off", sleeping);
  ctx.fillStyle = sleeping ? cssVar("--lcd-bg") : cssVar("--pet-color");
  const frame = Math.floor(now / 500) % 2;

  if (!p.alive) {
    drawSprite(ctx, S.ghost, 19, 6 + frame * 2);
    return;
  }
  if (p.stage === "egg") {
    drawSprite(ctx, S.egg, 19 + (frame ? 1 : 0), GROUND - S.egg.length);
    return;
  }

  if (!sleeping) Themes.drawLcdEffect(ctx, now, W, H);

  // poops, stacked on the right, with stink lines
  for (let i = 0; i < p.poops; i++) {
    const py = GROUND - 5 - i * 6 + (frame && i % 2 ? -1 : 0);
    drawSprite(ctx, S.poop, W - 7, py);
  }
  if (p.poops) drawSprite(ctx, S.stink, W - 5 + frame, GROUND - 5 - (p.poops - 1) * 6 - 4);

  const anim = state.anim && now - state.anim.start < state.anim.duration ? state.anim : null;
  if (!anim) state.anim = null;
  const progress = anim ? (now - anim.start) / anim.duration : 0;

  const mood = p.mood;
  const style = MOOD_STYLE[mood] || MOOD_STYLE.ok;
  // During an action animation show the happy face; otherwise the mood's face.
  const face = sleeping ? "sleep" : anim ? "happy" : mood;
  const rows = frame && !sleeping ? variant(p.stage, face, "step") : variant(p.stage, face);
  const w = rows[0].length;

  if (!sleeping && !anim) wander(now, w, style);
  let x = state.x;
  let y = GROUND - rows.length;
  if (!sleeping && !anim) {
    if (style.bounce && frame) y -= 1;
    if (style.shake) x += Math.floor(now / 120) % 2; // shivering
  }

  if (anim?.type === "eat") {
    x = 6;
    const bites = Math.floor(progress * 4);
    drawSprite(ctx, S.food, x + w + 3, GROUND - S.food.length, { maxCols: S.food[0].length - bites * 2 });
    if (frame) y += 1;
  } else if (anim?.type === "play") {
    if (frame) y -= 4;
    drawSprite(ctx, S.heart, x + w + 1, 3 + (frame ? 0 : 1));
    drawSprite(ctx, S.heart, x - 6, 6 + (frame ? 1 : 0));
  } else if (anim?.type === "clean") {
    const lineX = Math.round(W * (1 - progress));
    ctx.fillRect(lineX, 0, 1, H);
  }

  if (state.transform) {
    drawTransform(now, x + w / 2, y + rows.length / 2);
    drawSprite(ctx, rows, x, y, { flip: Math.floor(now / 120) % 2 === 0 }); // spinning
    return;
  }

  drawSprite(ctx, rows, x, y, { flip: state.dir < 0 && !sleeping });

  if (sleeping) {
    const zx = x + w + 1;
    drawSprite(ctx, S.z, zx, y - 2 - frame * 3);
    if (frame) drawSprite(ctx, S.z, zx + 4, y - 8);
  } else if (!anim) {
    drawMoodEffects(mood, p.stage, x, y, w, now, frame);
  }
}

// ---------- boot ----------
api("/theme").then(Themes.apply).catch(() => Themes.apply({ motif: "default", colors: ["#ffb3d4", "#e0408f", "#9c1f5f"] }));
buildIcons();
refresh();
setInterval(refresh, 5000);
requestAnimationFrame(render);
