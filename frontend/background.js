// Draws a pastel pixel-art wallpaper tile (plaid + hearts, mini eggs and sparkles)
// and uses it as the page background.
(function () {
  const TILE = 64; // tile size in art pixels
  const SCALE = 3; // CSS pixels per art pixel

  const PLAID = ["#fff3b8", "#cfe8ff", "#ffd3e6", "#d8f5c8"]; // yellow, blue, pink, green

  // 'o' outline, '#' fill, 'w' white shine, '-' screen
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
      "o#o-----o#o",
      "o#o-----o#o",
      "o#o-----o#o",
      "o##ooooo##o",
      "o#########o",
      "o##w#w#w##o",
      ".o#######o.",
      "..ooooooo..",
    ],
    sparkle: [
      "...o...",
      "...#...",
      "..###..",
      "o##w##o",
      "..###..",
      "...#...",
      "...o...",
    ],
  };

  const PALETTES = {
    pink: { o: "#e0609f", "#": "#ffb3d4", w: "#ffffff", "-": "#cfe8ff" },
    blue: { o: "#4f9be0", "#": "#8fd0ff", w: "#ffffff", "-": "#ffe0ef" },
    yellow: { o: "#f0b429", "#": "#ffe066", w: "#ffffff", "-": "#ffffff" },
  };

  const PLACEMENTS = [
    ["heart", "pink", 3, 3],
    ["egg", "blue", 36, 2],
    ["sparkle", "yellow", 22, 20],
    ["heart", "blue", 45, 36],
    ["egg", "pink", 8, 36],
    ["sparkle", "yellow", 55, 18],
    ["sparkle", "yellow", 28, 52],
  ];

  function mix(a, b) {
    const pa = parseInt(a.slice(1), 16), pb = parseInt(b.slice(1), 16);
    const ch = (p, s) => (p >> s) & 255;
    const m = (s) => Math.round((ch(pa, s) + ch(pb, s)) / 2);
    return `rgb(${m(16)}, ${m(8)}, ${m(0)})`;
  }

  const canvas = document.createElement("canvas");
  canvas.width = canvas.height = TILE;
  const g = canvas.getContext("2d");

  // plaid: each 8x8 cell blends its column stripe with its row stripe
  const CELL = 8;
  for (let y = 0; y < TILE / CELL; y++) {
    for (let x = 0; x < TILE / CELL; x++) {
      g.fillStyle = mix(PLAID[x % PLAID.length], PLAID[(y + 1) % PLAID.length]);
      g.fillRect(x * CELL, y * CELL, CELL, CELL);
    }
  }
  // thin white grid lines between cells
  g.fillStyle = "rgba(255, 255, 255, 0.7)";
  for (let i = 0; i < TILE; i += CELL) {
    g.fillRect(i, 0, 1, TILE);
    g.fillRect(0, i, TILE, 1);
  }

  for (const [name, palette, px, py] of PLACEMENTS) {
    SPRITES[name].forEach((row, j) => {
      [...row].forEach((c, i) => {
        const color = PALETTES[palette][c];
        if (!color) return;
        g.fillStyle = color;
        g.fillRect(px + i, py + j, 1, 1);
      });
    });
  }

  document.body.style.backgroundImage = `url(${canvas.toDataURL()})`;
  document.body.style.backgroundSize = `${TILE * SCALE}px`;
})();
