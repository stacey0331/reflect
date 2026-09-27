# Reflect

Reflect is a lightweight journaling app for capturing daily notes and turning them into reflection over time. The app is intentionally simple and calm: write, save, browse recent entries, and revisit them later for editing or deletion.

## What is built now

This repo currently includes:

- a static journaling frontend in [frontend](frontend)
- a FastAPI backend in [backend](backend)
- a PostgreSQL database configured with Docker in [compose.yaml](compose.yaml)
- SQLAlchemy models and a simple journal API
- a mock analytics/insights experience for the placeholder dashboard

The app is not yet a full AI reflection system, but the journal CRUD flow is in place and the frontend is wired to the backend API.

## Tech stack

- Frontend: plain HTML, CSS, JavaScript
- Backend: FastAPI
- Database: PostgreSQL
- ORM: SQLAlchemy
- Local dev DB: Docker Compose

## Local setup

### 1) Install Python dependencies

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2) Start PostgreSQL

```bash
docker compose up -d # bring it back without destroying the data
docker compose exec db psql -U user -d mydatabase
```

### 3) Configure the Gemini API key

Create or edit the local env file:

```bash
# backend/.env.local
export GEMINI_API_KEY="your-real-api-key"
```

Then load it before starting the backend:

```bash
source .venv/bin/activate
source backend/.env.local
uvicorn backend.api:app --reload
```

The API will be available at:

- http://localhost:8000/api/journal

> Do not commit the real key to Git. Keep the local env file untracked.

### 4) Run the frontend

```bash
cd frontend
python3 -m http.server 5500
```

Then open:

- http://localhost:5500

## API contract

The frontend expects these endpoints:

```text
GET    /api/journal
POST   /api/journal
GET    /api/journal/{id}
PUT    /api/journal/{id}
DELETE /api/journal/{id}
```

### Example payloads

Create an entry:

```json
{
  "date": "2026-09-25",
  "content": "Today I felt more focused after morning planning."
}
```

Update an entry:

```json
{
  "date": "2026-09-25",
  "content": "Updated reflection: I felt more focused after morning planning."
}
```

The journal list is sorted newest-first by `created_at`.

## Current status

This app currently supports:

- writing new entries
- listing recent entries in descending order
- opening a single entry
- editing an entry
- deleting an entry

The insights page is still mocked, and the AI/reflection features are still future work.

## Next ideas

- real AI-powered theme extraction and weekly reflection
- better journal search and filtering
- user auth
- deeper insights dashboard and analytics endpoints
- deployment setup and production config
