
import os

from sqlalchemy import create_engine
from sqlalchemy.engine import URL
from sqlalchemy.orm import sessionmaker

from .models import Base


connection_name = os.getenv("INSTANCE_CONNECTION_NAME")

if connection_name:
    database_url = URL.create(
        drivername="postgresql",
        username=os.getenv("DB_USER", "reflect-app"),
        password=os.environ["DB_PASSWORD"],
        database=os.getenv("DB_NAME", "reflect"),
        query={
            "host": f"/cloudsql/{connection_name}",
        },
    )
else:
    database_url = os.getenv(
        "DATABASE_URL",
        "postgresql://user:password@localhost:5432/mydatabase",
    )

engine = create_engine(database_url)
SessionLocal = sessionmaker(bind=engine)

Base.metadata.create_all(engine)