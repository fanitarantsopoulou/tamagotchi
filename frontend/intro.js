// Opening effect: a pixel-block dissolve uncovers the app, then the panels pop in step by step.
(() => {
  const BLOCK = 20;       // size of one dissolve block, in CSS px
  const DURATION = 900;   // ms for the whole dissolve
  const cover = document.getElementById("intro");
  if (!cover) return;
  const done = () => {
    cover.remove();
    document.body.classList.remove("intro");
  };
  if (matchMedia("(prefers-reduced-motion: reduce)").matches) return done();

  // the theme loads after this runs, so use the colors themes.js saved on the last visit
  let colors = ["#ffb3d4", "#e0408f"];
  try { colors = JSON.parse(localStorage.getItem("tama-intro-colors")) || colors; } catch {}
  const canvas = document.createElement("canvas");
  const w = (canvas.width = Math.ceil(innerWidth / BLOCK));
  const h = (canvas.height = Math.ceil(innerHeight / BLOCK));
  const ctx = canvas.getContext("2d");
  // one pixel per block (drawn up-scaled with crisp edges), checkered in two theme colors
  const cells = [];
  for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) {
    ctx.fillStyle = colors[(x + y) % 2];
    ctx.fillRect(x, y, 1, 1);
    cells.push([x, y]);
  }
  for (let i = cells.length - 1; i > 0; i--) { // shuffle: random dissolve order
    const j = Math.floor(Math.random() * (i + 1));
    [cells[i], cells[j]] = [cells[j], cells[i]];
  }
  cover.style.background = "none";
  cover.append(canvas);

  const start = performance.now();
  let erased = 0;
  const step = (now) => {
    const t = Math.min((now - start) / DURATION, 1);
    const target = Math.floor(t * t * cells.length); // starts slow, speeds up
    for (; erased < target; erased++) ctx.clearRect(cells[erased][0], cells[erased][1], 1, 1);
    if (t < 1) requestAnimationFrame(step);
    else done();
  };
  requestAnimationFrame(step);
})();
