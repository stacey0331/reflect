// =============================================================================
// app.js: page behavior for every page. Each HTML file sets
// <body data-page="..."> and the matching init function below runs.
// Anything that needs the backend goes through api.js.
// =============================================================================

import * as api from "./api.js";

// ---- Small helpers -----------------------------------------------------------

/** Create an element: h("p", { class: "x", text: "hi" }, [children]) */
function h(tag, attrs = {}, children = []) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs)) {
    if (key === "text") node.textContent = value;
    else if (key === "class") node.className = value;
    else node.setAttribute(key, value);
  }
  for (const child of children) node.append(child);
  return node;
}

const sparkle = () => h("span", { class: "sparkle", "aria-hidden": "true" });
const heart = () => h("span", { class: "heart", "aria-hidden": "true" });

const format = {
  // "Saturday, September 19"
  dayLong: (iso) =>
    new Date(iso).toLocaleDateString(undefined, {
      weekday: "long",
      month: "long",
      day: "numeric",
    }),
  // "Saturday, September 19", plus the year only if it isn't the current year:
  // "Friday, December 12, 2025"
  dayAuto: (iso) =>
    new Date(iso).toLocaleDateString(undefined, {
      weekday: "long",
      ...(isThisYear(iso) ? {} : { year: "numeric" }),
      month: "long",
      day: "numeric",
    }),
  time: (iso) =>
    new Date(iso).toLocaleTimeString(undefined, {
      hour: "numeric",
      minute: "2-digit",
    }),
  // "Friday, Dec 12, 2025"
  shortDayWithYear: (iso) =>
    new Date(iso).toLocaleDateString(undefined, {
      weekday: "long",
      month: "short",
      day: "numeric",
      year: "numeric",
    }),
  month: (iso) =>
    new Date(iso).toLocaleDateString(undefined, { month: "short" }),
  dayNumber: (iso) => new Date(iso).getDate(),
  weekday: (iso) =>
    new Date(iso).toLocaleDateString(undefined, { weekday: "long" }),
};

const isThisYear = (iso) => new Date(iso).getFullYear() === new Date().getFullYear();

const wordCount = (text) => (text.trim() ? text.trim().split(/\s+/).length : 0);

function preview(text, max = 160) {
  const flat = text.replace(/\s+/g, " ").trim();
  return flat.length > max ? flat.slice(0, max).trimEnd() + "…" : flat;
}

// ---- Shared sidebar / navigation ---------------------------------------------
// Rendered here so the nav lives in one place instead of being copied into
// every HTML file. On phones, CSS turns the nav into a bottom tab bar.

const NAV_LINKS = [
  { href: "index.html", label: "Journal", section: "journal" },
  { href: "insights.html", label: "Insights", section: "insights" },
  { href: "settings.html", label: "Settings", section: "settings" },
];

function renderSidebar(section) {
  const sidebar = document.getElementById("sidebar");
  if (!sidebar) return;

  const brand = h("a", { class: "brand", href: "index.html" }, [
    heart(),
    document.createTextNode("reflect"),
  ]);

  const nav = h("nav", { class: "nav", "aria-label": "Main" });
  for (const link of NAV_LINKS) {
    const a = h("a", { href: link.href });
    if (link.section === section) {
      a.setAttribute("aria-current", "page");
      a.append(heart());
    }
    a.append(document.createTextNode(link.label));
    nav.append(a);
  }

  sidebar.append(brand, nav);

  // Honest reminder while the backend doesn't exist yet
  if (api.USE_MOCK) {
    sidebar.append(
      h("p", {
        class: "sidebar-note",
        text: "Demo mode. Entries are saved in this browser only.",
      })
    );
  }
}

// ---- Journal page (index.html) ----------------------------------------------

