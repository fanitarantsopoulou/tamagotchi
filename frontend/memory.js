// ---------- MEMORY.EXE: what the pet remembers about you ----------
// Short personal facts (who you are, work, colleagues, friends, shows...) stored by the backend
// in data/memory.db. The chat looks them up only when a message needs them; private facts never
// reach it. Reuses el() and play() from app.js.

const Memory = (() => {
  const root = document.getElementById("memory");
  const list = document.getElementById("memory-list");
  const form = document.getElementById("memory-form");
  const fields = {
    category: form.querySelector("[name=category]"),
    subject: form.querySelector("[name=subject]"),
    text: form.querySelector("[name=text]"),
    private: form.querySelector("[name=private]"),
  };
  const submit = form.querySelector("[type=submit]");
  const cancelEdit = document.getElementById("memory-cancel");
  let editingId = null; // the fact being edited in the form, if any

  async function call(path = "", { method = "GET", json } = {}) {
    const res = await fetch("/api/memory" + path, {
      method,
      headers: json ? { "Content-Type": "application/json" } : undefined,
      body: json ? JSON.stringify(json) : undefined,
    });
    if (res.status === 204) return null;
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(typeof data.detail === "string" ? data.detail : "Something went wrong.");
    return data;
  }

  function render({ categories, memories }) {
    if (!fields.category.options.length) {
      categories.forEach((c) => fields.category.append(Object.assign(el("option", "", c.label), { value: c.key })));
    }
    list.replaceChildren();
    if (!memories.length) {
      list.append(el("p", "lib-hint", "Nothing yet. Add facts below, or tell your pet in the chat: \"θυμήσου ότι η Μαρία είναι συνάδελφός μου\"."));
    }
    categories.forEach((c) => {
      const items = memories.filter((m) => m.category === c.key);
      if (!items.length) return;
      list.append(el("h3", "memory-cat", c.label));
      items.forEach((m) => list.append(item(m)));
    });
  }

  function item(m) {
    const row = el("div", "memory-item");
    const text = el("p");
    if (m.subject) text.append(el("b", "", `${m.subject}: `));
    text.append(m.text);
    if (m.private) text.append(el("i", "lib-tag", "PRIVATE"));
    const edit = el("button", "lib-btn", "EDIT");
    edit.type = "button";
    edit.addEventListener("click", () => startEdit(m));
    const del = el("button", "lib-btn danger", "DEL");
    del.type = "button";
    // Two-step delete: the first click asks, the second one deletes.
    del.addEventListener("click", async () => {
      if (!del.classList.contains("confirm")) {
        del.classList.add("confirm");
        del.textContent = "SURE?";
        setTimeout(() => { del.classList.remove("confirm"); del.textContent = "DEL"; }, 3000);
        return;
      }
      await guarded(() => call(`/${m.id}`, { method: "DELETE" }));
    });
    row.append(text, edit, del);
    return row;
  }

  function startEdit(m) {
    play("click");
    editingId = m.id;
    fields.category.value = m.category;
    fields.subject.value = m.subject;
    fields.text.value = m.text;
    fields.private.checked = m.private;
    submit.textContent = "SAVE";
    cancelEdit.hidden = false;
    fields.text.focus();
  }

  function resetForm() {
    editingId = null;
    form.reset();
    submit.textContent = "ADD";
    cancelEdit.hidden = true;
  }

  // Run a change, then reload the list; errors are shown at the top of the list.
  async function guarded(action) {
    try {
      await action();
      play("confirm");
      render(await call());
      return true;
    } catch (e) {
      list.prepend(el("div", "lib-error", e.message));
      play("error");
      return false;
    }
  }

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const payload = {
      category: fields.category.value,
      subject: fields.subject.value,
      text: fields.text.value,
      private: fields.private.checked,
    };
    const ok = await guarded(() => (editingId ? call(`/${editingId}`, { method: "PATCH", json: payload }) : call("", { method: "POST", json: payload })));
    if (ok) resetForm();
  });
  cancelEdit.addEventListener("click", resetForm);

  async function open() {
    [closeChat, closeOutfits, closeMirror, closeWeather, closeCalendar, closeWizard, closeNotifs, closeLibrary].forEach((close) => close());
    showWindow(root);
    resetForm();
    try {
      render(await call());
    } catch (e) {
      list.replaceChildren(el("div", "wx-error", e.message));
    }
  }

  function close() {
    hideWindow(root);
  }

  document.getElementById("memory-close").addEventListener("click", close);
  return { open, close };
})();

function openMemory() {
  return Memory.open();
}

function closeMemory() {
  Memory.close();
}
