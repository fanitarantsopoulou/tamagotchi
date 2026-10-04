// ---------- MY.SHELF: the personal reading shelf, a column on the left of the page ----------
// Books you've read or are reading, each lying flat on the pile with a 1-5 heart rating. A book
// slides out a little when the cursor is on it; click one to edit it, or + to add a new one.
// A new shelf starts full of blank books (top to bottom of the page): title them or delete them.
(function () {
  const root = document.getElementById("reading-shelf");
  const list = document.getElementById("reading-list");
  const form = document.getElementById("reading-form");
  const addBtn = document.getElementById("reading-add");
  const toggleBtn = document.getElementById("reading-toggle");
  const statsEl = document.getElementById("reading-stats");
  const quipEl = document.getElementById("reading-quip");
  const MAX_RATING = 5;
  // Spine looks, picked per book id so each keeps its own look: [cover, lettering, band].
  const LOOKS = [
    ["#e84a3a", "#fff", "#f4d35e"], ["#f2c230", "#2a2a2a", "#2a2a2a"], ["#1f3a5f", "#e9e2d0", "#c9a24a"],
    ["#f3efe6", "#2c2c34", "#c0392b"], ["#e0508a", "#fff", "#fff"], ["#4a86b8", "#fff", "#f3efe6"],
    ["#2a2a30", "#e9e2d0", "#c9a24a"], ["#b5532a", "#f6e7d0", "#f6e7d0"], ["#3e7f6e", "#f6efe0", "#f6efe0"],
    ["#d9c7a4", "#3b2a1c", "#7a5a3a"], ["#6b3f8f", "#fff", "#f4d35e"], ["#f08a5d", "#2a1a2e", "#2a1a2e"],
  ];
  // Lettering styles: the face, size, spacing and case that make spines feel printed by different houses.
  // Titles are shown exactly as typed (no forced capitals).
  const FACES = [
    { face: "Georgia, 'Times New Roman', serif", size: "13px", track: "0" },
    { face: "'Tiny5', 'VT323', monospace", size: "14px", track: "0.5px" },
    { face: "'Arial Narrow', 'Helvetica Neue', Arial, sans-serif", size: "15px", track: "1px" },
    { face: "'VT323', monospace", size: "17px", track: "0" },
  ];
  const AVG_THICKNESS = 34; // px, the middle of the 26-42px range below
  let books = [];
  let editing = null; // id of the book in the form, or null when adding
  let rating = 0;
  let color = ""; // chosen cover color, "" = the book's automatic one

  async function request(path, options) {
    const res = await fetch("/api/reading" + path, {
      headers: { "Content-Type": "application/json" },
      ...options,
    });
    const data = res.status === 204 ? null : await res.json();
    if (!res.ok) throw new Error((data && data.detail) || "ERROR");
    return data;
  }

  // Lettering that reads on a chosen cover: dark on light colors, light on dark ones.
  function inkFor(hex) {
    const [r, g, b] = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16));
    return 0.299 * r + 0.587 * g + 0.114 * b > 150 ? "#2a2a2a" : "#ffffff";
  }

  // [cover, lettering, band]: the chosen color if any, otherwise the book's automatic look.
  function lookFor(book) {
    if (!book.color) return LOOKS[book.id % LOOKS.length];
    const ink = inkFor(book.color);
    return [book.color, ink, ink];
  }

  // ----- stats: counts per status and a little comment on them -----
  function quip({ read, reading, shelf }) {
    if (!read && !reading && !shelf) return "Your shelf is waiting for its first book!";
    if (shelf >= 3 && shelf > read) return "Wow! A lot of books are getting dusty...";
    if (reading >= 3) return `${reading} books at once? Multitasking queen!`;
    if (!reading && shelf) return "Pick one from the pile and start reading!";
    if (read >= 10) return `Look at you, bookworm! ${read} books read!`;
    if (reading) return "Happy reading! Don't lose your bookmark.";
    return "All done! Time to find a new book.";
  }

  function renderStats() {
    const titled = books.filter((b) => b.title);
    const count = (status) => titled.filter((b) => b.status === status).length;
    const stats = { read: count("read"), reading: count("reading"), shelf: count("shelf") };
    statsEl.replaceChildren(
      ...[["read", "READ"], ["reading", "READING"], ["shelf", "ON SHELF"]].map(([key, label]) => {
        const box = document.createElement("div");
        const n = document.createElement("b");
        n.textContent = stats[key];
        const l = document.createElement("span");
        l.textContent = label;
        box.append(n, l);
        return box;
      }),
    );
    quipEl.textContent = quip(stats);
  }

  // ----- hide / expand: remembered per browser -----
  let slideTimer = 0;
  function setCollapsed(collapsed, animate = true) {
    // stagger: the top book leaves first and comes back last
    list.querySelectorAll(".rbook").forEach((el, i, all) => {
      el.style.setProperty("--delay", `${(collapsed ? i : all.length - 1 - i) * 0.03}s`);
    });
    root.classList.toggle("sliding", animate);
    root.classList.toggle("collapsed", collapsed);
    clearTimeout(slideTimer);
    if (animate) slideTimer = setTimeout(() => root.classList.remove("sliding"), 1500);
    toggleBtn.textContent = collapsed ? "▶" : "◀";
    toggleBtn.title = collapsed ? "Show the books" : "Hide the books";
    toggleBtn.setAttribute("aria-expanded", String(!collapsed));
    if (collapsed) form.hidden = true;
    try {
      localStorage.setItem("shelfCollapsed", String(collapsed));
    } catch {
      /* not remembered */
    }
  }
  toggleBtn.addEventListener("click", () => setCollapsed(!root.classList.contains("collapsed")));
  try {
    if (localStorage.getItem("shelfCollapsed") === "true") setCollapsed(true, false);
  } catch {
    /* storage blocked: start expanded */
  }

  const hearts = (n) => "♥".repeat(n) + "♡".repeat(MAX_RATING - n);

  function render() {
    renderStats();
    list.replaceChildren();
    if (!books.length) {
      const empty = document.createElement("p");
      empty.className = "reading-empty";
      empty.textContent = "No books yet. Press + to add one!";
      list.append(empty);
      return;
    }
    // newest on top, like a real pile
    for (const book of [...books].reverse()) {
      const blank = !book.title;
      const btn = document.createElement("button");
      btn.type = "button";
      btn.dataset.id = book.id;
      btn.className = "rbook" + (blank ? " blank" : book.status === "reading" ? " in-progress" : "");
      const [cover, ink, band] = lookFor(book);
      const f = FACES[(book.id * 5) % FACES.length];
      const pick = (n, mod) => (book.id * n) % mod; // cheap deterministic variety
      const vars = {
        "--spine": cover, "--ink": ink, "--band": band,
        "--h": `${26 + pick(7, 5) * 4}px`, // thickness 26-42px, like real paperbacks and hardbacks
        "--w": `${168 + pick(11, 5) * 9}px`, // spine length 168-204px
        "--face": f.face, "--size": f.size, "--track": f.track,
      };
      for (const [k, v] of Object.entries(vars)) btn.style.setProperty(k, v);
      btn.title = blank ? "Blank book: click to give it a title" : `${book.title}${book.author ? " - " + book.author : ""}`;
      const title = document.createElement("span");
      title.className = "rbook-title";
      title.textContent = book.title;
      const meta = document.createElement("span");
      meta.className = "rbook-meta";
      meta.textContent = blank ? "" : book.status === "reading" ? "READING" : book.rating ? hearts(book.rating) : "";
      btn.append(title, meta);
      btn.addEventListener("click", () => openForm(book));
      list.append(btn);
    }
  }

  async function load() {
    try {
      let data = await request("");
      if (!data.filled) {
        // first visit: blank books enough to reach the top of the page (a one-time fill)
        const used = data.books.length * AVG_THICKNESS;
        const count = Math.max(0, Math.ceil((list.clientHeight - used) / AVG_THICKNESS));
        data = await request("/fill", { method: "POST", body: JSON.stringify({ count }) });
      }
      books = data.books;
    } catch {
      books = [];
    }
    render();
  }

  // ----- add / edit form -----
  function paintHearts() {
    form.querySelectorAll("[data-rate]").forEach((b) => {
      const on = Number(b.dataset.rate) <= rating;
      b.textContent = on ? "♥" : "♡";
      b.classList.toggle("on", on);
    });
  }

  // Color swatches: "auto" plus the automatic covers, and a picker for any other color.
  const swatches = form.querySelector(".reading-colors");
  const picker = form.elements.colorpick;
  for (const hex of ["", ...LOOKS.map((l) => l[0])]) {
    const b = document.createElement("button");
    b.type = "button";
    b.dataset.color = hex;
    b.title = hex || "Automatic";
    if (hex) b.style.background = hex;
    else b.classList.add("auto");
    swatches.insertBefore(b, picker);
  }
  // Live preview: the book being edited wears the chosen color right away. Nothing is saved until
  // SAVE; closing the form any other way re-renders the shelf with the saved colors.
  function previewColor() {
    const book = books.find((b) => b.id === editing);
    const el = book && list.querySelector(`.rbook[data-id="${book.id}"]`);
    if (!el) return; // a new book has nothing on the shelf to preview yet
    const [cover, ink, band] = lookFor({ ...book, color });
    el.style.setProperty("--spine", cover);
    el.style.setProperty("--ink", ink);
    el.style.setProperty("--band", band);
  }

  function paintColor() {
    swatches.querySelectorAll("[data-color]").forEach((b) => b.classList.toggle("on", b.dataset.color === color));
    const custom = color && !LOOKS.some((l) => l[0] === color);
    picker.classList.toggle("on", Boolean(custom));
    if (color) picker.value = color;
    previewColor();
  }
  picker.addEventListener("input", () => {
    color = picker.value.toLowerCase();
    paintColor();
  });

  function openForm(book) {
    if (!form.hidden) render(); // switching books: undo the previous one's unsaved preview
    editing = book ? book.id : null;
    rating = book ? book.rating : 0;
    color = (book && book.color) || "";
    form.elements.title.value = book ? book.title : "";
    form.elements.author.value = book ? book.author : "";
    form.elements.status.value = book ? book.status : "read";
    form.querySelector("[data-del]").hidden = !book;
    form.querySelector("[data-error]").textContent = "";
    paintHearts();
    paintColor();
    form.hidden = false;
    form.elements.title.focus();
  }

  function closeForm() {
    form.hidden = true;
    render(); // drops any unsaved color preview
  }

  form.addEventListener("click", async (e) => {
    const rate = e.target.closest("[data-rate]");
    const swatch = e.target.closest("[data-color]");
    if (swatch) {
      color = swatch.dataset.color;
      paintColor();
    } else if (rate) {
      const n = Number(rate.dataset.rate);
      rating = rating === n ? 0 : n; // click the same heart again to clear
      paintHearts();
    } else if (e.target.closest("[data-cancel]")) {
      closeForm();
    } else if (e.target.closest("[data-del]")) {
      try {
        await request(`/${editing}`, { method: "DELETE" });
        form.hidden = true;
        await load();
      } catch (err) {
        form.querySelector("[data-error]").textContent = err.message;
      }
    }
  });

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const body = JSON.stringify({
      title: form.elements.title.value,
      author: form.elements.author.value,
      status: form.elements.status.value,
      rating,
      color,
    });
    try {
      await (editing === null ? request("", { method: "POST", body }) : request(`/${editing}`, { method: "PATCH", body }));
      form.hidden = true;
      await load(); // re-renders with the saved book (no flash of the old color)
    } catch (err) {
      form.querySelector("[data-error]").textContent = err.message;
    }
  });

  addBtn.addEventListener("click", () => (form.hidden ? openForm(null) : closeForm()));
  form.addEventListener("keydown", (e) => e.key === "Escape" && closeForm());

  load();
})();