function initJournalPage() {
  const dayEl = document.getElementById("date-day");
  const timeEl = document.getElementById("date-time");
  const textarea = document.getElementById("entry-text");
  const saveBtn = document.getElementById("save-btn");
  const countEl = document.getElementById("word-count");
  const statusEl = document.getElementById("save-status");
  const listEl = document.getElementById("entry-list");
  const moreRow = document.getElementById("more-row");
  const moreBtn = document.getElementById("more-btn");

  const RECENT_COUNT = 5;
  let allEntries = [];
  let showAll = false;

  // Live date / time indicator
  function tick() {
    const now = new Date().toISOString();
    dayEl.textContent = format.dayLong(now);
    timeEl.textContent = format.time(now);
  }
  tick();
  setInterval(tick, 30 * 1000);

  function showStatus(message, isError = false) {
    statusEl.textContent = message;
    statusEl.classList.toggle("error", isError);
  }

  function updateComposer() {
    const words = wordCount(textarea.value);
    countEl.textContent = `${words} ${words === 1 ? "word" : "words"}`;
    saveBtn.disabled = textarea.value.trim() === "";
  }
  textarea.addEventListener("input", updateComposer);
  updateComposer();

  // Save Entry -> POST /api/journal  (see api.createEntry)
  saveBtn.addEventListener("click", async () => {
    const content = textarea.value.trim();
    if (!content) return;

    saveBtn.disabled = true;
    showStatus("Saving entry…");
    try {
      const newEntry = await api.createEntry({ content });
      textarea.value = "";
      allEntries = [newEntry, ...allEntries];
      showAll = false;
      renderList();
      showStatus("Entry saved");
    } catch (error) {
      console.error(error);
      showStatus("Couldn't save the entry. Check that the backend is running, then try again.", true);
    } finally {
      updateComposer();
      saveBtn.disabled = false;
    }
  });

  // Recent entries -> GET /api/journal (see api.listEntries)
  async function loadEntries() {
    try {
      // The backend returns everything, newest first. The UI shows the latest 5
      // and lets you expand to the full list, so there's no separate History page.
      // TODO(backend): if the list gets long, add pagination (e.g. ?limit= and
      // ?offset=) to GET /api/journal instead of fetching everything.
      allEntries = (await api.listEntries()).sort((a, b) => new Date(b.created_at) - new Date(a.created_at));
      renderList();
    } catch (error) {
      console.error(error);
      listEl.replaceChildren(
        h("li", {
          class: "empty error",
          text: "Couldn't load your entries. Check that the backend is running, or set USE_MOCK = true in js/api.js.",
        })
      );
      moreRow.hidden = true;
    }
  }

  function renderList() {
    listEl.replaceChildren();

    if (allEntries.length === 0) {
      listEl.append(
        h("li", { class: "empty", text: "No entries yet. Write your first one above and it will show up here." })
      );
      moreRow.hidden = true;
      return;
    }

    const visible = showAll ? allEntries : allEntries.slice(0, RECENT_COUNT);
    for (const entry of visible) listEl.append(entryCard(entry));

    moreRow.hidden = allEntries.length <= RECENT_COUNT;
    moreBtn.textContent = showAll
      ? "Show fewer entries"
      : `Show all ${allEntries.length} entries`;
  }

  moreBtn.addEventListener("click", () => {
    showAll = !showAll;
    renderList();
  });

  loadEntries();
}

function entryCard(entry) {
  const sticker = h("div", { class: "date-sticker", "aria-hidden": "true" }, [
    h("span", { class: "month", text: format.month(entry.created_at) }),
    h("span", { class: "day", text: String(format.dayNumber(entry.created_at)) }),
  ]);

  const body = h("div", {}, [
    h("p", {
      class: "meta",
      // Same year: "Friday, 9:40 PM". Other years add the full date: "Friday, Dec 12, 2025, 9:40 PM"
      text: isThisYear(entry.created_at)
        ? `${format.weekday(entry.created_at)}, ${format.time(entry.created_at)}`
        : `${format.shortDayWithYear(entry.created_at)}, ${format.time(entry.created_at)}`,
    }),
    h("p", { class: "preview", text: preview(entry.content) }),
  ]);

  const link = h("a", {
    class: "pixel-box entry-card",
    href: `journal.html?id=${encodeURIComponent(entry.id)}`,
  }, [sticker, body]);

  return h("li", {}, [link]);
}

// ---- Entry page (journal.html?id=...) ---------------------------------------

