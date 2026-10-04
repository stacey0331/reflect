import calendar
import json
import os
import re
import time
from datetime import date, datetime, timedelta, timezone
from typing import Optional

import requests
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from google import genai
from google.genai import types
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from sqlalchemy.exc import IntegrityError
from starlette.middleware.sessions import SessionMiddleware

from .models import (
    ImportantEvent,
    ImportantEventCreate,
    JournalEntry,
    JournalEntryCreate,
    JournalEntryUpdate,
    Insight,
    InsightResponse,
    User,
)
from .event_patterns import EVENT_PATTERNS
from .database import SessionLocal
from .logging_config import logger

os.environ.setdefault("OAUTHLIB_INSECURE_TRANSPORT", "1")

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise RuntimeError("GEMINI_API_KEY is not set. Source backend/.env.local before starting the server.")

DUPLICATE_DAY_MESSAGE = "An entry already exists for that day. Edit it instead."

client = genai.Client(api_key=GEMINI_API_KEY)
INSIGHT_MODELS = (
    # "gemini-3.8-flash",
    "gemini-3.5-flash-lite",
)

app = FastAPI()

app.add_middleware(
    SessionMiddleware,
    secret_key=os.environ.get("SESSION_SECRET_KEY", "reflect-dev-secret-change-me"),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5500"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

CLIENT_SECRETS_FILE = os.environ.get(
    "GOOGLE_CLIENT_SECRETS_FILE",
    os.path.join(os.path.dirname(os.path.dirname(__file__)), "credentials.json"),
)
FRONTEND_BASE_URL = os.environ.get("FRONTEND_URL", "http://localhost:5500")
GOOGLE_REDIRECT_URI = os.environ.get("GOOGLE_REDIRECT_URI", "http://localhost:8000/callback")
LOGIN_SCOPES = [
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
]
CALENDAR_SCOPE = "https://www.googleapis.com/auth/calendar.readonly"
CALENDAR_SCOPES = [*LOGIN_SCOPES, CALENDAR_SCOPE]
MAX_CALENDAR_EVENTS_PER_INSIGHT = 250


def get_google_flow(state: Optional[str] = None, scopes=LOGIN_SCOPES) -> Flow:
    return Flow.from_client_secrets_file(
        CLIENT_SECRETS_FILE,
        scopes=scopes,
        redirect_uri=GOOGLE_REDIRECT_URI,
        state=state,
    )


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_or_create_user(db, google_id: str) -> User:
    user = db.query(User).filter(User.google_id == google_id).first()
    if user is not None:
        return user

    is_first_user = db.query(User.id).first() is None
    user = User(google_id=google_id)
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        user = db.query(User).filter(User.google_id == google_id).first()
        if user is None:
            raise
        return user

    db.refresh(user)
    if is_first_user:
        db.query(JournalEntry).filter(JournalEntry.user_id.is_(None)).update(
            {JournalEntry.user_id: user.id}, synchronize_session=False
        )
        db.commit()
    return user


def get_current_user_id(request: Request) -> int:
    user = request.session.get("user")
    user_id = user.get("id") if user else None
    if not isinstance(user_id, int):
        raise HTTPException(status_code=401, detail="Please log in to continue.")
    return user_id


def _serialize_journal_entry(entry: JournalEntry):
    if entry is None:
        return None
    return {
        "id": entry.id,
        "date": entry.date.isoformat() if isinstance(entry.date, date) else entry.date,
        "content": entry.content,
        "created_at": entry.created_at.isoformat() if isinstance(entry.created_at, datetime) else entry.created_at,
        "updated_at": entry.updated_at.isoformat() if hasattr(entry, "updated_at") and entry.updated_at is not None and isinstance(entry.updated_at, datetime) else None,
    }


@app.get("/login")
def login(request: Request):
    flow = get_google_flow()
    authorization_url, state = flow.authorization_url(
        prompt="consent",
        access_type="offline",
        code_challenge_method="S256",
    )
    request.session["oauth_state"] = state
    request.session["oauth_code_verifier"] = flow.code_verifier
    request.session["oauth_action"] = "login"
    return RedirectResponse(authorization_url)


@app.get("/calendar/connect")
def connect_calendar(request: Request):
    if not isinstance((request.session.get("user") or {}).get("id"), int):
        return RedirectResponse(f"{FRONTEND_BASE_URL}/index.html?status=login_required")

    flow = get_google_flow(scopes=CALENDAR_SCOPES)
    authorization_url, state = flow.authorization_url(
        prompt="consent",
        access_type="offline",
        include_granted_scopes="true",
        code_challenge_method="S256",
    )
    request.session["oauth_state"] = state
    request.session["oauth_code_verifier"] = flow.code_verifier
    request.session["oauth_action"] = "calendar"
    return RedirectResponse(authorization_url)


@app.get("/callback")
def callback(request: Request, db=Depends(get_db)):
    state = request.session.get("oauth_state")
    if not state:
        raise HTTPException(status_code=400, detail="Invalid session or missing state token.")

    oauth_action = request.session.get("oauth_action", "login")
    returned_state = request.query_params.get("state")
    if returned_state and returned_state != state:
        raise HTTPException(status_code=400, detail="OAuth state did not match the session.")

    if request.query_params.get("error"):
        request.session.pop("oauth_state", None)
        request.session.pop("oauth_code_verifier", None)
        request.session.pop("oauth_action", None)
        if oauth_action == "calendar":
            return RedirectResponse(f"{FRONTEND_BASE_URL}/insights.html?status=calendar_denied")
        return RedirectResponse(f"{FRONTEND_BASE_URL}/index.html?status=login_cancelled")

    scopes = CALENDAR_SCOPES if oauth_action == "calendar" else LOGIN_SCOPES
    flow = get_google_flow(state=state, scopes=scopes)
    code_verifier = request.session.get("oauth_code_verifier")
    if code_verifier:
        flow.code_verifier = code_verifier

    try:
        flow.fetch_token(authorization_response=str(request.url))
    except Exception as exc:
        logger.exception("Google OAuth token exchange failed for callback request.")
        raise HTTPException(
            status_code=400,
            detail=f"Google OAuth exchange failed: {exc}",
        ) from exc

    credentials = flow.credentials

    if oauth_action == "calendar":
        user = request.session.get("user") or {}
        if not isinstance(user.get("id"), int):
            return RedirectResponse(f"{FRONTEND_BASE_URL}/index.html?status=login_required")
        if CALENDAR_SCOPE not in (credentials.scopes or []):
            return RedirectResponse(f"{FRONTEND_BASE_URL}/insights.html?status=calendar_denied")

        request.session["calendar_credentials"] = {
            "token": credentials.token,
            "refresh_token": credentials.refresh_token,
            "token_uri": credentials.token_uri,
            "client_id": credentials.client_id,
            "client_secret": credentials.client_secret,
            "scopes": credentials.scopes,
        }
        user["has_calendar_access"] = True
        request.session["user"] = user
        request.session.pop("oauth_state", None)
        request.session.pop("oauth_code_verifier", None)
        request.session.pop("oauth_action", None)
        return RedirectResponse(f"{FRONTEND_BASE_URL}/insights.html?status=calendar_connected")

    user_info_resp = requests.get(
        "https://www.googleapis.com/oauth2/v2/userinfo",
        headers={"Authorization": f"Bearer {credentials.token}"},
        timeout=15,
    )
    if not user_info_resp.ok:
        raise HTTPException(status_code=400, detail="Failed to retrieve user profile from Google.")

    user_info = user_info_resp.json()
    google_id = user_info.get("sub") or user_info.get("id")
    if not google_id:
        raise HTTPException(status_code=400, detail="Google account ID was not returned.")

    account = get_or_create_user(db, google_id)
    has_calendar_access = bool(
        request.session.get("calendar_credentials") or request.session.get("credentials")
    )

    request.session["user"] = {
        "id": account.id,
        "google_id": google_id,
        "email": user_info.get("email"),
        "name": user_info.get("name"),
        "picture": user_info.get("picture"),
        "has_calendar_access": has_calendar_access,
    }
    request.session.pop("oauth_state", None)
    request.session.pop("oauth_code_verifier", None)
    request.session.pop("oauth_action", None)
    return RedirectResponse(f"{FRONTEND_BASE_URL}/index.html?status=logged_in")


def url_for_dashboard(has_calendar_access: bool) -> str:
    status = "calendar_connected" if has_calendar_access else "logged_in_no_calendar"
    return f"{FRONTEND_BASE_URL}/index.html?status={status}"


# Shows calendar data in backend
@app.get("/calendar")
def read_calendar(request: Request):
    user = request.session.get("user")
    creds_data = request.session.get("calendar_credentials") or request.session.get("credentials")

    if not user or not creds_data:
        return RedirectResponse("/login")

    if not user.get("has_calendar_access"):
        raise HTTPException(
            status_code=403,
            detail="Calendar access was not granted by the user. Please re-authenticate at /login.",
        )

    creds = Credentials(**creds_data)
    service = build("calendar", "v3", credentials=creds)
    time_min = (
        datetime.now(timezone.utc) - timedelta(days=30)
    ).isoformat().replace("+00:00", "Z")

    events_result = service.events().list(
        calendarId="primary",
        timeMin=time_min,
        maxResults=MAX_CALENDAR_EVENTS_PER_INSIGHT,
        singleEvents=True,
        orderBy="startTime",
    ).execute()
    events = events_result.get("items", [])
    return {
        "account": user["email"],
        "event_count": len(events),
        "events": events,
    }


def _calendar_event_time(value: dict) -> str:
    return value.get("dateTime", value.get("date", "unknown time"))


def _get_calendar_context(credentials_data: dict, start_date: date, end_date: date) -> str:
    start_time = datetime.combine(start_date, datetime.min.time(), tzinfo=timezone.utc)
    end_time = datetime.combine(end_date + timedelta(days=1), datetime.min.time(), tzinfo=timezone.utc)
    events = []
    page_token = None

    try:
        creds = Credentials(**credentials_data)
        service = build("calendar", "v3", credentials=creds)
        while len(events) < MAX_CALENDAR_EVENTS_PER_INSIGHT:
            request_args = {
                "calendarId": "primary",
                "timeMin": start_time.isoformat().replace("+00:00", "Z"),
                "timeMax": end_time.isoformat().replace("+00:00", "Z"),
                "maxResults": min(250, MAX_CALENDAR_EVENTS_PER_INSIGHT - len(events)),
                "singleEvents": True,
                "orderBy": "startTime",
                "fields": "items(summary,start,end,status),nextPageToken",
            }
            if page_token:
                request_args["pageToken"] = page_token
            result = service.events().list(**request_args).execute()
            events.extend(
                event for event in result.get("items", [])
                if event.get("status") != "cancelled"
            )
            page_token = result.get("nextPageToken")
            if not page_token:
                break

        truncated = bool(page_token)
    except Exception as error:
        logger.warning("Calendar context unavailable for insight (%s).", type(error).__name__)
        return "Calendar events could not be retrieved for this period."

    if not events:
        return "No calendar events were found for this period."

    lines = []
    for event in events[:MAX_CALENDAR_EVENTS_PER_INSIGHT]:
        summary = " ".join((event.get("summary") or "Untitled event").split())
        start = _calendar_event_time(event.get("start") or {})
        end = _calendar_event_time(event.get("end") or {})
        lines.append(f"- {start} to {end}: {summary}")

    if truncated:
        lines.append(f"- Calendar list truncated after {MAX_CALENDAR_EVENTS_PER_INSIGHT} events.")
    return "\n".join(lines)


@app.get("/auth/status")
def auth_status(request: Request):
    user = request.session.get("user")
    if not user:
        return {"authenticated": False}
    return {
        "authenticated": True,
        "name": user.get("name"),
        "email": user.get("email"),
        "picture": user.get("picture"),
        "has_calendar_access": user.get("has_calendar_access", False),
    }


@app.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse(FRONTEND_BASE_URL, status_code=303)


@app.post("/api/journal")
def create_journal_entry(
    request: Request,
    entry: JournalEntryCreate,
    db = Depends(get_db)
):
    user_id = get_current_user_id(request)
    existing_entry = db.query(JournalEntry).filter(
        JournalEntry.user_id == user_id,
        JournalEntry.date == entry.date,
    ).first()
    if existing_entry:
        raise HTTPException(
            status_code=400,
            detail=DUPLICATE_DAY_MESSAGE,
        )

    db_entry = JournalEntry(
        user_id=user_id,
        date=entry.date,
        content=entry.content,
        created_at=datetime.now(timezone.utc),
    )
    db.add(db_entry)
    db.commit()
    db.refresh(db_entry)

    try:
        _upsert_event_candidate_from_entry(db, db_entry)
    except Exception:
        logger.exception(
            "Important event detection failed for journal entry %s; keeping the entry saved.",
            db_entry.id,
        )
    return _serialize_journal_entry(db_entry)


@app.get("/api/journal")
def get_journal_entries(
    request: Request,
    db = Depends(get_db)
):
    user_id = get_current_user_id(request)
    entries = db.query(JournalEntry).filter(
        JournalEntry.user_id == user_id
    ).order_by(JournalEntry.created_at.desc()).all()
    return [_serialize_journal_entry(entry) for entry in entries]


@app.get("/api/journal/{id}")
def get_journal_entry(
    id: int,
    request: Request,
    db = Depends(get_db)
):
    user_id = get_current_user_id(request)
    entry = db.query(JournalEntry).filter(
        JournalEntry.id == id,
        JournalEntry.user_id == user_id,
    ).first()
    if entry is None:
        raise HTTPException(status_code=404, detail="Journal entry not found.")
    return _serialize_journal_entry(entry)


@app.put("/api/journal/{id}")
def update_journal_entry(
    id: int,
    request: Request,
    entry: JournalEntryUpdate,
    db = Depends(get_db)
):
    user_id = get_current_user_id(request)
    db_entry = db.query(JournalEntry).filter(
        JournalEntry.id == id,
        JournalEntry.user_id == user_id,
    ).first()
    if db_entry is None:
        raise HTTPException(status_code=404, detail="Journal entry not found.")
    db_entry.date = entry.date
    db_entry.content = entry.content
    db.commit()
    db.refresh(db_entry)
    try:
        _upsert_event_candidate_from_entry(db, db_entry)
    except Exception:
        logger.exception(
            "Important event detection failed for journal entry %s; keeping the entry saved.",
            db_entry.id,
        )
    return _serialize_journal_entry(db_entry)

@app.delete("/api/journal/{id}")
def delete_journal_entry(
    id: int,
    request: Request,
    db = Depends(get_db)
):
    user_id = get_current_user_id(request)
    db_entry = db.query(JournalEntry).filter(
        JournalEntry.id == id,
        JournalEntry.user_id == user_id,
    ).first()
    if db_entry is None:
        raise HTTPException(status_code=404, detail="Journal entry not found.")
    db.delete(db_entry)
    db.commit()
    return {"message": "Entry deleted"}

@app.get("/api/insights")
def get_insights(
    request: Request,
    db = Depends(get_db)
):
    user_id = get_current_user_id(request)
    user = request.session.get("user") or {}
    calendar_credentials = request.session.get("calendar_credentials") or request.session.get("credentials")
    calendar_included = bool(user.get("has_calendar_access") and calendar_credentials)
    return {
        "weekly": _get_or_create_period_insight(db, "weekly", user_id, calendar_credentials, calendar_included),
        "monthly": _get_or_create_period_insight(db, "monthly", user_id, calendar_credentials, calendar_included),
        "yearly": _get_or_create_period_insight(db, "yearly", user_id, calendar_credentials, calendar_included),
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


def _get_or_create_period_insight(db, period_type, user_id, calendar_credentials=None, calendar_included=False):
    if period_type == "weekly":
        start_date, end_date = _get_last_completed_week_window()
        label = _get_week_label_for_date(start_date)
        return _get_or_create_insight_for_range(
            db,
            period_type="weekly",
            user_id=user_id,
            period_label=label,
            start_date=start_date,
            end_date=end_date,
            calendar_credentials=calendar_credentials,
            calendar_included=calendar_included,
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
                user_id=user_id,
                period_label=month_label,
                start_date=start_date,
                end_date=end_date,
                calendar_credentials=calendar_credentials,
                calendar_included=calendar_included,
            )
        start_date, end_date, month_label = month_window
        return _get_or_create_insight_for_range(
            db,
            period_type="monthly",
            user_id=user_id,
            period_label=month_label,
            start_date=start_date,
            end_date=end_date,
            calendar_credentials=calendar_credentials,
            calendar_included=calendar_included,
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
                user_id=user_id,
                period_label=str(last_year),
                start_date=start_date,
                end_date=end_date,
                calendar_credentials=calendar_credentials,
                calendar_included=calendar_included,
            )
        start_date, end_date, year_label = year_window
        return _get_or_create_insight_for_range(
            db,
            period_type="yearly",
            user_id=user_id,
            period_label=year_label,
            start_date=start_date,
            end_date=end_date,
            calendar_credentials=calendar_credentials,
            calendar_included=calendar_included,
        )

    return None


def _get_or_create_insight_for_range(
    db, period_type, period_label, start_date, end_date, user_id,
    calendar_credentials=None, calendar_included=False,
):
    existing = (
        db.query(Insight)
        .filter(Insight.user_id == user_id)
        .filter(Insight.calendar_included == calendar_included)
        .filter(Insight.period_type == period_type)
        .filter(Insight.period_label == period_label)
        .order_by(Insight.created_at.desc())
        .first()
    )
    if existing is not None:
        logger.info("Returning stored %s insight for %s", period_type, period_label)
        return _serialize_insight_row(existing)

    logger.info("No stored %s insight for %s; generating insight", period_type, period_label)
    return _generate_insight_for_range(
        db, period_type, period_label, start_date, end_date, user_id,
        calendar_credentials, calendar_included,
    )


def _signal_strength_for_text(text: str) -> tuple[str | None, int, str]:
    normalized = re.sub(r"[^a-z0-9\s]", " ", text.lower())
    phrase_matches = []
    for category, patterns in EVENT_PATTERNS.items():
        matched = [pattern for pattern in patterns if pattern in normalized]
        if matched:
            phrase_matches.append((category, len(matched)))

    if not phrase_matches:
        return None, 0, ""

    category, count = max(phrase_matches, key=lambda item: item[1])
    score = count * 4 + min(len(normalized.split()), 18)
    return category, score, normalized


def _already_has_similar_event(db, user_id: int, category: str, event_date: date, summary: str) -> bool:
    existing = (
        db.query(ImportantEvent)
        .filter(ImportantEvent.user_id == user_id)
        .filter(ImportantEvent.category == category)
        .filter(ImportantEvent.is_active.is_(True))
        .all()
    )
    if not existing:
        return False

    summary_tokens = set(re.sub(r"[^a-z0-9]", " ", summary.lower()).split())
    for event in existing:
        delta_days = abs((event_date - event.event_date).days)
        if delta_days <= 45:
            return True
        event_tokens = set(re.sub(r"[^a-z0-9]", " ", event.summary.lower()).split())
        overlap = len(summary_tokens & event_tokens)
        if overlap >= 4 and event.category == category:
            return True
    return False


def _upsert_event_candidate_from_entry(db, entry: JournalEntry):
    category, score, _ = _signal_strength_for_text(entry.content)
    if category is None or score < 8:
        return None

    summary = entry.content.strip()
    if len(summary) > 220:
        summary = summary[:217].rstrip() + "..."

    if _already_has_similar_event(db, entry.user_id, category, entry.date, summary):
        logger.info("Skipping duplicate important event candidate for %s on %s", category, entry.date.isoformat())
        return None

    existing_count = db.query(ImportantEvent).filter(
        ImportantEvent.user_id == entry.user_id,
        ImportantEvent.is_active.is_(True),
    ).count()
    if existing_count >= 10:
        logger.info("Important event cap reached; skipping new event candidate for %s", category)
        return None

    title = category.replace("_", " ").title()
    db_event = ImportantEvent(
        user_id=entry.user_id,
        title=title,
        category=category,
        summary=summary,
        event_date=entry.date,
        severity=min(10, max(6, score // 2)),
        is_active=True,
        related_journal_id=entry.id,
        source="auto-detect",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(db_event)
    db.commit()
    db.refresh(db_event)
    logger.info("Created important event candidate: %s (%s)", title, category)
    return db_event


def _detect_important_events(db, user_id, limit=10):
    active_events = (
        db.query(ImportantEvent)
        .filter(ImportantEvent.user_id == user_id)
        .filter(ImportantEvent.is_active.is_(True))
        .order_by(ImportantEvent.event_date.desc())
        .limit(limit)
        .all()
    )
    return active_events[:limit]


def _get_life_context_text(db, user_id):
    events = _detect_important_events(db, user_id, limit=10)
    if not events:
        return "No active important life events detected."

    formatted = []
    for event in events:
        label = f"{event.event_date.isoformat()} — {event.category} — {event.title}"
        formatted.append(f"- {label}: {event.summary}")
    return "\n".join(formatted)


def _generate_insight_for_range(
    db, period_type, period_label, start_date, end_date, user_id,
    calendar_credentials=None, calendar_included=False,
):
    range_entries = (
        db.query(JournalEntry)
        .filter(JournalEntry.user_id == user_id)
        .filter(JournalEntry.date >= start_date)
        .filter(JournalEntry.date <= end_date)
        .order_by(JournalEntry.date.desc())
        .all()
    )

    if not range_entries:
        logger.warning("No journal entries found for %s %s; returning empty insight", period_type, period_label)
        return _empty_insight(period_type, period_label, start_date, end_date)

    current_entries_text = "\n\n".join(
        f"{entry.date.isoformat()}: {entry.content}"
        for entry in range_entries
    )

    previous_start_date, previous_end_date = _get_previous_period_window(period_type, start_date, end_date)
    previous_entries = (
        db.query(JournalEntry)
        .filter(JournalEntry.user_id == user_id)
        .filter(JournalEntry.date >= previous_start_date)
        .filter(JournalEntry.date <= previous_end_date)
        .order_by(JournalEntry.date.desc())
        .all()
    )
    previous_entries_text = "\n\n".join(
        f"{entry.date.isoformat()}: {entry.content}"
        for entry in previous_entries
    )
    has_previous_data = bool(previous_entries)
    life_context_text = _get_life_context_text(db, user_id)
    calendar_context = (
        _get_calendar_context(calendar_credentials, start_date, end_date)
        if calendar_included and calendar_credentials
        else "Calendar context was not included."
    )
    logger.info(
        "Calendar context for %s (%s to %s):\n%s",
        period_type,
        start_date.isoformat(),
        end_date.isoformat(),
        calendar_context,
    )

    if period_type == "weekly":
        period_label_description = "week"
        previous_label = f"previous 3 weeks ({previous_start_date.isoformat()} to {previous_end_date.isoformat()})"
    elif period_type == "monthly":
        period_label_description = "month"
        previous_label = f"previous 3 months ({previous_start_date.isoformat()} to {previous_end_date.isoformat()})"
    else:
        period_label_description = "year"
        previous_label = f"previous year ({previous_start_date.isoformat()} to {previous_end_date.isoformat()})"

    prompt = f"""
    You are helping a person reflect on their {period_label_description}.

    Use the journal entries and calendar events below as context. 
    Calendar events are scheduled plans, not proof that the person attended, although the user should have attended most calendar events. 

    Analysis window:
    - periodType: {period_type}
    - periodLabel: {period_label}
    - dateRange: {start_date.isoformat()} to {end_date.isoformat()}

    Comparison context:
    - hasPreviousData: {str(has_previous_data).lower()}
    - compareAgainst: {'recent baseline' if has_previous_data else 'no prior period available'}
    - baselineLabel: {previous_label if has_previous_data else 'N/A'}
    - baselineDateRange: {previous_start_date.isoformat()} to {previous_end_date.isoformat()} if has_previous_data else 'N/A'

    ## Life context
    These are the person's active important life events. Treat them as personal context that may shape emotional patterns, stress, or recovery during this period.
    Keep this list limited to the most relevant active memories and do not invent anything beyond the summary provided.
    If there are no active important events, they are not relevant and should be ignored.

    {life_context_text}

    ## Calendar events for this period
    {calendar_context}

    ## Estimated time allocation
    Estimate how the period was distributed across categories as percentages.
    These are rough, best-effort proportions inferred from the journal, not exact tracked time.

    ## Reflection
    Write a short summary of what the period felt like overall.
    If hasPreviousData is true, start the reflection with a sentence that explicitly compares against the recent baseline, for example:
    "Compared with the previous 3 weeks, this week felt more intense and less restorative."
    or "Compared with the previous 3 months, this month felt calmer and more focused."
    or "Compared with last year, this year feels more fragmented and slower to recover."
    If hasPreviousData is false, do not mention a comparison at all. Write a normal summary of the period without comparing against a prior window.
    After the comparison sentence or the normal summary, add 1 thoughtful question that arises from the period.
    These should be open-ended, specific to the journal entries, and designed to help the user reflect rather than to give advice.

    ## Themes
    The main recurring ideas or topics in the journal entries.
    Focus on what is repeated across multiple entries, not one-off events.

    ## Concerns
    The main worries, blockers, or stressors from the period.

    ## Patterns
    Recurring habits or behaviors visible across the period, especially if they changed compared with the recent baseline.

    Return valid JSON that matches this schema:
    {InsightResponse.model_json_schema()}

    Current period journal entries:
    {current_entries_text}

    Previous period journal entries (only if available):
    {previous_entries_text if has_previous_data else 'No previous period data available.'}
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
        user_id=user_id,
        calendar_included=calendar_included,
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


def _get_previous_period_window(period_type, start_date, end_date):
    if period_type == "weekly":
        previous_start = start_date - timedelta(days=21)
        previous_end = start_date - timedelta(days=1)
        return previous_start, previous_end

    if period_type == "monthly":
        if start_date.month <= 3:
            previous_year = start_date.year - 1
            previous_month = start_date.month + 9
        else:
            previous_year = start_date.year
            previous_month = start_date.month - 3

        previous_start = date(previous_year, previous_month, 1)
        previous_end = date(
            previous_year,
            previous_month,
            calendar.monthrange(previous_year, previous_month)[1],
        )
        return previous_start, previous_end

    previous_year = start_date.year - 1
    previous_start = date(previous_year, 1, 1)
    previous_end = date(previous_year, 12, 31)
    return previous_start, previous_end


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

