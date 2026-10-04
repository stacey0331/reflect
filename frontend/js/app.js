// =============================================================================
// app.js: page behavior for every page. Each HTML file sets
// <body data-page="..."> and the matching init function below runs.
// Anything that needs the backend goes through api.js.
// =============================================================================

import * as api from "./api.js";

const API_BASE_URL = "http://localhost:8000";

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

async function fetchAuthStatus() {
  if (api.USE_MOCK) return { authenticated: true };

  const response = await fetch(`${API_BASE_URL}/auth/status`, {
    credentials: "include",
  });
  if (!response.ok) throw new Error(`Auth status failed (${response.status})`);
  return response.json();
}

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

  const authWrap = h("div", { class: "sidebar-auth-wrap" });
  const note = api.USE_MOCK
    ? h("p", {
        class: "sidebar-note",
        text: "Demo mode. Entries are saved in this browser only.",
      })
    : h("p", {
        class: "sidebar-note",
        text: "",
      });

  const loginLink = h(
    "a",
    {
      class: "btn btn-primary sidebar-auth",
      href: `${API_BASE_URL}/login`,
      target: "_self",
      text: "Google login",
    }
  );

  authWrap.append(loginLink);
  sidebar.append(brand, nav, note, authWrap);

  async function hydrateAuthState() {
    try {
      const data = await fetchAuthStatus();
      if (!data.authenticated) return;

      const accountMenu = h("details", { class: "sidebar-account" });
      const profileCard = h("summary", {
        class: "sidebar-profile",
        title: data.name || data.email || "Google account",
      });

      const avatar = h("img", {
        alt: "Google profile picture",
        src: data.picture || "",
        referrerpolicy: "no-referrer",
      });

      const text = h("div", { class: "sidebar-profile-text" }, [
        h("strong", { text: data.name || "Google user" }),
        h("span", { text: data.email || "Connected" }),
      ]);

      profileCard.append(avatar, text);
      accountMenu.append(
        profileCard,
        h("a", {
          class: "sidebar-logout",
          href: `${API_BASE_URL}/logout`,
          text: "Log out",
        })
      );
      authWrap.replaceChildren(accountMenu);
      document.addEventListener("click", (event) => {
        if (!accountMenu.contains(event.target)) accountMenu.open = false;
      });
    } catch (error) {
      console.debug("Auth state unavailable", error);
    }
  }

  hydrateAuthState();
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
  const dateFilterEl = document.getElementById("entry-date-filter");
  const moreRow = document.getElementById("more-row");
  const moreBtn = document.getElementById("more-btn");

  const RECENT_COUNT = 5;
  let allEntries = [];
  let showAll = false;
  let selectedDate = "";
  let authenticated = api.USE_MOCK;

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
    textarea.disabled = !authenticated;
    textarea.placeholder = authenticated
      ? "What happened today?"
      : "Sign in to write a journal entry";
    saveBtn.disabled = !authenticated || textarea.value.trim() === "";
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
      if (error instanceof Error && error.message.includes("401")) {
        authenticated = false;
        updateComposer();
        renderSignInPrompt();
        return;
      }
      const rawMessage = error instanceof Error ? error.message : String(error ?? "");
      const lowerMessage = rawMessage.toLowerCase();
      const isDuplicateDayError = lowerMessage.includes("already exists")
        || lowerMessage.includes("not allowed")
        || lowerMessage.includes("existing one");

      const message = isDuplicateDayError
        ? "This day already has an entry. Edit it instead."
        : "Couldn't save the entry. Check that the backend is running, then try again.";
      showStatus(message, true);
    } finally {
      updateComposer();
    }
  });

  // Recent entries -> GET /api/journal (see api.listEntries)
  async function loadEntries() {
    try {
      const auth = await fetchAuthStatus();
      authenticated = Boolean(auth.authenticated);
      updateComposer();
      if (!authenticated) {
        renderSignInPrompt();
        return;
      }

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
          text: "Your journal couldn't load. Check your connection and try again.",
        })
      );
      moreRow.hidden = true;
    }
  }

  function renderSignInPrompt() {
    const prompt = h("li", { class: "auth-prompt" }, [
      h("div", { class: "auth-prompt-copy" }, [
        h("h3", { text: "Your journal is waiting" }),
        h("p", { text: "Sign in to see your saved entries and write a new one." }),
      ]),
      h("a", {
        class: "btn btn-primary",
        href: `${API_BASE_URL}/login`,
        text: "Sign in",
      }),
    ]);
    listEl.replaceChildren(prompt);
    moreRow.hidden = true;
  }

  function renderList() {
    listEl.replaceChildren();

    const filteredEntries = selectedDate
      ? allEntries.filter((entry) => {
          const entryDate = new Date(entry.date || entry.created_at).toISOString().slice(0, 10);
          return entryDate === selectedDate;
        })
      : allEntries;

    if (filteredEntries.length === 0) {
      const emptyText = selectedDate
        ? `No entries for ${selectedDate}.`
        : "No entries yet. Write your first one above and it will show up here.";
      listEl.append(h("li", { class: "empty", text: emptyText }));
      moreRow.hidden = true;
      return;
    }

    const visible = showAll ? filteredEntries : filteredEntries.slice(0, RECENT_COUNT);
    for (const entry of visible) listEl.append(entryCard(entry));

    moreRow.hidden = filteredEntries.length <= RECENT_COUNT;
    moreBtn.textContent = showAll
      ? "Show fewer entries"
      : `Show all ${filteredEntries.length} entries`;
  }

  moreBtn.addEventListener("click", () => {
    showAll = !showAll;
    renderList();
  });

  dateFilterEl.addEventListener("input", (event) => {
    selectedDate = event.target.value;
    showAll = false;
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
  const insightsGrid = document.querySelector(".insights-grid");
  let auth = null;

  function renderSignInPrompt(title, description) {
    insightsGrid.hidden = true;
    document.querySelector(".lede").textContent = description;

    const prompt = h("section", {
      class: "auth-prompt insights-auth-prompt",
      "aria-labelledby": "insights-signin-heading",
    }, [
      h("div", { class: "auth-prompt-copy" }, [
        h("h2", { id: "insights-signin-heading", text: title }),
        h("p", { text: "Sign in and write a few journal entries. Reflect can then look for recurring themes and patterns across your week, month, and year." }),
      ]),
      h("div", { class: "auth-prompt-actions" }, [
        h("a", {
          class: "btn btn-primary",
          href: `${API_BASE_URL}/login`,
          text: "Log in",
        }),
      ]),
    ]);
    insightsGrid.before(prompt);
  }

  try {
    auth = await fetchAuthStatus();
    if (!auth.authenticated) {
      renderSignInPrompt(
        "Start with a journal entry",
        ""
      );
      return;
    }
  } catch (error) {
    console.error(error);
    renderSignInPrompt(
      "Insights are temporarily unavailable",
      "Reflect couldn't check your sign-in or load your insights. Check that the backend is running, then try again."
    );
    return;
  }

  if (!auth.has_calendar_access) {
    const calendarWasDeclined = new URLSearchParams(window.location.search).get("status") === "calendar_denied";
    const calendarPrompt = h("section", {
      class: "auth-prompt calendar-connect-prompt",
      "aria-labelledby": "calendar-connect-heading",
    }, [
      h("div", { class: "auth-prompt-copy" }, [
        h("h2", { id: "calendar-connect-heading", text: calendarWasDeclined ? "Calendar stays optional" : "Add Calendar context" }),
        h("p", {
          text: calendarWasDeclined
            ? "Calendar wasn't connected. You can keep using your journal and insights, or connect Calendar later."
            : "Your journal works without Calendar. Connect it to let Reflect include scheduled events in new insights.",
        }),
      ]),
      h("div", { class: "auth-prompt-actions" }, [
        h("a", {
          class: "btn btn-primary",
          href: `${API_BASE_URL}/calendar/connect`,
          text: "Connect Calendar",
        }),
      ]),
    ]);
    insightsGrid.before(calendarPrompt);
  }

  const response = await api.getInsights();
  const weekly = response?.weekly || response;
  const monthly = response?.monthly || null;
  const yearly = response?.yearly || null;

  const normalizeInsight = (insight) => {
    if (!insight) return null;
    return {
      periodType: insight.periodType || insight.period_type || "weekly",
      periodLabel: insight.periodLabel || insight.period_label || insight.weekLabel || "",
      dateRange: insight.dateRange || insight.date_range || "",
      reflection: insight.reflection || "Not enough data.",
      timeAllocation: insight.timeAllocation || insight.time_allocation || [],
      themes: insight.themes || [],
      concerns: insight.concerns || [],
      patterns: insight.patterns || [],
    };
  };

  const weeklyInsight = normalizeInsight(weekly);
  if (weeklyInsight) {
    const weekLabelEl = document.getElementById("week-label");
    const labelText = weeklyInsight.dateRange
      ? `${weeklyInsight.periodLabel} · ${weeklyInsight.dateRange}`
      : weeklyInsight.periodLabel;
    weekLabelEl.textContent = labelText;
    document.getElementById("weekly-reflection").textContent = weeklyInsight.reflection;

    const SEGMENTS = 20;
    const barsEl = document.getElementById("time-bars");
    const items = weeklyInsight.timeAllocation || [];
    const totalHours = items.reduce((sum, item) => sum + Math.max(0, Number(item.hours || 0)), 0);
    const toneMap = {
      lilac: "lilac",
      lavender: "lilac",
      sky: "sky",
      blue: "sky",
      pink: "pink",
      rose: "pink",
      calm: "sky",
      focused: "lilac",
      draining: "pink",
      stressful: "pink",
    };

    for (const item of items) {
      const tone = toneMap[String(item.tone || "").trim().toLowerCase()] || "lilac";
      const fraction = totalHours > 0 ? Number(item.hours || 0) / totalHours : 0;
      const percentage = totalHours > 0 ? Math.round(fraction * 100) : 0;
      const filled = totalHours > 0 ? Math.max(1, Math.round(fraction * SEGMENTS)) : 0;
      const segments = h("div", { class: "segments", "aria-hidden": "true" });
      for (let i = 0; i < SEGMENTS; i++) {
        segments.append(h("i", { class: i < filled ? `on tone-${tone}` : "" }));
      }
      barsEl.append(
        h("div", { class: "bar-row" }, [
          h("div", { class: "bar-label" }, [
            h("span", { text: item.label }),
            h("span", { text: `${percentage}%` }),
          ]),
          segments,
        ])
      );
    }

    const cloudEl = document.getElementById("theme-cloud");
    const themes = weeklyInsight.themes || [];
    const maxCount = themes.length ? Math.max(...themes.map((t) => t.count)) : 1;
    const tones = ["lilac", "sky", "lilac", "sky", "pink"];
    themes.forEach((theme, i) => {
      const chip = h("span", { class: `theme-chip tone-${tones[i % tones.length]}` }, [
        document.createTextNode(theme.label),
        h("small", { text: String(theme.count) }),
      ]);
      chip.style.fontSize = `${(0.8125 + (theme.count / maxCount) * 0.3).toFixed(2)}rem`;
      cloudEl.append(chip);
    });

    const concernsEl = document.getElementById("concerns");
    for (const concern of weeklyInsight.concerns || []) {
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

    const patternsEl = document.getElementById("patterns");
    for (const pattern of weeklyInsight.patterns || []) {
      patternsEl.append(h("li", {}, [sparkle(), h("div", { text: pattern })]));
    }
  }

  const monthlyInsight = normalizeInsight(monthly);
  if (monthlyInsight) {
    const monthlyLabelEl = document.getElementById("monthly-label");
    const monthlyLabelText = monthlyInsight.dateRange
      ? `${monthlyInsight.periodLabel} · ${monthlyInsight.dateRange}`
      : monthlyInsight.periodLabel;
    monthlyLabelEl.textContent = monthlyLabelText;
    document.getElementById("monthly-reflection").textContent = monthlyInsight.reflection;

    const monthlyBarsEl = document.getElementById("monthly-time-bars");
    const monthlyItems = monthlyInsight.timeAllocation || [];
    const monthlyTotalHours = monthlyItems.reduce((sum, item) => sum + Math.max(0, Number(item.hours || 0)), 0);
    const monthlyToneMap = {
      lilac: "lilac",
      lavender: "lilac",
      sky: "sky",
      blue: "sky",
      pink: "pink",
      rose: "pink",
      calm: "sky",
      focused: "lilac",
      draining: "pink",
      stressful: "pink",
    };

    for (const item of monthlyItems) {
      const tone = monthlyToneMap[String(item.tone || "").trim().toLowerCase()] || "lilac";
      const fraction = monthlyTotalHours > 0 ? Number(item.hours || 0) / monthlyTotalHours : 0;
      const percentage = monthlyTotalHours > 0 ? Math.round(fraction * 100) : 0;
      const filled = monthlyTotalHours > 0 ? Math.max(1, Math.round(fraction * 20)) : 0;
      const segments = h("div", { class: "segments", "aria-hidden": "true" });
      for (let i = 0; i < 20; i++) {
        segments.append(h("i", { class: i < filled ? `on tone-${tone}` : "" }));
      }
      monthlyBarsEl.append(
        h("div", { class: "bar-row" }, [
          h("div", { class: "bar-label" }, [
            h("span", { text: item.label }),
            h("span", { text: `${percentage}%` }),
          ]),
          segments,
        ])
      );
    }

    const monthlyCloudEl = document.getElementById("monthly-theme-cloud");
    const monthlyThemes = monthlyInsight.themes || [];
    const monthlyMaxCount = monthlyThemes.length ? Math.max(...monthlyThemes.map((t) => t.count)) : 1;
    const monthlyTones = ["lilac", "sky", "lilac", "sky", "pink"];
    monthlyThemes.forEach((theme, i) => {
      const chip = h("span", { class: `theme-chip tone-${monthlyTones[i % monthlyTones.length]}` }, [
        document.createTextNode(theme.label),
        h("small", { text: String(theme.count) }),
      ]);
      chip.style.fontSize = `${(0.8125 + (theme.count / monthlyMaxCount) * 0.3).toFixed(2)}rem`;
      monthlyCloudEl.append(chip);
    });

    const monthlyConcernsEl = document.getElementById("monthly-concerns");
    for (const concern of monthlyInsight.concerns || []) {
      monthlyConcernsEl.append(
        h("li", {}, [
          sparkle(),
          h("div", {}, [
            document.createTextNode(concern.text),
            h("span", { class: "note", text: concern.note }),
          ]),
        ])
      );
    }

    const monthlyPatternsEl = document.getElementById("monthly-patterns");
    for (const pattern of monthlyInsight.patterns || []) {
      monthlyPatternsEl.append(h("li", {}, [sparkle(), h("div", { text: pattern })]));
    }
  }

  const yearlyInsight = normalizeInsight(yearly);
  if (yearlyInsight) {
    const yearlyLabelEl = document.getElementById("yearly-label");
    const yearlyLabelText = yearlyInsight.dateRange
      ? `${yearlyInsight.periodLabel} · ${yearlyInsight.dateRange}`
      : yearlyInsight.periodLabel;
    yearlyLabelEl.textContent = yearlyLabelText;
    document.getElementById("yearly-reflection").textContent = yearlyInsight.reflection;

    const yearlyBarsEl = document.getElementById("yearly-time-bars");
    const yearlyItems = yearlyInsight.timeAllocation || [];
    const yearlyTotalHours = yearlyItems.reduce((sum, item) => sum + Math.max(0, Number(item.hours || 0)), 0);
    const yearlyToneMap = {
      lilac: "lilac",
      lavender: "lilac",
      sky: "sky",
      blue: "sky",
      pink: "pink",
      rose: "pink",
      calm: "sky",
      focused: "lilac",
      draining: "pink",
      stressful: "pink",
    };

    for (const item of yearlyItems) {
      const tone = yearlyToneMap[String(item.tone || "").trim().toLowerCase()] || "lilac";
      const fraction = yearlyTotalHours > 0 ? Number(item.hours || 0) / yearlyTotalHours : 0;
      const percentage = yearlyTotalHours > 0 ? Math.round(fraction * 100) : 0;
      const filled = yearlyTotalHours > 0 ? Math.max(1, Math.round(fraction * 20)) : 0;
      const segments = h("div", { class: "segments", "aria-hidden": "true" });
      for (let i = 0; i < 20; i++) {
        segments.append(h("i", { class: i < filled ? `on tone-${tone}` : "" }));
      }
      yearlyBarsEl.append(
        h("div", { class: "bar-row" }, [
          h("div", { class: "bar-label" }, [
            h("span", { text: item.label }),
            h("span", { text: `${percentage}%` }),
          ]),
          segments,
        ])
      );
    }

    const yearlyCloudEl = document.getElementById("yearly-theme-cloud");
    const yearlyThemes = yearlyInsight.themes || [];
    const yearlyMaxCount = yearlyThemes.length ? Math.max(...yearlyThemes.map((t) => t.count)) : 1;
    const yearlyTones = ["lilac", "sky", "lilac", "sky", "pink"];
    yearlyThemes.forEach((theme, i) => {
      const chip = h("span", { class: `theme-chip tone-${yearlyTones[i % yearlyTones.length]}` }, [
        document.createTextNode(theme.label),
        h("small", { text: String(theme.count) }),
      ]);
      chip.style.fontSize = `${(0.8125 + (theme.count / yearlyMaxCount) * 0.3).toFixed(2)}rem`;
      yearlyCloudEl.append(chip);
    });

    const yearlyConcernsEl = document.getElementById("yearly-concerns");
    for (const concern of yearlyInsight.concerns || []) {
      yearlyConcernsEl.append(
        h("li", {}, [
          sparkle(),
          h("div", {}, [
            document.createTextNode(concern.text),
            h("span", { class: "note", text: concern.note }),
          ]),
        ])
      );
    }

    const yearlyPatternsEl = document.getElementById("yearly-patterns");
    for (const pattern of yearlyInsight.patterns || []) {
      yearlyPatternsEl.append(h("li", {}, [sparkle(), h("div", { text: pattern })]));
    }
  }
}

// ---- Boot --------------------------------------------------------------------

const page = document.body.dataset.page;
renderSidebar(document.body.dataset.section || page);

if (page === "journal") initJournalPage();
if (page === "entry") initEntryPage();
if (page === "insights") initInsightsPage();
// History and Settings are static placeholders and need no script logic yet.
