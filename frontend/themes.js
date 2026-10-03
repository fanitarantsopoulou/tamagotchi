// Visual themes: applies the theme chosen by the backend (motif + 2-3 colors).
//
//  - Colors go into CSS custom properties (--theme-1/2/3). They're registered with @property in
//    style.css, so the browser animates them smoothly, and every derived color (shell, bezel,
//    buttons, chat, the pet itself) follows along.
//  - The pixel-art wallpaper is redrawn with the theme's colors and motif sprites, then
//    cross-faded over the old one.
//  - Each motif can add a small animated effect on the LCD (snow, rain...).
//
// To add a motif: add it to PRESETS in backend/theme.py, then (optionally) give it wallpaper
// sprites and an LCD effect in MOTIFS below. Unknown motifs fall back to the default look.

(function () {
  const TILE = 64; // wallpaper tile size in art pixels
  const SCALE = 3; // CSS pixels per art pixel

  // ---------- pixel sprites ('o' outline, '#' fill, '+' second fill, 'w' white shine) ----------
  const SPRITES = {
    heart: [
      "..ooo.ooo..",
      ".o###o###o.",
      "o#ww######o",
      "o#w#######o",
      "o#########o",
      ".o#######o.",
      "..o#####o..",
      "...o###o...",
      "....o#o....",
      ".....o.....",
    ],
    egg: [
      "...ooooo...",
      "..o#####o..",
      ".o#w#####o.",
      "o##ooooo##o",
      "o#o+++++o#o",
      "o#o+++++o#o",
      "o#o+++++o#o",
      "o##ooooo##o",
      "o#########o",
      "o##w#w#w##o",
      ".o#######o.",
      "..ooooooo..",
    ],
    sparkle: ["...o...", "...#...", "..###..", "o##w##o", "..###..", "...#...", "...o..."],
    tree: [
      ".....w.....",
      "....o#o....",
      "...o###o...",
      "..o#+###o..",
      "...o###o...",
      "..o###+#o..",
      ".o#+#####o.",
      "o#########o",
      "....ooo....",
      "....o+o....",
    ],
    ornament: ["...oo...", "..o..o..", ".oooooo.", "o#w####o", "o#w####o", "o######o", "o######o", ".oooooo."],
    snowflake: ["...w...", ".w.w.w.", "..www..", "wwwwwww", "..www..", ".w.w.w.", "...w..."],
    cloud: ["...oooo....", "..o####o...", ".o#w####oo.", "o#w#######o", "o#########o", ".ooooooooo."],
    drop: ["..o..", "..o..", ".o#o.", "o#w#o", "o###o", ".ooo."],
    sun: ["o..o..o", ".o###o.", ".#ww##.", "o##w##o", ".#####.", ".o###o.", "o..o..o"],
    flower: ["..o.o..", ".o+o+o.", "o+o#o+o", ".o###o.", "o+o#o+o", ".o+o+o.", "..o.o.."],
    mug: [".w.w....", "w.w.....", "oooooo..", "o####ooo", "o#w##o.o", "o####ooo", "o####o..", ".oooo..."],
    leaf: ["....oo", "..oo#o", ".o##+o", "o#+##o", "o##oo.", ".oo..."],
    icecream: ["..ooo..", ".o#w#o.", "o##w##o", "o#####o", ".ooooo.", ".o+++o.", "..o+o..", "..o+o..", "...o..."],
    wave: ["...oo......", "..o##o...oo", ".o#w##o.o#o", "o#######o#o", "ooooooooooo"],
    briefcase: ["...oooo...", "...o..o...", "oooooooooo", "o########o", "o##w#####o", "oooo++oooo", "o########o", "oooooooooo"],
    laptop: [".ooooooooo.", ".o+++++++o.", ".o+w+++++o.", ".o+++++++o.", ".ooooooooo.", "o#########o", "ooooooooooo"],
    tee: [".ooo...ooo.", "o###ooo###o", "o#########o", ".oo#####oo.", "..o#w###o..", "..o#####o..", "..o#####o..", "..ooooooo.."],
    sneaker: ["..ooo......", ".o#w#o.....", ".o###ooooo.", "o#######w#o", "o#########o", "o+++++++++o", "ooooooooooo"],
    bowtie: ["oo.......oo", "o#oo...oo#o", "o#w#ooo###o", "o###o+o###o", "o#oo...oo#o", "oo.......oo"],
    diamond: [".ooooooo.", "o#w#+#+#o", "ooooooooo", ".o#+#+#o.", "..o#+#o..", "...o#o...", "....o...."],
    balloon: [".ooooo.", "o##w##o", "o#w###o", "o#####o", "o#####o", ".o###o.", "..ooo..", "...o...", "....o..", "...o...", "....o.."],
    confetti: ["#.....+", "..+.#..", ".w.....", "....#.+", "+.#....", ".....w.", "..+..#."],
    pumpkin: ["....oo...", "...o.....", ".ooooooo.", "o#+#+#+#o", "o#w#+#+#o", "o#+#+#+#o", "o#+#+#+#o", ".ooooooo."],
    bat: ["o.........o", "oo..o.o..oo", "o#oo###oo#o", ".o##w#w##o.", "..o.o.o.o.."],
    dumbbell: ["oo.......oo", "o#o.....o#o", "o#o+++++o#o", "o#o.....o#o", "oo.......oo"],
    bottle: ["..oo..", ".o++o.", "oooooo", "o#w##o", "o#w##o", "o####o", "o####o", "oooooo"],
    butterfly: [".oo.....oo.", "o##o...o##o", "o#w#o.o#w#o", ".o###o###o.", "o##o.o.o##o", "o#o..o..o#o", ".o.......o."],
    flipphone: [".oooo.", "o++++o", "o+w++o", "o++++o", "oooooo", "o#w##o", "o#o#oo", "o####o", "o#o#oo", "o####o", ".oooo."],
    cassette: ["ooooooooooo", "o#########o", "o#o+o#o+o#o", "o#ooo#ooo#o", "o####w####o", "o#ooooooo#o", "ooooooooooo"],
    bolt: ["...ooo", "..o#o.", ".o#o..", "o####o", "..o#o.", ".o#o..", "o#o...", "oo...."],
    peace: ["..ooooo..", ".o##o##o.", "o###o###o", "o###o###o", "o##ooo##o", "o#o#o#o#o", "oo##o##oo", ".o##o##o.", "..ooooo.."],
    discoball: ["....o....", "....o....", "..ooooo..", ".o#w#+#o.", "o#+#+#+#o", "o+#+#+#+o", "o#+#+#+#o", ".o+#+#+o.", "..ooooo.."],
    star: ["...o...", "..o#o..", "ooo#ooo", "o##w##o", ".o###o.", "o#o.o#o", "oo...oo"],
  };

  // ---------- motif registry: wallpaper sprites + LCD effect ----------
  // Optional per motif: `plaid` (4 fixed tints) and `palettes` (one sprite palette per placement)
  // override the colors computed from the theme. The default motif uses them to keep the original
  // multi-color pastel wallpaper.
  const PINK = { o: "#e0609f", "#": "#ffb3d4", "+": "#cfe8ff", w: "#ffffff" };
  const BLUE = { o: "#4f9be0", "#": "#8fd0ff", "+": "#ffe0ef", w: "#ffffff" };
  const YELLOW = { o: "#f0b429", "#": "#ffe066", "+": "#ffffff", w: "#ffffff" };
  const MOTIFS = {
    default: {
      sprites: ["heart", "egg", "sparkle"],
      lcd: null,
      plaid: ["#fff3b8", "#cfe8ff", "#ffd3e6", "#d8f5c8"], // yellow, blue, pink, green
      palettes: [PINK, BLUE, YELLOW, BLUE, PINK, YELLOW, YELLOW],
    },
    custom: { sprites: ["heart", "egg", "sparkle"], lcd: null },
    christmas: { sprites: ["tree", "ornament", "snowflake"], lcd: "snow" },
    party: { sprites: ["balloon", "confetti", "star"], lcd: "confetti" },
    summer: { sprites: ["sun", "icecream", "wave"], lcd: "sun" },
    happy: { sprites: ["sun", "flower", "sparkle"], lcd: "sun" },
    rainy: { sprites: ["cloud", "drop", "drop"], lcd: "rain" },
    cozy: { sprites: ["mug", "leaf", "heart"], lcd: "leaves" },
    casual: { sprites: ["tee", "sneaker", "heart"], lcd: null },
    athletic: { sprites: ["dumbbell", "sneaker", "bottle"], lcd: "speed" },
    office: { sprites: ["briefcase", "laptop", "mug"], lcd: null },
    formal: { sprites: ["bowtie", "diamond", "star"], lcd: "glint" },
    y2k: { sprites: ["butterfly", "flipphone", "sparkle"], lcd: "butterflies" },
    seventies: { sprites: ["discoball", "flower", "peace"], lcd: "disco" },
    eighties: { sprites: ["cassette", "bolt", "star"], lcd: "sunset" },
    halloween: { sprites: ["pumpkin", "bat", "star"], lcd: "bats" },
  };

  // Where sprites sit inside one wallpaper tile: [sprite slot (0-2), x, y].
  const PLACEMENTS = [[0, 3, 3], [1, 36, 2], [2, 22, 20], [0, 45, 36], [1, 8, 36], [2, 55, 18], [2, 28, 52]];

  // ---------- color helpers ----------
  function rgb(hex) {
    const n = parseInt(hex.slice(1), 16);
    return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
  }
  // Blend hex color `a` toward hex color `b` by `t` (0 = a, 1 = b); returns hex.
  function mix(a, b, t) {
    const ca = rgb(a), cb = rgb(b);
    return "#" + ca.map((v, i) => Math.round(v + (cb[i] - v) * t).toString(16).padStart(2, "0")).join("");
  }
  // Two colors are enough; the third (deep) one is derived from the accent when missing.
  function palette(colors) {
    const [main, accent] = colors;
    return { main, accent, deep: colors[2] || mix(accent, "#000000", 0.45) };
  }

  // ---------- wallpaper ----------
  function drawWallpaper(colors, motif) {
    const { main, accent, deep } = palette(colors);
    const canvas = document.createElement("canvas");
    canvas.width = canvas.height = TILE;
    const g = canvas.getContext("2d");

    const m = MOTIFS[motif] || MOTIFS.default;
    // Plaid: soft tints of the theme colors; each 8x8 cell blends its column and row stripe.
    const tints = m.plaid || [mix(main, "#ffffff", 0.75), mix(accent, "#ffffff", 0.8), "#fff8ec", mix(deep, "#ffffff", 0.85)];
    const CELL = 8;
    for (let y = 0; y < TILE / CELL; y++) {
      for (let x = 0; x < TILE / CELL; x++) {
        g.fillStyle = tints[x % tints.length];
        g.fillRect(x * CELL, y * CELL, CELL, CELL);
        g.fillStyle = tints[(y + 1) % tints.length];
        g.globalAlpha = 0.5;
        g.fillRect(x * CELL, y * CELL, CELL, CELL);
        g.globalAlpha = 1;
      }
    }
    g.fillStyle = "rgba(255, 255, 255, 0.7)"; // thin grid lines
    for (let i = 0; i < TILE; i += CELL) {
      g.fillRect(i, 0, 1, TILE);
      g.fillRect(0, i, TILE, 1);
    }

    const sprites = m.sprites;
    const colorsFor = (i) =>
      (m.palettes && m.palettes[i]) || { o: deep, "#": i % 2 ? accent : main, "+": i % 2 ? main : accent, w: "#ffffff" };
    PLACEMENTS.forEach(([slot, px, py], i) => {
      const pal = colorsFor(i);
      SPRITES[sprites[slot]].forEach((row, j) => {
        [...row].forEach((c, k) => {
          if (!pal[c]) return;
          g.fillStyle = pal[c];
          g.fillRect(px + k, py + j, 1, 1);
        });
      });
    });
    return canvas.toDataURL();
  }

  // Two stacked layers: the new wallpaper fades in on top, then becomes the base.
  const layers = [0, 1].map(() => {
    const el = document.createElement("div");
    el.className = "wallpaper";
    el.style.backgroundSize = `${TILE * SCALE}px`;
    document.body.prepend(el);
    return el;
  });
  let front = 0;

  let fadeTimer;
  function showWallpaper(url) {
    const incoming = layers[1 - front];
    const outgoing = layers[front];
    incoming.style.backgroundImage = `url(${url})`;
    incoming.style.zIndex = "-1";
    outgoing.style.zIndex = "-2";
    incoming.classList.add("visible"); // fades in via the CSS opacity transition
    front = 1 - front;
    // Once the new layer covers the screen, hide the other one. Cancel any earlier pending hide,
    // otherwise two quick theme changes could hide the newest wallpaper.
    clearTimeout(fadeTimer);
    fadeTimer = setTimeout(() => layers[1 - front].classList.remove("visible"), 1300);
  }

  // ---------- LCD effects (drawn in the pet's color on the 48x32 screen) ----------
  const LCD_EFFECTS = {
    // falling snowflakes + a garland along the top
    snow(ctx, now, W, H) {
      for (let x = 0; x < W; x += 2) ctx.fillRect(x, (x % 6 === 0) ? 1 : 0, 1, 1);
      for (let x = 3; x < W; x += 6) ctx.fillRect(x, 2, 1, 1);
      for (let i = 0; i < 7; i++) {
        const y = Math.floor(now / 180 + i * 9) % H;
        const x = (i * 7 + Math.floor((now / 900 + i) % 2)) % W;
        ctx.fillRect(x, y, 1, 1);
      }
    },
    // diagonal raindrops
    rain(ctx, now, W, H) {
      for (let i = 0; i < 9; i++) {
        const y = Math.floor(now / 60 + i * 11) % (H + 4) - 4;
        const x = (i * 6 + Math.floor((now / 60 + i * 11) / (H + 4)) * 3) % W;
        ctx.fillRect(x, y, 1, 2);
      }
    },
    // a little sun in the corner with blinking rays
    sun(ctx, now) {
      ctx.fillRect(2, 2, 3, 3);
      if (Math.floor(now / 400) % 2) {
        [[3, 0], [3, 6], [0, 3], [6, 3], [0, 0], [6, 0], [0, 6], [6, 6]].forEach(([x, y]) => ctx.fillRect(x, y, 1, 1));
      }
    },
    // a disco ball hanging in the top-left corner, with light dots spinning around it
    disco(ctx, now) {
      const cx = 6, cy = 4;
      ctx.fillRect(cx, 0, 1, 2); // string
      ctx.fillRect(cx - 1, cy - 1, 3, 3); // ball
      for (let i = 0; i < 4; i++) {
        const a = now / 300 + (i * Math.PI) / 2;
        ctx.fillRect(Math.round(cx + Math.cos(a) * 5), Math.round(cy + Math.sin(a) * 3), 1, 1);
      }
    },
    // a tiny butterfly fluttering across the screen
    butterflies(ctx, now, W) {
      const x = Math.floor(now / 140) % (W + 6) - 3;
      const y = 6 + Math.round(Math.sin(now / 250) * 3);
      const open = Math.floor(now / 160) % 2;
      ctx.fillRect(x, y, 1, 2);
      ctx.fillRect(x - 1 - open, y - open, 1 + open, 1 + open);
      ctx.fillRect(x + 1, y - open, 1 + open, 1 + open);
    },
    // a striped synthwave sunset in the corner, stripes scrolling down
    sunset(ctx, now) {
      const scroll = Math.floor(now / 250) % 3;
      for (let y = 0; y < 6; y++) {
        if ((y + scroll) % 3 === 0 && y > 1) continue; // the classic sliced stripes
        const half = Math.round(Math.sqrt(9 - (y - 3) ** 2 + 6));
        ctx.fillRect(5 - half, 1 + y, half * 2, 1);
      }
    },
    // speed lines whooshing past
    speed(ctx, now, W) {
      for (let i = 0; i < 4; i++) {
        const x = W - (Math.floor(now / 30 + i * 13) % (W + 6));
        ctx.fillRect(x, 4 + i * 4, 4, 1);
      }
    },
    // multi-size confetti falling fast
    confetti(ctx, now, W, H) {
      for (let i = 0; i < 10; i++) {
        const y = Math.floor(now / 110 + i * 7) % H;
        const x = (i * 5 + Math.floor((now / 110 + i * 7) / H) * 7) % W;
        ctx.fillRect(x, y, i % 3 ? 1 : 2, 1);
      }
    },
    // little glints twinkling in the corners
    glint(ctx, now, W) {
      const on = Math.floor(now / 300) % 4;
      const spots = [[3, 3], [W - 4, 12], [3, 12], [W - 12, 20]]; // top-right is the weather reading
      const [x, y] = spots[on];
      ctx.fillRect(x - 1, y, 3, 1);
      ctx.fillRect(x, y - 1, 1, 3);
    },
    // a bat flapping across the top of the screen
    bats(ctx, now, W) {
      const x = Math.floor(now / 90) % (W + 8) - 4;
      const y = 3 + Math.round(Math.sin(now / 300) * 1.5);
      const up = Math.floor(now / 150) % 2;
      ctx.fillRect(x, y, 1, 1);
      ctx.fillRect(x - 1, y - up, 1, 1);
      ctx.fillRect(x + 1, y - up, 1, 1);
      ctx.fillRect(x - 2, y - 1 + up, 1, 1);
      ctx.fillRect(x + 2, y - 1 + up, 1, 1);
    },
    // leaves drifting down and swaying
    leaves(ctx, now, W, H) {
      for (let i = 0; i < 4; i++) {
        const y = Math.floor(now / 260 + i * 13) % H;
        const x = (i * 12 + 4 + Math.round(Math.sin(now / 500 + i) * 2) + W) % W;
        ctx.fillRect(x, y, 2, 1);
        ctx.fillRect(x + 1, y + 1, 1, 1);
      }
    },
  };

  // ---------- public API ----------
  let current = null;

  window.Themes = {
    // Apply a theme object from the backend: { motif, colors: [main, accent, deep?] }.
    apply(theme) {
      const key = JSON.stringify(theme);
      if (key === current) return;
      current = key;
      const { main, accent, deep } = palette(theme.colors);
      const root = document.documentElement.style;
      root.setProperty("--theme-1", main);
      root.setProperty("--theme-2", accent);
      root.setProperty("--theme-3", deep);
      document.documentElement.dataset.motif = theme.motif;
      showWallpaper(drawWallpaper([main, accent, deep], theme.motif));
      document.dispatchEvent(new CustomEvent("themechange", { detail: theme }));
    },

    // The active motif's sprites with their colors, for widgets that decorate themselves
    // (e.g. the clock): [{ rows, palette }] in the same palette logic as the wallpaper.
    motifSprites() {
      const theme = current ? JSON.parse(current) : { motif: "default", colors: ["#ffb3d4", "#e0408f"] };
      const { main, accent, deep } = palette(theme.colors);
      const m = MOTIFS[theme.motif] || MOTIFS.default;
      return m.sprites.map((name, i) => ({
        rows: SPRITES[name],
        palette: (m.palettes && m.palettes[i]) || { o: deep, "#": i % 2 ? accent : main, "+": i % 2 ? main : accent, w: "#ffffff" },
      }));
    },

    // Draw the active motif's LCD effect (called every frame by app.js).
    drawLcdEffect(ctx, now, W, H) {
      const motif = document.documentElement.dataset.motif;
      const effect = LCD_EFFECTS[(MOTIFS[motif] || {}).lcd];
      if (effect) effect(ctx, now, W, H);
    },
  };
})();
