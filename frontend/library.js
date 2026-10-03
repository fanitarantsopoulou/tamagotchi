// ---------- LIBRARY.EXE: a bookshelf that is really a personal knowledge base ----------
// Books (topics) -> chapters (sub-topics) -> notes (Markdown). Everything is stored by the
// backend in SQLite (see backend/library/); this file only draws the shelf and talks to
// /api/library. It reuses el(), play() and the window helpers from app.js.

const Library = (() => {
  const root = document.getElementById("library");
  const body = document.getElementById("lib-body");
  const dialogEl = document.getElementById("lib-dialog");
  const searchForm = document.getElementById("lib-search");
  const searchInput = searchForm.querySelector("input");
  const importInput = document.getElementById("lib-import");
  const PALETTE_SIZE = 8; // matches --book-0 ... --book-7 in style.css and PALETTE_SIZE in store.py
  const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");

  // What's on screen: the shelf, search results, or an open book (with a chapter / note / editor).
  const view = { mode: "shelf", book: null, chapterId: null, note: null, editing: null, query: "" };

  // ---------- API ----------
  async function call(path, { method = "GET", json, form } = {}) {
    const res = await fetch("/api/library" + path, {
      method,
      headers: json ? { "Content-Type": "application/json" } : undefined,
      body: json ? JSON.stringify(json) : form,
    });
    if (res.status === 204) return null;
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(typeof data.detail === "string" ? data.detail : "Something went wrong.");
    return data;
  }

  // ---------- Markdown (rendered locally, sanitized, code blocks highlighted) ----------
  marked.setOptions({ gfm: true, breaks: true });

  function renderMarkdown(target, markdown) {
    target.innerHTML = DOMPurify.sanitize(marked.parse(markdown || ""));
    target.querySelectorAll("pre code").forEach((code) => hljs.highlightElement(code));
    target.querySelectorAll("a").forEach((a) => {
      a.target = "_blank";
      a.rel = "noopener noreferrer";
    });
  }

  // ---------- small UI helpers ----------
  function button(label, onClick, className = "") {
    const b = el("button", `lib-btn ${className}`.trim(), label);
    b.type = "button";
    b.addEventListener("click", (e) => {
      e.stopPropagation();
      play("click");
      onClick(e);
    });
    return b;
  }

  function formatDate(iso) {
    return new Date(iso).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" });
  }

  function showError(message) {
    const bar = el("div", "lib-error", message);
    body.prepend(bar);
    play("error");
    setTimeout(() => bar.remove(), 4000);
  }

  // Wrap an action so a failure shows a message instead of breaking the window.
  const safely = (fn) => async (...args) => {
    try {
      return await fn(...args);
    } catch (e) {
      showError(e.message);
    }
  };

  // Stable pseudo-random spine height per book, so the shelf looks hand-arranged but never reshuffles.
  function spineHeight(id) {
    const h = (id * 2654435761) % 2 ** 32;
    return 96 + (h % 5) * 8;
  }

  // ---------- dialogs (in-window, never the browser's alert/confirm) ----------
  // fields: [{ name, label, type: "text" | "checkbox" | "select" | "colors" | "textarea", value, options, list }]
  // `list` (for text fields) returns datalist suggestions and is re-evaluated as the user types.
  function dialog({ title, text, fields = [], ok = "OK", danger = false }) {
    return new Promise((resolve) => {
      const form = el("form", "lib-dialog-box");
      form.append(el("h3", "", title));
      if (text) form.append(el("p", "", text));
      const inputs = {};
      const lists = [];

      fields.forEach((f, i) => {
        const row = el("label", `lib-field lib-field-${f.type || "text"}`);
        if (f.type === "checkbox") {
          const input = el("input");
          input.type = "checkbox";
          input.checked = !!f.value;
          row.append(input, el("span", "", f.label));
          inputs[f.name] = input;
        } else if (f.type === "colors") {
          row.append(el("span", "", f.label));
          const swatches = el("div", "lib-swatches");
          for (let c = 0; c < PALETTE_SIZE; c++) {
            const s = el("input");
            s.type = "radio";
            s.name = f.name;
            s.value = c;
            s.checked = c === (f.value ?? 0);
            s.style.setProperty("--book", `var(--book-${c})`);
            s.setAttribute("aria-label", `Color ${c + 1}`);
            swatches.append(s);
          }
          row.append(swatches);
          inputs[f.name] = { get value() { return Number(swatches.querySelector(":checked")?.value ?? 0); } };
        } else {
          row.append(el("span", "", f.label));
          let input;
          if (f.type === "select") {
            input = el("select");
            f.options.forEach((o) => {
              const opt = el("option", "", o.label);
              opt.value = o.value;
              opt.selected = String(o.value) === String(f.value);
              input.append(opt);
            });
          } else {
            input = el(f.type === "textarea" ? "textarea" : "input");
            input.value = f.value ?? "";
            input.maxLength = f.maxLength || 120;
            if (f.list) {
              const datalist = el("datalist");
              datalist.id = `lib-list-${i}`;
              input.setAttribute("list", datalist.id);
              row.append(datalist);
              lists.push({ datalist, fn: f.list });
            }
          }
          input.required = !!f.required;
          row.append(input);
          inputs[f.name] = input;
        }
        form.append(row);
      });

      const values = () =>
        Object.fromEntries(Object.entries(inputs).map(([k, input]) => [k, input.type === "checkbox" ? input.checked : input.value]));
      const refreshLists = () =>
        lists.forEach(({ datalist, fn }) => datalist.replaceChildren(...fn(values()).map((v) => Object.assign(el("option"), { value: v }))));
      form.addEventListener("input", refreshLists);
      refreshLists();

      const actions = el("div", "lib-dialog-actions");
      const cancel = button("CANCEL", () => finish(null));
      const okBtn = el("button", `lib-btn primary ${danger ? "danger" : ""}`, ok);
      okBtn.type = "submit";
      actions.append(cancel, okBtn);
      form.append(actions);

      function finish(result) {
        dialogEl.hidden = true;
        dialogEl.replaceChildren();
        resolve(result);
      }
      form.addEventListener("submit", (e) => {
        e.preventDefault();
        finish(values());
      });
      form.addEventListener("keydown", (e) => {
        if (e.key === "Escape") {
          e.stopPropagation();
          finish(null);
        }
      });

      dialogEl.replaceChildren(form);
      dialogEl.hidden = false;
      (form.querySelector("input:not([type=radio]):not([type=checkbox]), select, textarea") || okBtn).focus();
    });
  }

  const confirmDelete = (what, detail) =>
    dialog({ title: `Delete ${what}?`, text: `${detail} This can't be undone.`, ok: "DELETE", danger: true });

  // ---------- the shelf ----------
  async function showShelf() {
    Object.assign(view, { mode: "shelf", book: null, chapterId: null, note: null, editing: null });
    const { books } = await call("");
    const shelf = el("div", "shelf");
    books.forEach((book) => shelf.append(spineFor(book)));

    const add = el("button", "book-spine book-new", "+");
    add.type = "button";
    add.title = "New book";
    add.addEventListener("click", () => newBook());
    shelf.append(slot(add));

    body.replaceChildren(shelf);
    if (!books.length) {
      body.prepend(el("p", "lib-empty", "Your shelf is empty. Add a book for each big topic, e.g. Programming, Work, Personal projects."));
    }
  }

  function slot(content) {
    const s = el("div", "book-slot");
    s.append(content);
    return s;
  }

  function spineFor(book) {
    const spine = el("button", "book-spine");
    spine.type = "button";
    spine.style.setProperty("--book", `var(--book-${book.color})`);
    spine.style.height = `${spineHeight(book.id)}px`;
    // thicker books hold more notes
    spine.style.width = `${30 + Math.min(book.note_count, 24) * 1.5}px`;
    spine.title = `${book.title} · ${book.chapter_count} chapters · ${book.note_count} notes${book.private ? " · private" : ""}`;
    spine.append(el("span", "spine-band"), el("span", "spine-title", book.title));
    if (book.private) spine.append(el("span", "spine-lock", "PRIV"));
    spine.addEventListener("click", () => {
      play("click");
      openBook(book.id, { from: spine });
    });
    return slot(spine);
  }

  // The spine flies to the middle and its cover swings open, then the book's pages appear.
  async function playOpenAnimation(from, color) {
    if (!from || reducedMotion.matches) return;
    const start = from.getBoundingClientRect();
    const end = body.getBoundingClientRect();
    const ghost = el("div", "book-ghost");
    ghost.style.setProperty("--book", color);
    Object.assign(ghost.style, { left: `${end.left}px`, top: `${end.top}px`, width: `${end.width}px`, height: `${end.height}px` });
    ghost.append(el("div", "book-ghost-cover"));
    document.body.append(ghost);

    const dx = start.left - end.left, dy = start.top - end.top;
    const sx = start.width / end.width, sy = start.height / end.height;
    await ghost.animate(
      [{ transform: `translate(${dx}px, ${dy}px) scale(${sx}, ${sy})` }, { transform: "none" }],
      { duration: 320, easing: "cubic-bezier(.2,.7,.3,1)" }
    ).finished;
    ghost.classList.add("opening");
    await sleep(380);
    ghost.remove();
  }

  // ---------- an open book ----------
  async function openBook(bookId, { from, chapterId, noteId } = {}) {
    const [book] = await Promise.all([call(`/books/${bookId}`), playOpenAnimation(from, from?.style.getPropertyValue("--book"))]);
    view.mode = "book";
    view.book = book;
    view.chapterId = chapterId ?? view.chapterId ?? book.chapters[0]?.id ?? null;
    if (!book.chapters.some((c) => c.id === view.chapterId)) view.chapterId = book.chapters[0]?.id ?? null;
    view.editing = null;
    view.note = noteId ? await call(`/notes/${noteId}`) : null;
    renderBook();
    if (from) body.querySelector(".lib-book")?.classList.add("just-opened");
  }

  async function reloadBook() {
    view.book = await call(`/books/${view.book.id}`);
    renderBook();
  }

  function currentChapter() {
    return view.book.chapters.find((c) => c.id === view.chapterId) || null;
  }

  function renderBook() {
    const book = view.book;
    const wrap = el("div", "lib-book");
    wrap.style.setProperty("--book", `var(--book-${book.color})`);
    // On narrow screens only one page fits: the table of contents, or the open chapter/note.
    if (view.note || view.editing || view.chapterId) wrap.classList.add("show-page");

    const head = el("div", "lib-book-head");
    head.append(
      button("◀ SHELF", safely(showShelf)),
      el("h2", "", book.title + (book.private ? " · PRIVATE" : "")),
      button("EDIT", safely(editBook)),
      button("DELETE", safely(deleteBook), "danger")
    );

    const toc = el("nav", "lib-page lib-toc");
    toc.append(el("h3", "", "Chapters"));
    if (!book.chapters.length) toc.append(el("p", "lib-hint", "No chapters yet. A chapter is a sub-topic, e.g. Python or Docker."));
    book.chapters.forEach((ch) => {
      const item = el("button", "lib-toc-item" + (ch.id === view.chapterId ? " current" : ""));
      item.type = "button";
      item.append(el("span", "", ch.title), el("small", "", (ch.private ? "PRIV · " : "") + ch.notes.length));
      item.addEventListener("click", () => {
        play("click");
        Object.assign(view, { chapterId: ch.id, note: null, editing: null });
        renderBook();
      });
      toc.append(item);
    });
    toc.append(button("+ CHAPTER", safely(newChapter)));

    const page = el("section", "lib-page lib-content");
    if (view.editing) renderEditor(page);
    else if (view.note) renderNote(page);
    else renderChapter(page);

    const pages = el("div", "lib-pages");
    pages.append(toc, page);
    wrap.append(head, pages);
    body.replaceChildren(wrap);
  }

  function renderChapter(page) {
    const ch = currentChapter();
    if (!ch) {
      page.append(el("p", "lib-hint", "Pick or add a chapter to start writing notes."));
      return;
    }
    const head = el("div", "lib-page-head");
    head.append(
      button("◀", () => { view.chapterId = null; renderBook(); }, "lib-back"),
      el("h3", "", ch.title + (ch.private ? " · PRIVATE" : "")),
      button("EDIT", safely(() => editChapter(ch))),
      button("DELETE", safely(() => deleteChapter(ch)), "danger")
    );
    page.append(head);
    if (!ch.notes.length) page.append(el("p", "lib-hint", "No notes here yet."));
    ch.notes.forEach((n) => page.append(noteCard(n)));
    page.append(button("+ NOTE", () => { view.editing = { chapterId: ch.id }; renderBook(); }, "primary"));
  }

  function noteCard(n, place) {
    const card = el("button", "lib-note-card");
    card.type = "button";
    card.append(el("b", "", n.title));
    if (place) card.append(el("small", "lib-place", place));
    card.append(el("span", "", n.excerpt || "(empty)"));
    const meta = el("small", "lib-meta", formatDate(n.updated_at));
    n.tags.forEach((t) => meta.append(el("i", "lib-tag", t)));
    card.append(meta);
    card.addEventListener("click", safely(async () => {
      play("click");
      if (place) return openBook(n.book_id, { chapterId: n.chapter_id, noteId: n.id });
      view.note = await call(`/notes/${n.id}`);
      renderBook();
    }));
    return card;
  }

  function renderNote(page) {
    const n = view.note;
    const head = el("div", "lib-page-head");
    head.append(
      button("◀", () => { view.note = null; renderBook(); }, "lib-back"),
      el("h3", "", n.title),
      button("EDIT", () => { view.editing = { note: n }; renderBook(); }),
      button("MOVE", safely(moveNote)),
      button("DELETE", safely(deleteNote), "danger")
    );
    const meta = el("p", "lib-meta", `${n.book} › ${n.chapter} · created ${formatDate(n.created_at)} · edited ${formatDate(n.updated_at)}`);
    n.tags.forEach((t) => meta.append(el("i", "lib-tag", t)));
    const text = el("article", "lib-markdown");
    renderMarkdown(text, n.body);
    page.append(head, meta, text);
  }

  // Write / preview editor for a new or existing note.
  function renderEditor(page) {
    const { note, chapterId, draft } = view.editing;
    const form = el("form", "lib-editor");
    const title = Object.assign(el("input"), { value: draft?.title ?? note?.title ?? "", placeholder: "Title", maxLength: 120, required: true });
    const tags = Object.assign(el("input"), { value: (draft?.tags ?? note?.tags ?? []).join(", "), placeholder: "tags, comma separated (optional)" });
    const text = Object.assign(el("textarea"), { value: draft?.body ?? note?.body ?? "", placeholder: "Write in Markdown. Code blocks: ```python ... ```" });
    const preview = el("article", "lib-markdown lib-preview");
    preview.hidden = true;

    const tabs = el("div", "lib-tabs");
    const write = button("WRITE", () => toggle(false), "on");
    const show = button("PREVIEW", () => toggle(true));
    function toggle(previewing) {
      if (previewing) renderMarkdown(preview, text.value);
      preview.hidden = !previewing;
      text.hidden = previewing;
      write.classList.toggle("on", !previewing);
      show.classList.toggle("on", previewing);
    }
    tabs.append(write, show);

    const actions = el("div", "lib-dialog-actions");
    const save = el("button", "lib-btn primary", "SAVE");
    save.type = "submit";
    actions.append(button("CANCEL", () => { view.editing = null; renderBook(); }), save);

    form.append(title, tags, tabs, text, preview, actions);
    form.addEventListener("submit", safely(async (e) => {
      e.preventDefault();
      const payload = { title: title.value, body: text.value, tags: tags.value.split(",").map((t) => t.trim()).filter(Boolean) };
      save.disabled = true;
      try {
        view.note = note
          ? await call(`/notes/${note.id}`, { method: "PATCH", json: payload })
          : await call(`/chapters/${chapterId}/notes`, { method: "POST", json: payload });
        play("confirm");
        view.editing = null;
        await reloadBook();
      } finally {
        save.disabled = false;
      }
    }));
    page.append(form);
    title.focus();
  }

  // ---------- create / edit / delete ----------
  async function newBook() {
    const v = await dialog({
      title: "New book",
      fields: [
        { name: "title", label: "Topic", required: true },
        { name: "color", label: "Color", type: "colors", value: Math.floor(Math.random() * PALETTE_SIZE) },
        { name: "private", label: "Private (the chat can never see it)", type: "checkbox" },
      ],
      ok: "ADD",
    });
    if (!v) return;
    try {
      const book = await call("/books", { method: "POST", json: v });
      play("confirm");
      await showShelf();
      openBook(book.id);
    } catch (e) {
      showError(e.message);
    }
  }

  async function editBook() {
    const b = view.book;
    const v = await dialog({
      title: "Edit book",
      fields: [
        { name: "title", label: "Topic", value: b.title, required: true },
        { name: "color", label: "Color", type: "colors", value: b.color },
        { name: "private", label: "Private (the chat can never see it)", type: "checkbox", value: b.private },
      ],
      ok: "SAVE",
    });
    if (!v) return;
    view.book = await call(`/books/${b.id}`, { method: "PATCH", json: v });
    renderBook();
  }

  async function deleteBook() {
    const b = view.book;
    const notes = b.chapters.reduce((sum, c) => sum + c.notes.length, 0);
    if (!(await confirmDelete(`«${b.title}»`, `The book, its ${b.chapters.length} chapters and ${notes} notes will be deleted.`))) return;
    await call(`/books/${b.id}`, { method: "DELETE" });
    play("confirm");
    await showShelf();
  }

  async function newChapter() {
    const v = await dialog({
      title: `New chapter in «${view.book.title}»`,
      fields: [
        { name: "title", label: "Sub-topic", required: true },
        { name: "private", label: "Private (the chat can never see it)", type: "checkbox" },
      ],
      ok: "ADD",
    });
    if (!v) return;
    const ch = await call(`/books/${view.book.id}/chapters`, { method: "POST", json: v });
    view.chapterId = ch.id;
    view.note = null;
    await reloadBook();
  }

  async function editChapter(ch) {
    const v = await dialog({
      title: "Edit chapter",
      fields: [
        { name: "title", label: "Sub-topic", value: ch.title, required: true },
        { name: "private", label: "Private (the chat can never see it)", type: "checkbox", value: ch.private },
      ],
      ok: "SAVE",
    });
    if (!v) return;
    await call(`/chapters/${ch.id}`, { method: "PATCH", json: v });
    await reloadBook();
  }

  async function deleteChapter(ch) {
    if (!(await confirmDelete(`«${ch.title}»`, `The chapter and its ${ch.notes.length} notes will be deleted.`))) return;
    await call(`/chapters/${ch.id}`, { method: "DELETE" });
    view.chapterId = null;
    await reloadBook();
  }

  async function moveNote() {
    const n = view.note;
    const { books } = await call("/places");
    const options = books.flatMap((b) => b.chapters.map((c) => ({ value: c.id, label: `${b.title} › ${c.title}` })));
    const v = await dialog({
      title: `Move «${n.title}»`,
      fields: [{ name: "chapter_id", label: "To", type: "select", options, value: n.chapter_id }],
      ok: "MOVE",
    });
    if (!v || Number(v.chapter_id) === n.chapter_id) return;
    const moved = await call(`/notes/${n.id}`, { method: "PATCH", json: { chapter_id: Number(v.chapter_id) } });
    play("confirm");
    await openBook(moved.book_id, { chapterId: moved.chapter_id, noteId: moved.id });
  }

  async function deleteNote() {
    const n = view.note;
    if (!(await confirmDelete(`«${n.title}»`, "This note will be deleted."))) return;
    await call(`/notes/${n.id}`, { method: "DELETE" });
    view.note = null;
    await reloadBook();
  }

  // ---------- search (works on its own, without the chat) ----------
  async function runSearch(query) {
    view.mode = "results";
    view.query = query;
    const { results } = await call("/search", { method: "POST", json: { query } });
    const list = el("div", "lib-results");
    const head = el("div", "lib-page-head");
    head.append(button("◀ SHELF", safely(showShelf)), el("h3", "", `${results.length} result${results.length === 1 ? "" : "s"} for «${query}»`));
    list.append(head);
    if (!results.length) list.append(el("p", "lib-hint", "Nothing found. Try fewer or shorter words."));
    results.forEach((r) => list.append(noteCard(r, `${r.book} › ${r.chapter}${r.book_private || r.chapter_private ? " · PRIVATE" : ""}`)));
    body.replaceChildren(list);
  }

  searchForm.addEventListener("submit", safely(async (e) => {
    e.preventDefault();
    const q = searchInput.value.trim();
    if (q) await runSearch(q);
    else await showShelf();
  }));

  // ---------- importing files ----------
  // The backend reads the file and suggests a place by comparing it with existing notes
  // (locally: the file never goes to the AI). The user confirms or changes the place.
  async function readFile(file) {
    const form = new FormData();
    form.append("file", file);
    return call("/import", { method: "POST", form });
  }

  // Book/chapter suggestions for the "where to save" fields.
  async function placePicker() {
    const { books } = await call("/places");
    return {
      books: books.map((b) => b.title),
      chaptersOf: (bookTitle) => books.find((b) => b.title.toLowerCase() === (bookTitle || "").trim().toLowerCase())?.chapters.map((c) => c.title) || [],
    };
  }

  async function saveImported(imported, { title, book, chapter }) {
    return call("/save", { method: "POST", json: { title, body: imported.body, tags: [], book, chapter } });
  }

  importInput.addEventListener("change", () => {
    const file = importInput.files[0];
    importInput.value = "";
    if (file) importFile(file);
  });

  const importFile = safely(async (file) => {
    const imported = await readFile(file);
    const picker = await placePicker();
    const s = imported.suggestion;
    const v = await dialog({
      title: `Add «${file.name}»`,
      text: s ? `Suggested place: ${s.book} › ${s.chapter}. Change it if you like (new names create a new book or chapter).`
              : "Where should it go? New names create a new book or chapter.",
      fields: [
        { name: "title", label: "Note title", value: imported.title, required: true },
        { name: "book", label: "Book", value: s?.book ?? view.book?.title ?? "", required: true, list: () => picker.books },
        { name: "chapter", label: "Chapter", value: s?.chapter ?? currentChapterTitle(), required: true, list: (vals) => picker.chaptersOf(vals.book) },
      ],
      ok: "SAVE",
    });
    if (!v) return;
    const note = await saveImported(imported, v);
    play("confirm");
    await openBook(note.book_id, { chapterId: note.chapter_id, noteId: note.id });
  });

  // Files can also be dragged from Finder and dropped onto the library or the chat window.
  function acceptDrops(target, onFile) {
    target.addEventListener("dragover", (e) => {
      if (!e.dataTransfer.types.includes("Files")) return;
      e.preventDefault(); // without this the browser would open the file itself
      target.classList.add("drop-target");
    });
    target.addEventListener("dragleave", (e) => {
      if (!target.contains(e.relatedTarget)) target.classList.remove("drop-target");
    });
    target.addEventListener("drop", (e) => {
      if (!e.dataTransfer.files.length) return;
      e.preventDefault();
      target.classList.remove("drop-target");
      onFile(e.dataTransfer.files[0]);
    });
  }
  acceptDrops(root, importFile);
  acceptDrops(document.getElementById("chat"), (file) => attachToChat(file));

  function currentChapterTitle() {
    return view.book ? currentChapter()?.title ?? "" : "";
  }

  // ---------- in the chat: file uploads and note sources ----------
  // A file added in the chat is read by the backend and never sent to the AI. The pet asks where
  // to keep it (with a local suggestion) and saves it once you confirm.
  async function attachToChat(file) {
    const asking = addMessage("pet typing", "📖 ...");
    let imported, picker;
    try {
      [imported, picker] = await Promise.all([readFile(file), placePicker()]);
    } catch (e) {
      asking.remove();
      return addMessage("error", e.message);
    }
    asking.remove();
    const s = imported.suggestion;
    addMessage("pet", s
      ? `Πού να βάλω το «${imported.title}»; Λέω στο ${s.book} › ${s.chapter}. Άλλαξέ το αν θες!`
      : `Πού να βάλω το «${imported.title}»; Γράψε βιβλίο και κεφάλαιο.`);

    const card = el("form", "msg chat-file-card");
    const field = (label, value, list) => {
      const row = el("label", "", label);
      const input = Object.assign(el("input"), { value, required: true, maxLength: 120 });
      const datalist = el("datalist");
      datalist.id = `chat-list-${Math.random().toString(36).slice(2)}`;
      input.setAttribute("list", datalist.id);
      row.append(input, datalist);
      return { row, input, fill: (items) => datalist.replaceChildren(...items.map((v) => Object.assign(el("option"), { value: v }))) };
    };
    const book = field("Book", s?.book ?? "");
    const chapter = field("Chapter", s?.chapter ?? "");
    book.fill(picker.books);
    const refreshChapters = () => chapter.fill(picker.chaptersOf(book.input.value));
    book.input.addEventListener("input", refreshChapters);
    refreshChapters();
    const actions = el("div", "chat-file-actions");
    const save = el("button", "", "SAVE");
    const cancel = el("button", "", "CANCEL");
    cancel.type = "button";
    actions.append(cancel, save);
    card.append(book.row, chapter.row, actions);
    chatLog.append(card);
    chatLog.scrollTop = chatLog.scrollHeight;

    cancel.addEventListener("click", () => {
      card.remove();
      addMessage("note", "OK, δεν το κράτησα.");
    });
    card.addEventListener("submit", async (e) => {
      e.preventDefault();
      save.disabled = true;
      try {
        const note = await saveImported(imported, { title: imported.title, book: book.input.value, chapter: chapter.input.value });
        card.remove();
        showSource({ ...note, note_id: note.id }, "✓ saved:");
        play("confirm");
      } catch (err) {
        save.disabled = false;
        addMessage("error", err.message);
      }
    });
  }

  // ---------- open / close ----------
  async function open() {
    [closeChat, closeOutfits, closeMirror, closeWeather, closeCalendar, closeWizard, closeNotifs].forEach((close) => close());
    root.hidden = false;
    try {
      if (view.mode === "book" && view.book) await openBook(view.book.id);
      else await showShelf();
    } catch (e) {
      body.replaceChildren(el("div", "wx-error", e.message));
    }
  }

  function close() {
    root.hidden = true;
    dialogEl.hidden = true;
  }

  // Jump straight to a note (e.g. from a source link under a chat reply).
  async function openNote(note) {
    await open();
    await safely(openBook)(note.book_id, { chapterId: note.chapter_id, noteId: note.note_id ?? note.id });
  }

  document.getElementById("library-close").addEventListener("click", close);
  document.getElementById("lib-new-book").addEventListener("click", () => { play("click"); newBook(); });

  return { open, close, openNote, attachToChat };
})();

// A link under a chat reply to the library note it was based on.
function showSource(source, label = "📚") {
  const link = addMessage("note source", `${label} ${source.book} › ${source.chapter} · ${source.title}`);
  link.title = "Open in the library";
  link.addEventListener("click", () => Library.openNote(source));
}

document.getElementById("chat-file").addEventListener("change", (e) => {
  const file = e.target.files[0];
  e.target.value = "";
  if (file) Library.attachToChat(file);
});

function openLibrary() {
  return Library.open();
}

function closeLibrary() {
  Library.close();
}
