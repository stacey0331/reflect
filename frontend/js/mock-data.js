// =============================================================================
// mock-data.js: TEMPORARY. Delete this file once the FastAPI backend is live.
//
// Everything in here exists only so the UI can be demoed with no backend
// running. api.js is the only file that imports it. When you're ready:
//   1. Set USE_MOCK = false in api.js
//   2. Remove the mock import and the `if (USE_MOCK)` branches in api.js
//   3. Delete this file
//
// Mock entries are kept in localStorage so save / edit / delete survive a page
// reload during the demo. Your real data will live in PostgreSQL instead.
// =============================================================================

const STORAGE_KEY = "reflect:mock-entries";

// Build an ISO timestamp for "N days ago at HH:MM" so the demo always looks fresh.
function at(daysAgo, hour, minute) {
  const d = new Date();
  d.setDate(d.getDate() - daysAgo);
  d.setHours(hour, minute, 0, 0);
  return d.toISOString();
}

// Assumed entry shape. Change it freely to match whatever you design:
//   { id: number, created_at: ISO string, updated_at?: ISO string, content: string }
const SEED_ENTRIES = [
  {
    id: 6,
    created_at: at(1, 21, 40),
    content:
      "Long day. Spent most of it heads-down on the quarterly report and skipped lunch, which I regret. Went for a walk around the block at sunset and it reset my brain a little.\n\nCalled Mei after dinner. We talked for almost an hour about her move. I'm happy for her, and a little sad she'll be so far away.",
  },
  {
    id: 5,
    created_at: at(2, 22, 5),
    content:
      "Pilates in the morning, then a slow afternoon at the cafe with my book. Made pasta with way too much garlic and didn't regret it.\n\nStill thinking about the presentation on Thursday. I keep rehearsing it in my head at random moments.",
  },
  {
    id: 4,
    created_at: at(3, 20, 15),
    content:
      "Rough start. Woke up late, missed the bus, and felt behind all day. Meetings back to back until 4.\n\nManaged a quick stretch before bed. I need to stop scrolling my phone until midnight, it's making mornings harder.",
  },
  {
    id: 3,
    created_at: at(5, 19, 30),
    content:
      "Dinner with the girls at the new ramen place! Laughed so much my face hurt.\n\nSomeone brought up the group trip in November and now I'm excited and also anxious about money.",
  },
  {
    id: 2,
    created_at: at(6, 18, 50),
    content:
      "Quiet Sunday. Cleaned my room, watered the plants, and finally sorted the pile of clothes to donate. Watched two episodes of a show and went to bed early. Felt really good.",
  },
  {
    id: 1,
    created_at: at(8, 21, 10),
    content:
      "Worked on the side project for two hours after work, the first time in weeks. It felt good to make something just for fun.\n\nAlso worried I'm not spending enough time on it, or on anything that isn't work.",
  },
];

// -----------------------------------------------------------------------------
// Mock "database" (localStorage). Mirrors what the real endpoints will do.
// -----------------------------------------------------------------------------
function readAll() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) return JSON.parse(raw);
  } catch {
    /* storage unavailable or corrupted: fall through to the seed data */
  }
  return structuredClone(SEED_ENTRIES);
}

function writeAll(entries) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(entries));
  } catch {
    /* ignore: the demo just won't persist */
  }
}

function newestFirst(entries) {
  return [...entries].sort(
    (a, b) => new Date(b.created_at) - new Date(a.created_at)
  );
}

export const mockApi = {
  async list() {
    return newestFirst(readAll());
  },

  async get(id) {
    const entry = readAll().find((e) => String(e.id) === String(id));
    if (!entry) throw new Error("Entry not found");
    return entry;
  },

  async create({ content }) {
    const entries = readAll();
    const nextId = entries.reduce((max, e) => Math.max(max, e.id), 0) + 1;
    const entry = { id: nextId, created_at: new Date().toISOString(), content };
    writeAll([entry, ...entries]);
    return entry;
  },

  async update(id, { content }) {
    const entries = readAll();
    const index = entries.findIndex((e) => String(e.id) === String(id));
    if (index === -1) throw new Error("Entry not found");
    entries[index] = {
      ...entries[index],
      content,
      updated_at: new Date().toISOString(),
    };
    writeAll(entries);
    return entries[index];
  },

  async remove(id) {
    writeAll(readAll().filter((e) => String(e.id) !== String(id)));
    return null;
  },
};

