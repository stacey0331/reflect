# reflect: a personal journal and reflection app

## What this is

A journal you write in plain language. Over time it will store your entries,
pull structure out of them with an LLM, and show you patterns: where your time
goes, what keeps coming up, what's been bothering you, and a weekly reflection.

**Right now this repo contains only the frontend and project boilerplate.** The
backend, database, and AI parts are deliberately left for you to build.

The look is calm and Claude-like (sidebar, plain composer) with pixel y2k
details (one pixel font throughout, pixel hearts and sparkles, notched pixel
corners, segmented bars). Mostly white, baby blue and lavender, with a little pink.

It's plain HTML, CSS, and JavaScript with no framework, no build step, and no
dependencies. The font (Pixelify Sans, SIL Open Font License)
is bundled in `frontend/fonts/`, so the app makes no external requests.

## Project structure

```
.
├── frontend/
│   ├── index.html        Journal: write an entry, see recent entries
│   ├── journal.html      A single entry (journal.html?id=3): read, edit, delete
│   ├── insights.html     Placeholder analytics dashboard (mock data)
│   ├── settings.html     Placeholder page
│   ├── css/
│   │   └── styles.css    All styling, with design tokens at the top
│   ├── fonts/            Bundled web fonts + their licenses
│   └── js/
│       ├── app.js        Page behavior + shared sidebar (builds DOM with textContent)
│       ├── api.js        The ONLY file that talks to the backend
│       └── mock-data.js  TEMPORARY mock entries + fake insights (delete later)
├── backend/
│   └── README.md         Notes for the API you'll build
├── README.md
└── .gitignore
```

There is no separate History page. The Journal page shows your latest 5 entries
with a "Show all entries" button that expands to the full list, using the same
`GET /api/journal` call.

## Run the frontend locally

The pages use ES modules, which browsers won't load from `file://`, so serve
the folder over HTTP:

```bash
cd frontend
python3 -m http.server 5500
```

Then open <http://localhost:5500>.

## What is mocked

- **Journal entries.** While `USE_MOCK = true` in `frontend/js/api.js`, entries
  come from `frontend/js/mock-data.js` and are saved to your browser's
  `localStorage`, so save, edit, and delete work and survive a refresh. To reset
  the demo, clear that site's local storage. A "Demo mode" note in the sidebar
  reminds you while this is on.
- **Insights.** Every number and sentence on the Insights page is made-up data
  (`MOCK_INSIGHTS` in `mock-data.js`). The page is marked "Sample data only".
  It stays mocked even after you flip `USE_MOCK`, until you build an insights
  endpoint.
- **Settings.** A static placeholder page with no logic.

## API endpoints the frontend expects

```
GET    /api/journal          list entries, newest first
POST   /api/journal          body: { "content": "…" }, returns the created entry
GET    /api/journal/{id}     one entry
PUT    /api/journal/{id}     body: { "content": "…" }, returns the updated entry
DELETE /api/journal/{id}     204 No Content
```

Assumed entry shape: `{ id, created_at, content, updated_at? }`. See
`backend/README.md` for details and how to connect. Look for `TODO(backend)`
comments in `js/api.js` and `js/app.js`.

## Left for you to implement

- The FastAPI app and the five endpoints above
- The PostgreSQL schema, models, and queries
- Authentication (nothing is built, and there is no login screen)
- LLM extraction of activities, themes, and concerns from entries
- Analytics, weekly reflections, and "ask questions about my entries"
  (including any embeddings or RAG)
- A real `/api/insights` endpoint (the Insights page shape is in `mock-data.js`)
- Pagination on `GET /api/journal` once the list gets long
- Docker setup and GCP deployment
