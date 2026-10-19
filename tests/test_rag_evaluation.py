import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from eval.evaluate_weekly_retrieval import (
    calculate_metrics,
    derive_thresholds,
    eligible_candidates,
    evaluate,
    score_candidates,
)


class RagEvaluationTest(unittest.TestCase):
    def test_calculates_precision_recall_and_f1(self):
        metrics = calculate_metrics(true_positives=2, false_positives=1, false_negatives=2)

        self.assertAlmostEqual(metrics["precision"], 2 / 3)
        self.assertAlmostEqual(metrics["recall"], 1 / 2)
        self.assertAlmostEqual(metrics["f1"], 4 / 7)

    def test_candidate_pool_applies_cutoff_and_recent_entry_limit(self):
        query = {
            "cutoff_date": "2026-09-21",
            "candidates": [
                {"id": "old", "date": "2026-01-01"},
                {"id": "newer", "date": "2026-08-01"},
                {"id": "on-cutoff", "date": "2026-09-21"},
            ],
        }

        result = eligible_candidates(query, max_candidates=1)

        self.assertEqual([candidate["id"] for candidate in result], ["newer"])

    def test_derives_thresholds_from_unique_observed_scores(self):
        self.assertEqual(
            derive_thresholds([-0.2, 0.2, 0.5, 0.5, 1.2]),
            [0.0, 0.2, 0.5, 1.0],
        )

    def test_scores_candidates_with_cosine_similarity(self):
        candidates = [SimpleNamespace(id="near"), SimpleNamespace(id="far")]

        scores = score_candidates(
            candidates,
            [[0.8, 0.6], [0.6, 0.8]],
            [[1.0, 0.0]],
        )

        self.assertEqual([entry.id for entry, _score in scores], ["near", "far"])
        self.assertAlmostEqual(scores[0][1], 0.8)
        self.assertAlmostEqual(scores[1][1], 0.6)

    def test_evaluate_uses_observed_thresholds_and_reuses_embeddings(self):
        response = lambda vectors: SimpleNamespace(
            embeddings=[SimpleNamespace(values=vector) for vector in vectors]
        )
        embed_content = Mock(side_effect=[
            response([[1.0, 0.0]]),
            response([[0.8, 0.6], [0.6, 0.8]]),
        ])
        fake_api = SimpleNamespace(
            client=SimpleNamespace(models=SimpleNamespace(embed_content=embed_content)),
            types=SimpleNamespace(EmbedContentConfig=lambda **kwargs: kwargs),
        )
        dataset = {
            "queries": [{
                "cutoff_date": "2026-09-21",
                "text": "current query",
                "candidates": [
                    {"id": "near", "date": "2026-08-20", "text": "near", "relevant": True},
                    {"id": "far", "date": "2026-08-10", "text": "far", "relevant": False},
                ],
            }]
        }

        results = evaluate(dataset, fake_api)

        self.assertEqual(sorted(results), [0.0, 0.6, 0.8, 1.0])
        self.assertEqual(results[0.8]["precision"], 1.0)
        self.assertEqual(results[0.8]["recall"], 1.0)
        self.assertEqual(embed_content.call_count, 2)


if __name__ == "__main__":
    unittest.main()