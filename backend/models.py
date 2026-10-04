from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import DateTime, ForeignKey
from datetime import date as Date, datetime

## Pydantic
class JournalEntryCreate(BaseModel):
    date: Date
    content: str

class JournalEntryResponse(BaseModel):
    id: int

class JournalEntryUpdate(BaseModel):
    date: Date
    content: str

class ImportantEventCreate(BaseModel):
    title: str
    category: str
    summary: str
    event_date: Date
    severity: int = Field(default=7, ge=1, le=10)
    is_active: bool = True
    related_journal_id: int | None = None
    source: str = "manual"

class ImportantEventResponse(BaseModel):
    id: int
    title: str
    category: str
    summary: str
    event_date: Date
    severity: int
    is_active: bool
    related_journal_id: int | None = None
    source: str

class TimeAllocationItem(BaseModel):
    label: str = Field(
        description="Category label such as Work, Exercise, Family, Recovery, or Personal admin."
    )
    hours: float = Field(
        description="Approximate number of hours for this category, inferred from the journal and not meant to be exact tracked time."
    )
    tone: str = Field(
        description="The emotional tone of this time block, such as focused, calm, draining, or stressful."
    )

class ThemeItem(BaseModel):
    label: str = Field(
        description="A short label for the main topic or idea that repeated across the week, such as focus, burnout, family stress, or health."
    )
    count: int = Field(
        description="How many times this theme appears across the week's journal entries."
    )

class ConcernItem(BaseModel):
    text: str = Field(
        description="A short description of the concern or pain point."
    )
    note: str = Field(
        description="Context or explanation about why this concern matters."
    )

class InsightResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    periodType: str = Field(
        description="The type of period, such as weekly, monthly, or yearly."
    )
    periodLabel: str = Field(
        description="The label for the analysis period, such as 2026-W39, 2026-09, or 2026."
    )
    dateRange: str = Field(
        description="The exact date range for the analysis in YYYY-MM-DD to YYYY-MM-DD format."
    )
    reflection: str = Field(
        description="A concise reflection on how the period felt overall."
    )
    timeAllocation: list[TimeAllocationItem] = Field(
        description="Estimated time allocation: a rough, approximate distribution of how the period felt, not exact tracked hours."
    )
    themes: list[ThemeItem] = Field(
        description="Main recurring topics or ideas across the period. Each item is a short label and how often it appeared."
    )
    concerns: list[ConcernItem] = Field(
        description="Main concerns, blockers, or recurring stressors."
    )
    patterns: list[str] = Field(
        description="Recurring behaviors or routines visible across the journal entries, such as Mornings feel harder after nights you write about scrolling past midnight, or journaling most after stressful days."
    )


## SQLAlchemy
class Base(DeclarativeBase):
    pass

class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    google_id: Mapped[str] = mapped_column(unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow
    )

class JournalEntry(Base):
    __tablename__ = "journal_entries"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    date: Mapped[Date]
    content: Mapped[str]
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True)
    )

class Insight(Base):
    __tablename__ = "insights"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    calendar_included: Mapped[bool] = mapped_column(default=False)
    period_type: Mapped[str]
    period_label: Mapped[str]
    date_range: Mapped[str]
    reflection: Mapped[str]
    time_allocation: Mapped[str]
    themes: Mapped[str]
    concerns: Mapped[str]
    patterns: Mapped[str]
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True)
    )

class ImportantEvent(Base):
    __tablename__ = "important_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    title: Mapped[str]
    category: Mapped[str]
    summary: Mapped[str]
    event_date: Mapped[Date]
    severity: Mapped[int] = mapped_column(default=7)
    is_active: Mapped[bool] = mapped_column(default=True)
    related_journal_id: Mapped[int | None] = mapped_column(default=None)
    source: Mapped[str] = mapped_column(default="manual")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow
    )


