import os
import unittest
from datetime import date, datetime
from types import SimpleNamespace
from unittest.mock import patch

os.environ.setdefault("GEMINI_API_KEY", "test-key")
os.environ.setdefault("DATABASE_URL", "sqlite://")

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import backend.api as api
from backend.models import Base, JournalEntry, User


class WeeklyInsightRetrievalTest(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.db = sessionmaker(bind=self.engine)()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def test_retrieves_similar_entries_from_same_user_before_baseline(self):
        first_user = User(google_id="first-user")
        second_user = User(google_id="second-user")
        self.db.add_all([first_user, second_user])
        self.db.flush()

        relevant = JournalEntry(
            user_id=first_user.id,
            date=date(2026, 8, 20),
            content="My heartbeats are always fast when presenting at work.",
            created_at=datetime(2026, 8, 20),
        )
        unrelated = JournalEntry(
            user_id=first_user.id,
            date=date(2026, 8, 10),
            content="I spent the afternoon gardening.",
            created_at=datetime(2026, 8, 10),
        )
        baseline = JournalEntry(
            user_id=first_user.id,
            date=date(2026, 9, 25),
            content="I was nervous about work.",
            created_at=datetime(2026, 9, 25),
        )
        other_user = JournalEntry(
            user_id=second_user.id,
            date=date(2026, 8, 21),
            content="I felt anxious about presenting at work.",
            created_at=datetime(2026, 8, 21),
        )
        self.db.add_all([relevant, unrelated, baseline, other_user])
        self.db.commit()

        response = lambda vectors: SimpleNamespace(
            embeddings=[SimpleNamespace(values=vector) for vector in vectors]
        )
        with patch.object(api, "client") as mocked_client:
            mocked_client.models.embed_content.side_effect = [
                response([[1.0, 0.0]]),
                response([[0.99, 0.1], [0.1, 0.99]]),
            ]
            matches = api._retrieve_similar_journal_entries(
                self.db,
                first_user.id,
                [
                    SimpleNamespace(
                        date=date(2026, 10, 12),
                        content="I am anxious about an upcoming work presentation.",
                    )
                ],
                before_date=date(2026, 9, 21),
            )
            mocked_client.models.embed_content.side_effect = [
                response([[1.0, 0.0]]),
                response([[0.99, 0.1], [0.1, 0.99]]),
            ]
            strict_matches = api._retrieve_similar_journal_entries(
                self.db,
                first_user.id,
                [
                    SimpleNamespace(
                        date=date(2026, 10, 12),
                        content="I am anxious about an upcoming work presentation.",
                    )
                ],
                before_date=date(2026, 9, 21),
                min_similarity=0.999,
            )

        self.assertEqual([entry.id for entry in matches], [relevant.id])
        self.assertEqual(strict_matches, [])
        self.assertEqual(mocked_client.models.embed_content.call_count, 4)


if __name__ == "__main__":
    unittest.main()