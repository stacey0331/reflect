import os
import unittest
from datetime import date

os.environ.setdefault("GEMINI_API_KEY", "test-key")

import backend.api as api


class CreateJournalEntryTest(unittest.TestCase):
    def test_returns_saved_entry_when_event_detection_fails(self):
        db = type("FakeDB", (), {})()
        db.query = lambda *args, **kwargs: type(
            "Query",
            (),
            {"filter": lambda *a, **k: type("Filter", (), {"first": lambda *aa, **kk: None})()},
        )()
        db.add = lambda *_args, **_kwargs: None
        db.commit = lambda *_args, **_kwargs: None
        db.refresh = lambda *_args, **_kwargs: None
        db.rollback = lambda *_args, **_kwargs: None

        def explode(*_args, **_kwargs):
            raise RuntimeError("event detection exploded")

        original = api._upsert_event_candidate_from_entry
        api._upsert_event_candidate_from_entry = explode
        try:
            result = api.create_journal_entry(
                api.JournalEntryCreate(
                    date=date(2026, 9, 28),
                    content="I broke up with my partner and it wrecked me.",
                ),
                db=db,
            )
        finally:
            api._upsert_event_candidate_from_entry = original

        self.assertEqual(result["date"], "2026-09-28")
        self.assertEqual(result["content"], "I broke up with my partner and it wrecked me.")


if __name__ == "__main__":
    unittest.main()
