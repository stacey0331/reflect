from pydantic import BaseModel
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

