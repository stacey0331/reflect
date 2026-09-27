import calendar
import json
import os
import time
from datetime import date, datetime, timedelta, timezone
from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from .models import JournalEntry, JournalEntryCreate, JournalEntryUpdate, Insight, InsightResponse
from .database import SessionLocal
from .logging_config import logger
from google import genai
from google.genai import types

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise RuntimeError("GEMINI_API_KEY is not set. Source backend/.env.local before starting the server.")

client = genai.Client(api_key=GEMINI_API_KEY)
INSIGHT_MODELS = (
    "gemini-3.8-flash",
    "gemini-3.5-flash-lite",
)

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

DUPLICATE_DAY_MESSAGE = "An entry already exists for that day. Edit it instead."


@app.post("/api/journal")
def create_journal_entry(
    entry: JournalEntryCreate,
    db = Depends(get_db)
):
    existing_entry = db.query(JournalEntry).filter(JournalEntry.date == entry.date).first()
    if existing_entry:
        raise HTTPException(
            status_code=400,
            detail=DUPLICATE_DAY_MESSAGE,
        )

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

@app.get("/api/insights")
def get_insights(
    db = Depends(get_db)
):
    return {
        "weekly": _get_or_create_period_insight(db, "weekly"),
        "monthly": _get_or_create_period_insight(db, "monthly"),
        "yearly": _get_or_create_period_insight(db, "yearly"),
    }


def _serialize_insight_row(row):
    if row is None:
        return None

    return {
        "periodType": row.period_type,
        "periodLabel": row.period_label,
        "dateRange": row.date_range,
        "reflection": row.reflection,
        "timeAllocation": json.loads(row.time_allocation or "[]"),
        "themes": json.loads(row.themes or "[]"),
        "concerns": json.loads(row.concerns or "[]"),
        "patterns": json.loads(row.patterns or "[]"),
    }


def _empty_insight(period_type, period_label, start_date, end_date):
    return {
        "periodType": period_type,
        "periodLabel": period_label,
        "dateRange": f"{start_date.isoformat()} to {end_date.isoformat()}",
        "reflection": "Not enough data.",
        "timeAllocation": [],
        "themes": [],
        "concerns": [],
        "patterns": [],
    }


def _get_or_create_period_insight(db, period_type):
    if period_type == "weekly":
        start_date, end_date = _get_last_completed_week_window()
        label = _get_week_label_for_date(start_date)
        return _get_or_create_insight_for_range(
            db,
            period_type="weekly",
            period_label=label,
            start_date=start_date,
            end_date=end_date,
        )

    if period_type == "monthly":
        month_window = _get_last_completed_month_window()
        if month_window is None:
            today = datetime.now().astimezone().date()
            target_month = date(today.year, today.month, 1)
            last_month = target_month - timedelta(days=1)
            start_date = date(last_month.year, last_month.month, 1)
            end_date = date(
                last_month.year,
                last_month.month,
                calendar.monthrange(last_month.year, last_month.month)[1],
            )
            month_label = start_date.strftime("%Y-%m")
            return _get_or_create_insight_for_range(
                db,
                period_type="monthly",
                period_label=month_label,
                start_date=start_date,
                end_date=end_date,
            )
        start_date, end_date, month_label = month_window
        return _get_or_create_insight_for_range(
            db,
            period_type="monthly",
            period_label=month_label,
            start_date=start_date,
            end_date=end_date,
        )

    if period_type == "yearly":
        year_window = _get_last_completed_year_window()
        if year_window is None:
            today = datetime.now().astimezone().date()
            last_year = today.year - 1
            start_date = date(last_year, 1, 1)
            end_date = date(last_year, 12, 31)
            return _get_or_create_insight_for_range(
                db,
                period_type="yearly",
                period_label=str(last_year),
                start_date=start_date,
                end_date=end_date,
            )
        start_date, end_date, year_label = year_window
        return _get_or_create_insight_for_range(
            db,
            period_type="yearly",
            period_label=year_label,
            start_date=start_date,
            end_date=end_date,
        )

    return None