// -----------------------------------------------------------------------------
// PLACEHOLDER INSIGHTS: made-up numbers for the dashboard layout only.
// These will eventually be computed by your backend (LLM extraction + SQL
// aggregation). The shape below is just a suggestion for what the UI renders.
// -----------------------------------------------------------------------------
export const MOCK_INSIGHTS = {
  weekLabel: "2026-W37",
  dateRange: "2026-09-13 to 2026-09-19",

  // Where the week went, in hours. tone is one of: lilac, sky, pink
  timeAllocation: [
    { label: "Work", hours: 31, tone: "lilac" },
    { label: "Rest and sleep-ins", hours: 12, tone: "sky" },
    { label: "Friends and family", hours: 9, tone: "pink" },
    { label: "Cooking and home", hours: 7, tone: "sky" },
    { label: "Movement", hours: 6, tone: "lilac" },
  ],

  // Themes that keep coming up; `count` is how many entries mention them
  themes: [
    { label: "deadlines", count: 7 },
    { label: "friends", count: 5 },
    { label: "sleep", count: 4 },
    { label: "cooking", count: 3 },
    { label: "walks", count: 3 },
    { label: "money", count: 2 },
    { label: "side project", count: 2 },
  ],

  // Things that seem to be bothering you
  concerns: [
    { text: "The Thursday presentation", note: "Mentioned in 3 entries" },
    { text: "Late-night phone scrolling", note: "Mentioned in 2 entries" },
    { text: "Money for the November trip", note: "Mentioned in 1 entry" },
  ],

  weeklyReflection:
    "This was a work-heavy week, but the days that felt best all had something small and offline in them: a walk at sunset, a slow cafe afternoon, a long call with a friend. The tougher days followed nights with late scrolling. You keep circling back to the Thursday presentation, and you sound calmer once you've rehearsed it out loud.",

  patterns: [
    "Mornings feel harder after nights you write about scrolling past midnight.",
    "You mention feeling good on days with a walk or a workout.",
    "Worries about money tend to appear right after plans with friends.",
  ],

  monthly: {
    weekLabel: "2026-09",
    dateRange: "2026-09-01 to 2026-09-30",
    weeklyReflection:
      "September has felt like a month of catching up. You’ve been in motion, but not always by choice. The work pattern still dominates, and the calmest moments are the ones where you step away from screens and back into your routine.",
    timeAllocation: [
      { label: "Work", hours: 96, tone: "lilac" },
      { label: "Rest and sleep-ins", hours: 52, tone: "sky" },
      { label: "Friends and family", hours: 30, tone: "pink" },
      { label: "Cooking and home", hours: 24, tone: "sky" },
      { label: "Movement", hours: 18, tone: "lilac" },
    ],
    themes: [
      { label: "workload", count: 10 },
      { label: "sleep", count: 8 },
      { label: "family", count: 6 },
      { label: "home", count: 5 },
      { label: "money", count: 4 },
    ],
    concerns: [
      { text: "The rhythm keeps slipping", note: "Reappeared across multiple entries" },
      { text: "A few too many late nights", note: "Especially on work-heavy days" },
    ],
    patterns: [
      "Your best days are the ones with a walk, a meal, or a real conversation.",
      "Stress seems to spike when the week gets crowded and there’s no recovery time.",
      "You can feel the difference when your routine gets modest and consistent.",
    ],
  },

  yearly: {
    weekLabel: "2026",
    dateRange: "2026-01-01 to 2026-12-31",
    weeklyReflection:
      "This year has been about momentum, but not always with enough recovery. The pattern is bigger than a single month: work and obligations dominate, while your best days are the ones that include movement, rest, and actual human connection.",
    timeAllocation: [
      { label: "Work", hours: 1120, tone: "lilac" },
      { label: "Rest and sleep-ins", hours: 620, tone: "sky" },
      { label: "Friends and family", hours: 360, tone: "pink" },
      { label: "Cooking and home", hours: 260, tone: "sky" },
      { label: "Movement", hours: 220, tone: "lilac" },
    ],
    themes: [
      { label: "focus", count: 22 },
      { label: "rest", count: 18 },
      { label: "family", count: 15 },
      { label: "money", count: 12 },
      { label: "health", count: 10 },
    ],
    concerns: [
      { text: "Too much work without enough transition time", note: "It keeps showing up in the writing" },
      { text: "Pressure around money and planning", note: "Often shows up before trips or big decisions" },
    ],
    patterns: [
      "Your most sustainable days usually include a walk, a meal, or a low-pressure break.",
      "The wave of stress is usually tied to an overloaded week and not enough recovery.",
      "You feel most grounded when your routine is simple and steady.",
    ],
  },
};
