# Reflect

An AI-powered journaling app that analyzes your entries to surface meaningful patterns and insights, helping you better understand and reflect on your life.

## Why I Built Reflect
This app solves a real problem I personally have. I believe journaling helps processing emotions, but sometimes I want to look back on what happened in my life during a certain period of time. I also want to check how I am doing lately compare to last month or year, and see if the way I spend my time is actually leading me to the life I'm trying to build. 

## Tech stack

- Frontend: plain HTML, CSS, JavaScript
- Backend: FastAPI
- Database: PostgreSQL
- ORM: SQLAlchemy
- Local PostgreSQL: Docker Compose
- Deployment: GCP Cloud Run, Firebase

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

To open a PostgreSQL shell: 
```
docker compose exec db sh -c 'exec psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"'
```

### 4) Run the frontend

In a separate terminal:

```bash
cd frontend
python3 -m http.server 5500
```

Then open:

* http://localhost:5500

### 5) Run unit test
```
python -m unittest tests.test_weekly_insight_retrieval -v
python -m unittest tests.test_weekly_insight_retrieval_live -v
```
run all: 
```
python -m unittest discover -s tests -v
```

### Evaluate weekly RAG retrieval

This live retrieval evaluation compares cosine-similarity thresholds using labeled query/candidate examples. It calls Gemini's embedding API. The example dataset is fictional; copy it to the git-ignored local dataset and replace it with labeled examples for a meaningful evaluation.

Load the Gemini key from `backend/.env.local`, then run from the repository root:

```bash
set -a
source backend/.env.local
set +a
python -m eval.evaluate_weekly_retrieval \
  --dataset eval/dataset.example.json \
  --thresholds 0.60,0.70,0.80,0.90,0.95,0.99
```

For a private dataset, first copy `eval/dataset.example.json` to `eval/dataset.local.json`, edit the examples and labels, and pass `--dataset eval/dataset.local.json`.



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
- i really want to spend a lot more time on making the AI smarter
- make the app more scalable by accommodating many requests at the same time. 
- better UX. currently things don't load right away for some reason. also would like to add more features like search and filtering

