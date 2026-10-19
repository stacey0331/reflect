import os
import unittest
from datetime import date, datetime

os.environ.setdefault("DATABASE_URL", "sqlite://")
os.environ.setdefault("GEMINI_API_KEY", "test-key")

from google import genai
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import backend.api as api
from backend.models import Base, JournalEntry, User


LIVE_GEMINI_ENABLED = (
    os.getenv("RUN_LIVE_GEMINI_TESTS") == "1"
    and bool(os.getenv("GEMINI_API_KEY"))
    and os.getenv("GEMINI_API_KEY") != "test-key"
)


@unittest.skipUnless(
    LIVE_GEMINI_ENABLED,
    "Set RUN_LIVE_GEMINI_TESTS=1 and provide a real GEMINI_API_KEY to run this integration test",
)
class LiveWeeklyInsightRetrievalTest(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.db = sessionmaker(bind=self.engine)()
        self.original_client = api.client

    def tearDown(self):
        api.client = self.original_client
        self.db.close()
        self.engine.dispose()

    def test_real_embeddings_retrieve_semantically_related_entry(self):
        user = User(google_id="live-retrieval-test-user")
        self.db.add(user)
        self.db.flush()

        related = JournalEntry(
            user_id=user.id,
            date=date(2026, 8, 20),
            content=(
                "Before giving presentations at work, I notice my heart racing "
                "and feel physically anxious."
            ),
            created_at=datetime(2026, 8, 20),
        )
        unrelated = JournalEntry(
            user_id=user.id,
            date=date(2026, 8, 10),
            content="I spent a quiet afternoon planting tomatoes in the garden.",
            created_at=datetime(2026, 8, 10),
        )
        self.db.add_all([related, unrelated])
        self.db.commit()

        api.client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
        try:
            matches = api._retrieve_similar_journal_entries(
                self.db,
                user.id,
                [
                    JournalEntry(
                        date=date(2026, 10, 12),
                        content=(
                            "I feel sick before my meeting today"
                        ),
                    )
                ],
                before_date=date(2026, 9, 21),
                limit=2,
            )
        finally:
            api.client = self.original_client

        self.assertTrue(matches, "Expected at least one semantically similar past entry")
        self.assertEqual(matches[0].id, related.id)


if __name__ == "__main__":
    unittest.main()
