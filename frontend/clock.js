// ---------- TAMA♥CLOCK: a pixel clock, analog or digital, dressed in the current theme ----------
// It doubles as a Pomodoro focus timer (FOCUS button): 25' focus, 5' break, a 15' break after
// every 4th focus round. The timer runs on an end timestamp saved in localStorage, so it keeps
// counting through a page refresh, and the pet cheers when a round is done.
// Drawn on a 56x56 canvas scaled up with crisp pixels. Colors come from the theme variables and
// the corners carry the active motif's sprites (pumpkins at Halloween, trees at Christmas...), so
// the clock changes outfit together with the device. The chosen mode is remembered per browser.

(function () {
  const SIZE = 56;
  const C = SIZE / 2; // center
  const RADIUS = 19;
  const root = document.getElementById("clock");
  const canvas = document.getElementById("clock-face");
  const modeBtn = document.getElementById("clock-mode");
  const g = canvas.getContext("2d");

  // 3x5 pixel font: digits, ':' and the letters needed for day and month names.
  const FONT = {
    0: ["###", "#.#", "#.#", "#.#", "###"], 1: [".#.", "##.", ".#.", ".#.", "###"],
    2: ["###", "..#", "###", "#..", "###"], 3: ["###", "..#", ".##", "..#", "###"],
    4: ["#.#", "#.#", "###", "..#", "..#"], 5: ["###", "#..", "###", "..#", "###"],
    6: ["###", "#..", "###", "#.#", "###"], 7: ["###", "..#", "..#", ".#.", ".#."],
    8: ["###", "#.#", "###", "#.#", "###"], 9: ["###", "#.#", "###", "..#", "###"],
    ":": ["...", ".#.", "...", ".#.", "..."], " ": ["...", "...", "...", "...", "..."],
    A: [".#.", "#.#", "###", "#.#", "#.#"], B: ["##.", "#.#", "##.", "#.#", "##."],
    C: [".##", "#..", "#..", "#..", ".##"], D: ["##.", "#.#", "#.#", "#.#", "##."],
    E: ["###", "#..", "##.", "#..", "###"], F: ["###", "#..", "##.", "#..", "#.."],
    G: [".##", "#..", "#.#", "#.#", ".##"], H: ["#.#", "#.#", "###", "#.#", "#.#"],
    I: ["###", ".#.", ".#.", ".#.", "###"], J: ["..#", "..#", "..#", "#.#", ".#."],
    K: ["#.#", "#.#", "##.", "#.#", "#.#"],
    L: ["#..", "#..", "#..", "#..", "###"], M: ["#.#", "###", "###", "#.#", "#.#"],
    N: ["##.", "#.#", "#.#", "#.#", "#.#"], O: [".#.", "#.#", "#.#", "#.#", ".#."],
    P: ["##.", "#.#", "##.", "#..", "#.."], R: ["##.", "#.#", "##.", "#.#", "#.#"],
    S: [".##", "#..", ".#.", "..#", "##."], T: ["###", ".#.", ".#.", ".#.", ".#."],
    U: ["#.#", "#.#", "#.#", "#.#", "###"], V: ["#.#", "#.#", "#.#", "#.#", ".#."],
    W: ["#.#", "#.#", "###", "###", "#.#"], Y: ["#.#", "#.#", ".#.", ".#.", ".#."],
  };
  const DAYS = ["SUN", "MON", "TUE", "WED", "THU", "FRI", "SAT"];
  const MONTHS = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"];

  let mode = "analog";
  try {
    mode = localStorage.getItem("clockMode") === "digital" ? "digital" : "analog";
  } catch {
    /* storage blocked: analog by default */
  }

  // ---------- colors (read from the animated theme variables) ----------
  const probe = document.createElement("i");
  probe.hidden = true;
  root.append(probe);

  function themeRgb(name) {
    probe.style.color = `var(${name})`;
    return getComputedStyle(probe).color.match(/\d+(\.\d+)?/g).slice(0, 3).map(Number);
  }
  const mix = (a, b, t) => a.map((v, i) => Math.round(v + (b[i] - v) * t));
  const css = (c) => `rgb(${c.join(",")})`;

  function colors() {
    const main = themeRgb("--theme-1"), accent = themeRgb("--theme-2"), deep = themeRgb("--theme-3");
    const ink = mix(deep, [26, 16, 48], 0.4); // darkened, like the pet on the LCD, so it always reads
    return { face: css(mix(main, [255, 255, 255], 0.7)), rim: css(main), ink: css(ink), accent: css(accent) };
  }

  // ---------- drawing helpers ----------
  const dot = (x, y) => g.fillRect(Math.round(x), Math.round(y), 1, 1);

  // Bresenham line: crisp, one-pixel steps, no anti-aliasing.
  function line(x0, y0, x1, y1) {
    [x0, y0, x1, y1] = [x0, y0, x1, y1].map(Math.round);
    const dx = Math.abs(x1 - x0), dy = -Math.abs(y1 - y0);
    const sx = x0 < x1 ? 1 : -1, sy = y0 < y1 ? 1 : -1;
    let err = dx + dy;
    for (;;) {
      dot(x0, y0);
      if (x0 === x1 && y0 === y1) break;
      const e2 = 2 * err;
      if (e2 >= dy) { err += dy; x0 += sx; }
      if (e2 <= dx) { err += dx; y0 += sy; }
    }
  }

  // Filled pixel disc (and, with `ring`, only its outline).
  function disc(r, ring = false) {
    for (let y = -r; y <= r; y++) {
      for (let x = -r; x <= r; x++) {
        const d = x * x + y * y;
        if (d <= r * r + r && (!ring || d > (r - 1) * (r - 1) + (r - 1))) dot(C + x, C + y);
      }
    }
  }

  function text(str, x, y, scale = 1) {
    [...str].forEach((ch, i) => {
      (FONT[ch] || FONT[" "]).forEach((row, j) => {
        [...row].forEach((c, k) => {
          if (c === "#") g.fillRect(x + (i * 4 + k) * scale, y + j * scale, scale, scale);
        });
      });
    });
  }
  const textWidth = (str, scale = 1) => (str.length * 4 - 1) * scale;

  function sprite({ rows, palette }, x, y) {
    rows.forEach((row, j) => [...row].forEach((c, k) => {
      if (!palette[c]) return;
      g.fillStyle = palette[c];
      g.fillRect(x + k, y + j, 1, 1);
    }));
  }

  // The motif's sprites in the corners (the third one only on the analog face, bottom right).
  function decorate(analog) {
    const sprites = window.Themes?.motifSprites?.() || [];
    if (sprites[0]) sprite(sprites[0], 1, 1);
    if (sprites[1]) sprite(sprites[1], SIZE - 1 - sprites[1].rows[0].length, 1);
    if (analog && sprites[2]) sprite(sprites[2], SIZE - 1 - sprites[2].rows[0].length, SIZE - 1 - sprites[2].rows.length);
  }

  // ---------- faces ----------
  function drawAnalog(now, col) {
    g.fillStyle = col.face;
    disc(RADIUS);
    g.fillStyle = col.rim;
    disc(RADIUS + 1, true);
    g.fillStyle = col.ink;
    disc(RADIUS + 2, true);

    for (let i = 0; i < 12; i++) {
      const a = (i / 12) * 2 * Math.PI;
      const quarter = i % 3 === 0;
      const r1 = RADIUS - 2, r0 = quarter ? RADIUS - 4 : RADIUS - 2;
      line(C + Math.sin(a) * r0, C - Math.cos(a) * r0, C + Math.sin(a) * r1, C - Math.cos(a) * r1);
    }

    const s = now.getSeconds(), m = now.getMinutes() + s / 60, h = (now.getHours() % 12) + m / 60;
    const hand = (turns, len) => line(C, C, C + Math.sin(turns * 2 * Math.PI) * len, C - Math.cos(turns * 2 * Math.PI) * len);
    hand(h / 12, 9);
    hand(m / 60, 14);
    g.fillStyle = col.accent;
    hand(s / 60, 15);
    g.fillStyle = col.ink;
    g.fillRect(C - 1, C - 1, 2, 2);
  }

  function drawDigital(now, col) {
    g.fillStyle = col.face;
    g.fillRect(3, 14, SIZE - 6, 30);
    g.fillStyle = col.ink;
    g.fillRect(3, 14, SIZE - 6, 1);
    g.fillRect(3, 43, SIZE - 6, 1);
    g.fillRect(3, 14, 1, 30);
    g.fillRect(SIZE - 4, 14, 1, 30);

    const pad = (n) => String(n).padStart(2, "0");
    const blink = now.getSeconds() % 2 === 0; // the colon blinks every second, like an old LCD
    const time = `${pad(now.getHours())}${blink ? ":" : " "}${pad(now.getMinutes())}`;
    text(time, Math.round((SIZE - textWidth(time, 2)) / 2), 18, 2);

    const date = `${DAYS[now.getDay()]} ${pad(now.getDate())} ${MONTHS[now.getMonth()]}`;
    g.fillStyle = col.accent;
    text(date, Math.round((SIZE - textWidth(date)) / 2), 33);

    // seconds as a row of pixels filling up along the bottom edge
    g.fillStyle = col.rim;
    g.fillRect(5, 40, Math.round(((SIZE - 10) * now.getSeconds()) / 59), 1);
  }

  // ---------- Pomodoro focus timer ----------
  const focusBtn = document.getElementById("clock-focus");
  const controls = document.getElementById("clock-controls");
  const startBtn = document.getElementById("focus-start");
  const ROUNDS = 4; // focus rounds before a long break
  const PHASES = {
    focus: { label: "FOCUS", minutes: 25, done: "BREAK TIME!" },
    short: { label: "BREAK", minutes: 5, done: "FOCUS TIME!" },
    long: { label: "LONG BREAK", minutes: 15, done: "FOCUS TIME!" },
  };
  const timer = loadTimer();

  function loadTimer() {
    const fresh = { phase: "focus", running: false, endAt: 0, leftMs: PHASES.focus.minutes * 60000, round: 0,
                    minutes: { focus: 25, short: 5, long: 15 } };
    try {
      return { ...fresh, ...JSON.parse(localStorage.getItem("focusTimer") || "{}") };
    } catch {
      return fresh;
    }
  }

  function saveTimer() {
    try {
      localStorage.setItem("focusTimer", JSON.stringify(timer));
    } catch {
      /* the timer still works, it just won't survive a refresh */
    }
  }

  const leftMs = () => (timer.running ? Math.max(0, timer.endAt - Date.now()) : timer.leftMs);
  const phaseMs = () => timer.minutes[timer.phase] * 60000;

  function drawFocus(col) {
    const left = leftMs();
    const phase = PHASES[timer.phase];
    g.fillStyle = col.face;
    g.fillRect(3, 14, SIZE - 6, 34);
    g.fillStyle = col.ink;
    g.fillRect(3, 14, SIZE - 6, 1);
    g.fillRect(3, 47, SIZE - 6, 1);
    g.fillRect(3, 14, 1, 34);
    g.fillRect(SIZE - 4, 14, 1, 34);

    g.fillStyle = col.accent;
    text(phase.label, Math.round((SIZE - textWidth(phase.label)) / 2), 17);

    // MM:SS; the colon blinks only while counting, so a paused timer looks frozen
    const secs = Math.ceil(left / 1000);
    const pad = (n) => String(n).padStart(2, "0");
    const colon = !timer.running || Math.floor(Date.now() / 1000) % 2 === 0 ? ":" : " ";
    const time = `${pad(Math.floor(secs / 60))}${colon}${pad(secs % 60)}`;
    g.fillStyle = col.ink;
    text(time, Math.round((SIZE - textWidth(time, 2)) / 2), 25, 2);

    // progress through the current phase, filling left to right
    g.fillStyle = col.rim;
    g.fillRect(6, 38, SIZE - 12, 2);
    g.fillStyle = col.accent;
    g.fillRect(6, 38, Math.round((SIZE - 12) * (1 - left / phaseMs())), 2);

    // one pixel "tomato" per focus round in the cycle; done ones are filled
    for (let i = 0; i < ROUNDS; i++) {
      const x = C - ROUNDS * 3 + i * 6 + 1;
      g.fillStyle = col.ink;
      g.fillRect(x, 42, 4, 3);
      if (i >= timer.round) {
        g.fillStyle = col.face;
        g.fillRect(x + 1, 43, 2, 1);
      }
    }
  }

  // A round ended: cheer, then move to the next phase (it waits for START, so nothing runs unnoticed).
  function finishPhase() {
    const phase = PHASES[timer.phase];
    if (timer.phase === "focus") timer.round += 1;
    let next = "focus";
    if (timer.phase === "focus") next = timer.round >= ROUNDS ? "long" : "short";
    if (timer.phase === "long") timer.round = 0;
    Object.assign(timer, { phase: next, running: false, endAt: 0, leftMs: timer.minutes[next] * 60000 });
    saveTimer();

    play("happy");
    say(phase.done, 4000);
    if (state.pet?.alive) state.anim = { type: "play", start: performance.now(), duration: 2000 };
    flashTitle(phase.done);
    if (document.hidden && "Notification" in window && Notification.permission === "granted") {
      new Notification("TAMA♥CLOCK", { body: timer.phase === "focus" ? "Break's over, back to focus!" : "Focus round done. Take a break!" });
    }
    syncControls();
  }

  // The tab title blinks until you come back to the page.
  function flashTitle(message) {
    const original = document.title;
    let on = false;
    const id = setInterval(() => (document.title = (on = !on) ? `⏰ ${message}` : original), 800);
    const stop = () => {
      clearInterval(id);
      document.title = original;
      window.removeEventListener("focus", stop);
    };
    window.addEventListener("focus", stop);
    if (!document.hidden) setTimeout(stop, 4000);
  }

  function syncControls() {
    startBtn.textContent = timer.running ? "PAUSE" : leftMs() < phaseMs() ? "GO ON" : "START";
    focusBtn.classList.toggle("running", timer.running);
    controls.querySelectorAll("[data-adjust]").forEach((b) => (b.disabled = timer.running));
  }

  function startPause() {
    if (timer.running) {
      Object.assign(timer, { running: false, leftMs: leftMs(), endAt: 0 });
    } else {
      Object.assign(timer, { running: true, endAt: Date.now() + timer.leftMs });
      if ("Notification" in window && Notification.permission === "default") Notification.requestPermission();
      say(timer.phase === "focus" ? "FOCUS MODE!" : "RELAX...", 1500);
    }
    saveTimer();
    syncControls();
    render();
  }

  controls.addEventListener("click", (e) => {
    const btn = e.target.closest("button");
    if (!btn) return;
    play("click");
    const action = btn.dataset.action;
    if (action === "start") return startPause();
    if (action === "reset") Object.assign(timer, { running: false, endAt: 0, leftMs: phaseMs() });
    if (action === "skip") return finishPhase();
    if (btn.dataset.adjust) {
      // +/- 5 minutes for the current phase (between 5 and 90), only while stopped
      const minutes = Math.min(90, Math.max(5, timer.minutes[timer.phase] + Number(btn.dataset.adjust)));
      timer.minutes[timer.phase] = minutes;
      timer.leftMs = minutes * 60000;
    }
    saveTimer();
    syncControls();
    render();
  });

  // ---------- views: analog / digital clock, or the focus timer ----------
  function render() {
    const now = new Date();
    if (timer.running && leftMs() <= 0) finishPhase();
    const col = colors();
    g.clearRect(0, 0, SIZE, SIZE);
    if (focusView) drawFocus(col);
    else if (mode === "analog") drawAnalog(now, col);
    else drawDigital(now, col);
    decorate(mode === "analog" && !focusView);
    canvas.setAttribute("aria-label", focusView
      ? `${PHASES[timer.phase].label.toLowerCase()}: ${Math.ceil(leftMs() / 60000)} minutes left`
      : now.toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" }));
  }

  let focusView = false;

  // Flip the face over (a quick squash animation) and swap the view at its midpoint.
  function flip(change) {
    play("click");
    canvas.classList.remove("flip");
    void canvas.offsetWidth; // restart the animation
    canvas.classList.add("flip");
    setTimeout(change, 90);
  }

  function setMode(next) {
    mode = next;
    modeBtn.textContent = mode === "analog" ? "DIGI" : "ANLG";
    modeBtn.title = `Switch to ${mode === "analog" ? "digital" : "analog"}`;
    try {
      localStorage.setItem("clockMode", mode);
    } catch {
      /* not remembered */
    }
    render();
  }

  function setFocusView(on) {
    focusView = on;
    controls.hidden = !on;
    modeBtn.hidden = on;
    focusBtn.textContent = on ? "CLOCK" : "FOCUS";
    focusBtn.title = on ? "Back to the clock" : "Pomodoro focus timer";
    syncControls();
    render();
  }

  modeBtn.addEventListener("click", () => flip(() => setMode(mode === "analog" ? "digital" : "analog")));
  focusBtn.addEventListener("click", () => flip(() => setFocusView(!focusView)));

  // While a new theme fades in, redraw every frame so the clock's colors follow smoothly.
  document.addEventListener("themechange", () => {
    const until = performance.now() + 1400;
    const step = () => {
      render();
      if (performance.now() < until) requestAnimationFrame(step);
    };
    requestAnimationFrame(step);
  });

  setMode(mode);
  setFocusView(timer.running); // a timer that was running before a refresh opens straight to it
  // Tick exactly on each new second.
  setTimeout(function tick() {
    render();
    setTimeout(tick, 1000 - (Date.now() % 1000));
  }, 1000 - (Date.now() % 1000));
})();
