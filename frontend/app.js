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
};

// Per-stage tweaks: closed eyes for sleeping, alternate feet for walking.
const VARIANTS = {
  baby: { sleep: { 3: "#..####..#" }, step: { 8: ".#......#." } },
  child: { sleep: { 3: "#...####...#" }, step: { 10: ".##......##." } },
  adult: { sleep: { 4: "##############", 5: "##...####...##" }, step: { 13: ".##........##." } },
};

const ICON_ART = {
  feed: ["...##...", "..####..", ".######.", "##....##", "#......#", "########", "########", ".######."],
  light: ["..####..", ".#....#.", "#......#", "#......#", ".#....#.", "..####..", "..####..", "...##..."],
  play: ["..####..", ".#.##.#.", "#..##..#", "########", "########", "#..##..#", ".#.##.#.", "..####.."],
  clean: ["..##....", ".###....", "####....", "..#....#", ".#######", "########", ".######.", "..####.."],
  stats: ["........", "......#.", "......#.", "....#.#.", "....#.#.", "..#.#.#.", "..#.#.#.", "########"],
  chat: [".######.", "#......#", "#.#.#..#", "#......#", ".######.", "..#.....", ".#......", "........"],
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

function variant(stage, kind) {
  const changes = VARIANTS[stage]?.[kind] || {};
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
    state.pet = await api("/pet");
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

// ---------- sound ----------
let audio;
function beep(freq = 1800, ms = 60) {
  try {
    audio ||= new AudioContext();
    const osc = audio.createOscillator();
    const gain = audio.createGain();
    osc.type = "square";
    osc.frequency.value = freq;
    gain.gain.value = 0.04;
    osc.connect(gain).connect(audio.destination);
    osc.start();
    osc.stop(audio.currentTime + ms / 1000);
  } catch {
    /* audio is optional */
  }
}

// ---------- actions ----------
const ACTION_FOR = { feed: "feed", light: "sleep", play: "play", clean: "clean" };
const ANIM_FOR = { feed: "eat", play: "play", clean: "clean" };

async function runIcon(icon) {
  if (icon.soon) return say("SOON!");
  if (icon.id === "stats") return showStats();
  if (icon.id === "chat") return openChat();

  try {
    const { pet, message } = await api(`/pet/${ACTION_FOR[icon.id]}`, { method: "POST" });
    state.pet = pet;
    if (ANIM_FOR[icon.id]) state.anim = { type: ANIM_FOR[icon.id], start: performance.now(), duration: 2000 };
    say(message);
    beep(2400, 90);
  } catch (e) {
    say(e.message);
    beep(400, 200);
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
    <div class="stat">HEALTH ${meter(p.health)}</div>`;
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
  beep();

  if (state.pet && !state.pet.alive) {
    if (btn === "B") {
      state.pet = await api("/reset", { method: "POST", body: JSON.stringify({ name: state.pet.name }) });
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
  if (e.target.closest?.(".chat")) {
    if (e.key === "Escape") closeChat();
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
    const { message, changes } = await api("/chat", { method: "POST", body: JSON.stringify({ messages: chatHistory }) });
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
    if (e.error === "not-allowed") addMessage("error", "Δώσε άδεια για το μικρόφωνο στον browser.");
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

function wander(now, spriteW) {
  if (now - lastWander < 900) return;
  lastWander = now;
  const r = Math.random();
  if (r < 0.2) state.dir *= -1;
  if (r < 0.75) state.x += state.dir * 2;
  const maxX = W - spriteW - 2 - (state.pet.poops ? 9 : 0);
  if (state.x <= 1 || state.x >= maxX) {
    state.x = Math.max(1, Math.min(state.x, maxX));
    state.dir *= -1;
  }
}

function render(now) {
  requestAnimationFrame(render);
  ctx.clearRect(0, 0, W, H);
  const p = state.pet;
  if (!p) return;

  const sleeping = p.alive && p.sleeping;
  lcd.classList.toggle("lights-off", sleeping);
  ctx.fillStyle = sleeping ? cssVar("--lcd-bg") : cssVar("--lcd-px");
  const frame = Math.floor(now / 500) % 2;

  if (!p.alive) {
    drawSprite(ctx, S.ghost, 19, 6 + frame * 2);
    return;
  }
  if (p.stage === "egg") {
    drawSprite(ctx, S.egg, 19 + (frame ? 1 : 0), GROUND - S.egg.length);
    return;
  }

  // poops, stacked on the right
  for (let i = 0; i < p.poops; i++) {
    drawSprite(ctx, S.poop, W - 7, GROUND - 5 - i * 6 + (frame && i % 2 ? -1 : 0));
  }

  const anim = state.anim && now - state.anim.start < state.anim.duration ? state.anim : null;
  if (!anim) state.anim = null;
  const progress = anim ? (now - anim.start) / anim.duration : 0;

  let rows;
  if (sleeping) rows = variant(p.stage, "sleep");
  else rows = frame ? variant(p.stage, "step") : S[p.stage];
  const w = rows[0].length;

  if (!sleeping && !anim) wander(now, w);
  let x = state.x;
  let y = GROUND - rows.length;

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

  drawSprite(ctx, rows, x, y, { flip: state.dir < 0 && !sleeping });

  if (sleeping) {
    const zx = x + w + 1;
    drawSprite(ctx, S.z, zx, y - 2 - frame * 3);
    if (frame) drawSprite(ctx, S.z, zx + 4, y - 8);
  }
}

// ---------- boot ----------
buildIcons();
refresh();
setInterval(refresh, 5000);
requestAnimationFrame(render);
