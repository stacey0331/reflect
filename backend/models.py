from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import DateTime
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

class TimeAllocationItem(BaseModel):
    label: str = Field(
        description="Category label such as Work, Exercise, Family, Recovery, or Personal admin."
    )
    hours: float = Field(
        description="Estimated number of hours spent in this category during the week."
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

    weekLabel: str = Field(
        description="The week label for the analysis, such as 2026-W39."
    )
    dateRange: str = Field(
        description="The exact date range for the analysis in YYYY-MM-DD to YYYY-MM-DD format."
    )
    weeklyReflection: str = Field(
        description="A concise reflection on how the week felt overall."
    )
    timeAllocation: list[TimeAllocationItem] = Field(
        description="Estimated time allocation: where your hours went this week."
    )
    themes: list[ThemeItem] = Field(
        description="Main recurring topics or ideas across the week. Each item is a short label and how often it appeared."
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

class JournalEntry(Base):
    __tablename__ = "journal_entries"

    id: Mapped[int] = mapped_column(primary_key=True)
    date: Mapped[Date]
    content: Mapped[str]
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True)
    )

class Insight(Base):
    __tablename__ = "insights"

    id: Mapped[int] = mapped_column(primary_key=True)
    week_label: Mapped[str]
    weekly_reflection: Mapped[str]
    time_allocation: Mapped[str]
    themes: Mapped[str]
    concerns: Mapped[str]
    patterns: Mapped[str]
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True)
    )