async function initEntryPage() {
  const id = new URLSearchParams(window.location.search).get("id");

  const article = document.getElementById("entry");
  const notFound = document.getElementById("entry-missing");
  const dayEl = document.getElementById("entry-day");
  const timeEl = document.getElementById("entry-time");
  const bodyEl = document.getElementById("entry-body");
  const editor = document.getElementById("entry-editor");
  const viewActions = document.getElementById("view-actions");
  const editActions = document.getElementById("edit-actions");
  const statusEl = document.getElementById("entry-status");

  const editBtn = document.getElementById("edit-btn");
  const deleteBtn = document.getElementById("delete-btn");
  const saveBtn = document.getElementById("save-changes-btn");
  const cancelBtn = document.getElementById("cancel-btn");

  let entry = null;

  function showMissing(message) {
    article.hidden = true;
    notFound.hidden = false;
    notFound.textContent = message;
  }

  function render() {
    dayEl.textContent = format.dayAuto(entry.created_at);
    timeEl.textContent = entry.updated_at
      ? `${format.time(entry.created_at)}, edited ${format.time(entry.updated_at)}`
      : format.time(entry.created_at);
    bodyEl.textContent = entry.content;
  }

  function setEditing(isEditing) {
    bodyEl.hidden = isEditing;
    editor.hidden = !isEditing;
    viewActions.hidden = isEditing;
    editActions.hidden = !isEditing;
    statusEl.textContent = "";
    statusEl.classList.remove("error");
    if (isEditing) {
      editor.value = entry.content;
      editor.focus();
    }
  }

  if (!id) {
    showMissing("No entry selected. Head back to the journal and pick one.");
    return;
  }

  // GET /api/journal/{id}
  try {
    entry = await api.getEntry(id);
  } catch (error) {
    console.error(error);
    showMissing("Couldn't find that entry. It may have been deleted, or the backend isn't reachable.");
    return;
  }
  article.hidden = false;
  render();

  editBtn.addEventListener("click", () => setEditing(true));
  cancelBtn.addEventListener("click", () => setEditing(false));

  // Save changes -> PUT /api/journal/{id}
  saveBtn.addEventListener("click", async () => {
    const content = editor.value.trim();
    if (!content) {
      statusEl.textContent = "An entry can't be empty. Delete it instead if you don't want to keep it.";
      statusEl.classList.add("error");
      return;
    }
    saveBtn.disabled = true;
    try {
      entry = await api.updateEntry(id, { content });
      render();
      setEditing(false);
      statusEl.textContent = "Changes saved";
    } catch (error) {
      console.error(error);
      statusEl.textContent = "Couldn't save your changes. Check the backend connection and try again.";
      statusEl.classList.add("error");
    } finally {
      saveBtn.disabled = false;
    }
  });

  // Delete -> DELETE /api/journal/{id}
  deleteBtn.addEventListener("click", async () => {
    if (!window.confirm("Delete this entry? This can't be undone.")) return;
    deleteBtn.disabled = true;
    try {
      await api.deleteEntry(id);
      window.location.href = "index.html";
    } catch (error) {
      console.error(error);
      statusEl.textContent = "Couldn't delete the entry. Check the backend connection and try again.";
      statusEl.classList.add("error");
      deleteBtn.disabled = false;
    }
  });
}

// ---- Insights page (insights.html) ------------------------------------------
// Renders PLACEHOLDER data from api.getInsights(). See mock-data.js.

async function initInsightsPage() {
  const insights = await api.getInsights();

  const weekLabelEl = document.getElementById("week-label");
  const labelText = insights.dateRange
    ? `${insights.weekLabel} · ${insights.dateRange}`
    : insights.weekLabel;
  weekLabelEl.textContent = labelText;
  document.getElementById("weekly-reflection").textContent = insights.weeklyReflection;

  // Time allocation: 20-block pixel bars, scaled to the biggest category
  const SEGMENTS = 20;
  const barsEl = document.getElementById("time-bars");
  const maxHours = Math.max(...(insights.timeAllocation || []).map((t) => t.hours));
  for (const item of insights.timeAllocation || []) {
    const filled = Math.max(1, Math.round((item.hours / maxHours) * SEGMENTS));
    const segments = h("div", { class: "segments", "aria-hidden": "true" });
    for (let i = 0; i < SEGMENTS; i++) {
      segments.append(h("i", { class: i < filled ? `on tone-${item.tone}` : "" }));
    }
    barsEl.append(
      h("div", { class: "bar-row" }, [
        h("div", { class: "bar-label" }, [
          h("span", { text: item.label }),
          h("span", { text: `${item.hours} hrs` }),
        ]),
        segments,
      ])
    );
  }

  // Recurring themes: bigger text for themes that appear more often
  const cloudEl = document.getElementById("theme-cloud");
  const themes = insights.themes || [];
  const maxCount = themes.length ? Math.max(...themes.map((t) => t.count)) : 1;
  const tones = ["lilac", "sky", "lilac", "sky", "pink"]; // pink is a small accent
  themes.forEach((theme, i) => {
    const chip = h("span", { class: `theme-chip tone-${tones[i % tones.length]}` }, [
      document.createTextNode(theme.label),
      h("small", { text: String(theme.count) }),
    ]);
    chip.style.fontSize = `${(0.8125 + (theme.count / maxCount) * 0.3).toFixed(2)}rem`;
    cloudEl.append(chip);
  });

  // Recent concerns
  const concernsEl = document.getElementById("concerns");
  for (const concern of insights.concerns || []) {
    concernsEl.append(
      h("li", {}, [
        sparkle(),
        h("div", {}, [
          document.createTextNode(concern.text),
          h("span", { class: "note", text: concern.note }),
        ]),
      ])
    );
  }

  // Patterns
  const patternsEl = document.getElementById("patterns");
  for (const pattern of insights.patterns || []) {
    patternsEl.append(h("li", {}, [sparkle(), h("div", { text: pattern })]));
  }
}

// ---- Boot --------------------------------------------------------------------

const page = document.body.dataset.page;
renderSidebar(document.body.dataset.section || page);

if (page === "journal") initJournalPage();
if (page === "entry") initEntryPage();
if (page === "insights") initInsightsPage();
// History and Settings are static placeholders and need no script logic yet.
