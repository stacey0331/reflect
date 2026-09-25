from datetime import datetime, timezone
from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .models import JournalEntry, JournalEntryCreate, JournalEntryUpdate
from .database import SessionLocal

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