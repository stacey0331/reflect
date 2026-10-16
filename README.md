# Reflect

A journaling app for capturing daily notes and turning them into meaningful insights over time. Think of it as a friend that knows you well—helping you become more aware of how you spend your time, understand your moods, and gain potential insights for navigating life.

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
- Local PostgreSQL: Docker Compose

## Local setup

### 1) Install Python dependencies

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2) Configure local environment variables

Create or edit:

```bash
backend/.env.local
```

```bash
GEMINI_API_KEY="your-real-api-key"
FRONTEND_URL="http://localhost:5500"
GOOGLE_REDIRECT_URI="http://localhost:8000/callback"
```

> Do not commit the real API key to Git. Keep `backend/.env.local` untracked.

### 3) Start the backend and PostgreSQL

Docker Compose starts both the FastAPI backend and PostgreSQL:

```bash
docker compose up --build
```

To run them in the background:

```bash
docker compose up --build -d
```

The API will be available at:

* http://localhost:8000
* http://localhost:8000/docs

PostgreSQL data is persisted in the `db-data` Docker volume, so stopping the containers does not delete the database.

To stop the containers:

```bash
docker compose down
```

### 4) Run the frontend

In a separate terminal:

```bash
cd frontend
python3 -m http.server 5500
```

Then open:

* http://localhost:5500


## Dpeloyement
### Create PostgreSQL instance
```
gcloud sql instances create reflect-db \
  --database-version=POSTGRES_16 \
  --region=asia-east1 \
  --tier=db-f1-micro
```

### Backend
```
gcloud run deploy reflect-api \
  --source . \
  --region asia-east1 \
  --allow-unauthenticated \
  --port 8000 \
  --min 0 \
  --max 2
```

### Frontend
```
firebase deploy --only hosting
```


## Current status

This app currently supports:

- writing/editing/deleting/viewing entries
- user log in
- the "insight" page


## Next ideas
- i really want to spend a lot of time on making the AI smarter
- better journal search and filtering
- deeper insights dashboard and analytics endpoints
- better deployment
