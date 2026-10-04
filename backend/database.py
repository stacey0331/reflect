from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from .models import Base
import os


DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://user:password@localhost:5432/mydatabase"
)
engine = create_engine(DATABASE_URL)

SessionLocal = sessionmaker(bind=engine)

Base.metadata.create_all(engine)