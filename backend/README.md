# Backend (yours to build)

This folder is intentionally empty. The frontend in `../frontend` is ready to
talk to a FastAPI app that lives here.

Nothing has been implemented for you: no FastAPI app, no PostgreSQL schema, no
models, no auth, no LLM calls.

## The contract the frontend expects

| Method | Path                | Body                 | Returns                         |
| ------ | ------------------- | -------------------- | ------------------------------- |
| GET    | `/api/journal`      |                      | list of entries, newest first   |
| POST   | `/api/journal`      | `{ "content": "…" }` | the created entry               |
| GET    | `/api/journal/{id}` |                      | one entry (404 if missing)      |
| PUT    | `/api/journal/{id}` | `{ "content": "…" }` | the updated entry               |
| DELETE | `/api/journal/{id}` |                      | `204 No Content`                |

The frontend reads these fields from an entry (rename them if you like, then
update `frontend/js/app.js`):

```json
{ "id": 1, "created_at": "2026-09-18T21:40:00Z", "content": "…", "updated_at": "…optional…" }
```

Assumptions worth knowing:

- The backend sets `id` and `created_at`; the frontend only ever sends `content`.
- `created_at` should be an ISO 8601 timestamp (the browser formats it for display).
- Errors just need a non-2xx status. The UI shows a generic message.

## Connecting the frontend

1. Start your FastAPI app (default `http://localhost:8000`).
2. Add `CORSMiddleware` allowing the origin the frontend is served from
   (for example `http://localhost:5500`), **or** serve `../frontend` from FastAPI
   with `StaticFiles` and change `API_BASE` in `frontend/js/api.js` to `/api`.
3. In `frontend/js/api.js`, set `USE_MOCK = false`.

## Setup
```bash
pip install -r requirements.txt

python3 -m backend.database

python3 -m uvicorn backend.api:app --reload
```

## Local PostgreSQL

Reflect uses PostgreSQL for local development. PostgreSQL runs in Docker.
NOTE: update this section when moving FastAPI to Docker. 

### Start the database

From the project root:

```bash
docker compose up -d
```

### Check database status

```bash
docker compose ps
```

### Stop the database

```bash
docker compose down
```

## Open a PostgreSQL shell inside the Docker database container
```bash
docker compose exec db psql -U user -d mydatabase
```

Database data is persisted in the Docker volume `db-data`, so stopping the container does not delete the database.
