// =============================================================================
// api.js: the ONLY file that talks to the backend.
//
// Every page goes through the functions below, so connecting your FastAPI
// backend means editing this one file.
//
// Endpoints the frontend expects:
//   GET    /api/journal        -> list of entries, newest first
//   POST   /api/journal        -> create an entry, returns the created entry
//   GET    /api/journal/{id}   -> one entry
//   PUT    /api/journal/{id}   -> update an entry, returns the updated entry
//   DELETE /api/journal/{id}   -> delete an entry (204 No Content is fine)
//
// Entry shape the UI reads (change it however you like, then update app.js):
//   { id, created_at, content }
// =============================================================================

import { mockApi, MOCK_INSIGHTS } from "./mock-data.js";

// -----------------------------------------------------------------------------
// flip this to false once your FastAPI server is running.
// While true, nothing is sent over the network and data comes from mock-data.js.
// -----------------------------------------------------------------------------
export const USE_MOCK = false;

// -----------------------------------------------------------------------------
// TODO(backend): where your FastAPI app lives.
//   - Frontend served by another dev server (e.g. python -m http.server)?
//     Use the full URL below and add CORSMiddleware to FastAPI.
//   - Frontend served BY FastAPI (StaticFiles)? Use "/api" (same origin).
// -----------------------------------------------------------------------------
const API_BASE = "http://localhost:8000/api";

// Small fetch wrapper: JSON in, JSON out, throws on any non-2xx response.
async function request(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    ...options,
  });

  const isJson = (response.headers.get("content-type") || "").includes("application/json");
  let payload = null;

  if (response.status !== 204) { // 204 is No Content
    payload = isJson
      ? await response.json().catch(() => null)
      : await response.text().catch(() => null);
  }

  if (!response.ok) {
    const detail = payload && typeof payload === "object"
      ? payload.detail ?? payload.error ?? payload.message
      : payload;

    const message = typeof detail === "string" && detail
      ? detail
      : `${options.method || "GET"} ${path} failed (${response.status})`;
    throw new Error(message);
  }

  return payload;
}

// ---- Journal entries --------------------------------------------------------

/** GET /api/journal */
export function listEntries() {
  if (USE_MOCK) return mockApi.list();
  return request("/journal");
}

/** GET /api/journal/{id} */
export function getEntry(id) {
  if (USE_MOCK) return mockApi.get(id);
  return request(`/journal/${encodeURIComponent(id)}`);
}

/**
 * POST /api/journal
 * Backend expects { date, content } where date is an ISO date string like
 * "2026-09-25".
 */
export function createEntry({ content }) {
  if (USE_MOCK) return mockApi.create({ content });

  const now = new Date();
  const date = [
    now.getFullYear(),
    String(now.getMonth() + 1).padStart(2, "0"),
    String(now.getDate()).padStart(2, "0"),
  ].join("-");

  return request("/journal", {
    method: "POST",
    body: JSON.stringify({ date, content }),
  });
}

/** PUT /api/journal/{id} */
export function updateEntry(id, { content }) {
  if (USE_MOCK) return mockApi.update(id, { content });

  const now = new Date();
  const date = [
    now.getFullYear(),
    String(now.getMonth() + 1).padStart(2, "0"),
    String(now.getDate()).padStart(2, "0"),
  ].join("-");

  return request(`/journal/${encodeURIComponent(id)}`, {
    method: "PUT",
    body: JSON.stringify({ date, content }),
  });
}

/** DELETE /api/journal/{id} */
export function deleteEntry(id) {
  if (USE_MOCK) return mockApi.remove(id);
  return request(`/journal/${encodeURIComponent(id)}`, { method: "DELETE" });
}

// ---- Insights (placeholder) -------------------------------------------------

/**
 * Insight payload for the dashboard. The backend now returns the same shape for
 * all periods, keyed by period type.
 */
export async function getInsights() {
  if (USE_MOCK) return MOCK_INSIGHTS;
  return request("/insights");
}
