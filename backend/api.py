import json
import os
from datetime import date, datetime, timedelta, timezone
from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .models import JournalEntry, JournalEntryCreate, JournalEntryUpdate, Insight, InsightResponse
from .database import SessionLocal
from .logging_config import logger
from google import genai
from google.genai import types

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise RuntimeError("GEMINI_API_KEY is not set. Source backend/.env.local before starting the server.")

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5500"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.post("/api/journal")
def create_journal_entry(
    entry: JournalEntryCreate,
    db = Depends(get_db)
):
    db_entry = JournalEntry(
        date=entry.date,
        content=entry.content,
        created_at=datetime.now(timezone.utc),
    )
    db.add(db_entry)
    db.commit()
    db.refresh(db_entry)
    return db_entry

@app.get("/api/journal")
def get_journal_entries(
    db = Depends(get_db)
):
    return db.query(JournalEntry).order_by(JournalEntry.created_at.desc()).all()

@app.get("/api/journal/{id}")
def get_journal_entry(
    id: int,
    db = Depends(get_db)
):
    return db.query(JournalEntry).filter(JournalEntry.id == id).first()

@app.put("/api/journal/{id}")
def update_journal_entry(
    id: int,
    entry: JournalEntryUpdate,
    db = Depends(get_db)
):
    db_entry = db.query(JournalEntry).filter(JournalEntry.id == id).first()
    if db_entry:
        db_entry.date = entry.date
        db_entry.content = entry.content
        db.commit()
        db.refresh(db_entry)
    return db_entry

@app.delete("/api/journal/{id}")
def delete_journal_entry(
    id: int,
    db = Depends(get_db)
):
    db_entry = db.query(JournalEntry).filter(JournalEntry.id == id).first()
    if db_entry:
        db.delete(db_entry)
        db.commit()
    return {"message": "Entry deleted"}

@app.get("/api/insight")
def get_insight(
    db = Depends(get_db)
):
    start_date, end_date = _get_last_completed_week_window()
    week_label = _get_week_label_for_date(start_date)
    date_range = f"{start_date.isoformat()} to {end_date.isoformat()}"

    existing = (
        db.query(Insight)
        .filter(Insight.week_label == week_label)
        .order_by(Insight.created_at.desc())
        .first()
    )

    if existing is not None:
        logger.info("Returning stored insight for %s", week_label)
        return {
            "weekLabel": existing.week_label,
            "dateRange": date_range,
            "weeklyReflection": existing.weekly_reflection,
            "timeAllocation": json.loads(existing.time_allocation or "[]"),
            "themes": json.loads(existing.themes or "[]"),
            "concerns": json.loads(existing.concerns or "[]"),
            "patterns": json.loads(existing.patterns or "[]"),
        }

    logger.info("No stored insight for %s; generating insight", week_label)
    insight_data = _generate_insight_for_recent_entries(db)
    return insight_data


def _get_week_label_for_date(day: date) -> str:
    iso_year, iso_week, _ = day.isocalendar()
    return f"{iso_year}-W{iso_week:02d}"


def _get_last_completed_week_window():
    today = datetime.now().astimezone().date()

    # Compute the most recent Sunday, then go back one full week to get the
    # previous completed Sunday-Saturday window.
    most_recent_sunday = today - timedelta(days=(today.weekday() + 1) % 7)
    start_date = most_recent_sunday - timedelta(days=7)
    end_date = start_date + timedelta(days=6)
    return start_date, end_date


def _generate_insight_for_recent_entries(db):
    start_date, end_date = _get_last_completed_week_window()
    week_label = _get_week_label_for_date(start_date)
    date_range = f"{start_date.isoformat()} to {end_date.isoformat()}"

    logger.info("Generating insight for week %s (%s)", week_label, date_range)

    recent_entries = (
        db.query(JournalEntry)
        .filter(JournalEntry.date >= start_date)
        .filter(JournalEntry.date <= end_date)
        .order_by(JournalEntry.date.desc())
        .all()
    )

    entries_text = "\n\n".join(
        f"{entry.date.isoformat()}: {entry.content}"
        for entry in recent_entries
    )

    prompt = f"""
    You are helping a person reflect on their week.

    Use only the journal entries below.

    Analysis window:
    - weekLabel: {week_label}
    - dateRange: {date_range}

    ## Estimated time allocation
    Where your hours went this week.

    ## Weekly reflection
    A short summary of what the week felt like overall.

    ## Themes
    The main recurring ideas or topics in the journal entries.

    ## Concerns
    The main worries, blockers, or stressors from the week.

    ## Patterns
    Recurring habits or behaviors visible across the week.

    Return valid JSON that matches this schema:
    {InsightResponse.model_json_schema()}

    Journal entries:
    {entries_text}
    """

    logger.debug("Insight prompt: %s", prompt)

    client = genai.Client(api_key=GEMINI_API_KEY)
    response = client.models.generate_content(
        model="gemini-3.8-flash",
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=InsightResponse,
        ),
    )

    logger.info("Gemini insight response received")
    insight = InsightResponse.model_validate_json(response.text)
    insight.weekLabel = week_label
    insight.dateRange = date_range

    db_insight = Insight(
        week_label=week_label,
        weekly_reflection=insight.weeklyReflection,
        time_allocation=json.dumps(
            [item.model_dump(mode="json") for item in insight.timeAllocation],
            ensure_ascii=False,
        ),
        themes=json.dumps(
            [item.model_dump(mode="json") for item in insight.themes],
            ensure_ascii=False,
        ),
        concerns=json.dumps(
            [item.model_dump(mode="json") for item in insight.concerns],
            ensure_ascii=False,
        ),
        patterns=json.dumps(insight.patterns, ensure_ascii=False),
        created_at=datetime.now(timezone.utc),
    )
    db.add(db_insight)
    db.commit()
    db.refresh(db_insight)

    return insight.model_dump(by_alias=True)