def _get_or_create_insight_for_range(db, period_type, period_label, start_date, end_date):
    existing = (
        db.query(Insight)
        .filter(Insight.period_type == period_type)
        .filter(Insight.period_label == period_label)
        .order_by(Insight.created_at.desc())
        .first()
    )
    if existing is not None:
        logger.info("Returning stored %s insight for %s", period_type, period_label)
        return _serialize_insight_row(existing)

    logger.info("No stored %s insight for %s; generating insight", period_type, period_label)
    return _generate_insight_for_range(db, period_type, period_label, start_date, end_date)


def _generate_insight_for_range(db, period_type, period_label, start_date, end_date):
    range_entries = (
        db.query(JournalEntry)
        .filter(JournalEntry.date >= start_date)
        .filter(JournalEntry.date <= end_date)
        .order_by(JournalEntry.date.desc())
        .all()
    )

    if not range_entries:
        logger.warning("No journal entries found for %s %s; returning empty insight", period_type, period_label)
        return _empty_insight(period_type, period_label, start_date, end_date)

    entries_text = "\n\n".join(
        f"{entry.date.isoformat()}: {entry.content}"
        for entry in range_entries
    )

    if period_type == "weekly":
        period_label_description = "week"
    elif period_type == "monthly":
        period_label_description = "month"
    else:
        period_label_description = "year"

    prompt = f"""
    You are helping a person reflect on their {period_label_description}.

    Use only the journal entries below.

    Analysis window:
    - periodType: {period_type}
    - periodLabel: {period_label}
    - dateRange: {start_date.isoformat()} to {end_date.isoformat()}

    ## Estimated time allocation
    Roughly estimate how the period was distributed across categories, using approximate hours only.
    Do not pretend these hours are exact tracked time; they are best-effort estimates from the journal.

    ## Reflection
    A short summary of what the period felt like overall.

    ## Themes
    The main recurring ideas or topics in the journal entries.

    ## Concerns
    The main worries, blockers, or stressors from the period.

    ## Patterns
    Recurring habits or behaviors visible across the period.

    Return valid JSON that matches this schema:
    {InsightResponse.model_json_schema()}

    Journal entries:
    {entries_text}
    """

    logger.debug("Insight prompt for %s %s: %s", period_type, period_label, prompt)

    last_error = None
    insight = None
    for model_name in INSIGHT_MODELS:
        for attempt in range(3):
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        response_schema=InsightResponse,
                    ),
                )
                insight = InsightResponse.model_validate_json(response.text)
                logger.info(
                    "Gemini insight generated for %s %s using model %s",
                    period_type,
                    period_label,
                    model_name,
                )
                break
            except Exception as exc:  # pragma: no cover - runtime provider behavior
                last_error = exc
                logger.warning(
                    "Gemini request failed for %s %s using %s on attempt %s/%s: %s",
                    period_type,
                    period_label,
                    model_name,
                    attempt + 1,
                    3,
                    exc,
                )
                if attempt < 2:
                    time.sleep(2)
        if insight is not None:
            break
    if insight is None:
        raise last_error

    insight.periodType = period_type
    insight.periodLabel = period_label
    insight.dateRange = f"{start_date.isoformat()} to {end_date.isoformat()}"

    db_insight = Insight(
        period_type=period_type,
        period_label=period_label,
        date_range=insight.dateRange,
        reflection=insight.reflection,
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


def _get_last_completed_month_window():
    today = datetime.now().astimezone().date()
    days_in_month = calendar.monthrange(today.year, today.month)[1]
    if today.day < days_in_month:
        return None

    start_date = date(today.year, today.month, 1)
    end_date = date(today.year, today.month, days_in_month)
    return start_date, end_date, start_date.strftime("%Y-%m")


def _get_last_completed_year_window():
    today = datetime.now().astimezone().date()
    if today.month != 12 or today.day != 31:
        return None

    start_date = date(today.year, 1, 1)
    end_date = date(today.year, 12, 31)
    return start_date, end_date, str(today.year)

