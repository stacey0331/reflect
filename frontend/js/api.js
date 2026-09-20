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
// TODO(backend): flip this to false once your FastAPI server is running.
// While true, nothing is sent over the network and data comes from mock-data.js.
// -----------------------------------------------------------------------------
export const USE_MOCK = true;

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
    ...options,
  });

  if (!response.ok) {
    throw new Error(`${options.method || "GET"} ${path} failed (${response.status})`);
  }
  if (response.status === 204) return null; // e.g. successful DELETE
  return response.json();
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
 * Sends only { content }. The frontend assumes your backend sets the id and
 * created_at timestamp.
 */
export function createEntry({ content }) {
  if (USE_MOCK) return mockApi.create({ content });
  return request("/journal", {
    method: "POST",
    body: JSON.stringify({ content }),
  });
}

/** PUT /api/journal/{id} */
export function updateEntry(id, { content }) {
  if (USE_MOCK) return mockApi.update(id, { content });
  return request(`/journal/${encodeURIComponent(id)}`, {
    method: "PUT",
    body: JSON.stringify({ content }),
  });
}

/** DELETE /api/journal/{id} */
export function deleteEntry(id) {
  if (USE_MOCK) return mockApi.remove(id);
  return request(`/journal/${encodeURIComponent(id)}`, { method: "DELETE" });
}

// ---- Insights (placeholder) -------------------------------------------------

/**
 * FUTURE endpoint, not part of the list above. The Insights page currently
 * renders MOCK_INSIGHTS. Once you've built analytics on the backend, expose
 * something like GET /api/insights and return the same shape (see mock-data.js).
 * Unlike the journal calls, this one stays on mock data even after USE_MOCK
 * is flipped, until you implement it.
 */
export async function getInsights() {
  // TODO(backend): return request("/insights");
  return MOCK_INSIGHTS;
}
