"""Evaluate semantic retrieval quality and select a cosine cutoff.

Embeds each query and its eligible candidate entries with Gemini, computes
cosine similarities locally, then evaluates top-five predictions at each
observed similarity threshold. Reports precision, recall, F1, and the best-F1
threshold for cosine similarities. Requires a labeled JSON dataset and a real GEMINI_API_KEY.
"""

import argparse
import json
import math
import os
from datetime import date
from types import SimpleNamespace


DEFAULT_DATASET = os.path.join(os.path.dirname(__file__), "dataset.local.json")


def eligible_candidates(query, max_candidates=80):
    cutoff_date = date.fromisoformat(query["cutoff_date"])
    candidates = [
        candidate
        for candidate in query["candidates"]
        if date.fromisoformat(candidate["date"]) < cutoff_date
    ]
    candidates.sort(key=lambda candidate: candidate["date"], reverse=True)
    return candidates[:max_candidates]


def calculate_metrics(true_positives, false_positives, false_negatives):
    precision_denominator = true_positives + false_positives
    recall_denominator = true_positives + false_negatives
    precision = true_positives / precision_denominator if precision_denominator else 0.0
    recall = true_positives / recall_denominator if recall_denominator else 0.0
    f1 = (
        2 * precision * recall / (precision + recall)
        if precision + recall
        else 0.0
    )
    return {"precision": precision, "recall": recall, "f1": f1}


def parse_thresholds(value):
    try:
        thresholds = [float(item) for item in value.split(",")]
    except ValueError as exc:
        raise argparse.ArgumentTypeError("Thresholds must be comma-separated numbers") from exc
    if not thresholds or any(threshold < 0 or threshold > 1 for threshold in thresholds):
        raise argparse.ArgumentTypeError("Each threshold must be between 0 and 1")
    return thresholds


def score_candidates(entries, entry_embeddings, query_embeddings):
    scored = []
    for entry, entry_embedding in zip(entries, entry_embeddings):
        entry_norm = math.sqrt(sum(value * value for value in entry_embedding))
        if not entry_norm:
            continue

        best_similarity = 0.0
        for query_embedding in query_embeddings:
            if len(query_embedding) != len(entry_embedding):
                continue
            query_norm = math.sqrt(sum(value * value for value in query_embedding))
            if not query_norm:
                continue
            similarity = sum(
                left * right for left, right in zip(entry_embedding, query_embedding)
            ) / (entry_norm * query_norm)
            best_similarity = max(best_similarity, similarity)
        scored.append((entry, best_similarity))

    scored.sort(key=lambda item: item[1], reverse=True)
    return scored


def derive_thresholds(similarity_scores):
    thresholds = {0.0, 1.0}
    thresholds.update(score for score in similarity_scores if 0.0 <= score <= 1.0)
    return sorted(thresholds)


def _load_api():
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key or api_key == "test-key":
        raise RuntimeError("Load a real GEMINI_API_KEY before running this evaluation")

    os.environ.setdefault("DATABASE_URL", "sqlite://")
    import backend.api as api

    return api


def _embed(api, text_or_texts, task_type):
    response = api.client.models.embed_content(
        model="gemini-embedding-001",
        contents=text_or_texts,
        config=api.types.EmbedContentConfig(task_type=task_type),
    )
    return [embedding.values for embedding in response.embeddings]


def evaluate(dataset, api, thresholds=None):
    query_results = []
    all_similarity_scores = []
    for query in dataset["queries"]:
        candidates = eligible_candidates(query)
        relevant_ids = {
            candidate["id"] for candidate in candidates if candidate["relevant"]
        }
        if not candidates:
            query_results.append(([], relevant_ids))
            continue

        query_embeddings = _embed(api, query["text"], "RETRIEVAL_QUERY")
        candidate_embeddings = _embed(
            api,
            [candidate["text"] for candidate in candidates],
            "RETRIEVAL_DOCUMENT",
        )
        if len(query_embeddings) != 1 or len(candidate_embeddings) != len(candidates):
            raise RuntimeError("Gemini returned an unexpected number of embeddings")

        candidate_entries = [
            SimpleNamespace(id=candidate["id"], date=candidate["date"], content=candidate["text"])
            for candidate in candidates
        ]
        scored_candidates = score_candidates(
            candidate_entries,
            candidate_embeddings,
            query_embeddings,
        )
        all_similarity_scores.extend(score for _entry, score in scored_candidates)
        query_results.append((scored_candidates, relevant_ids))

    thresholds = thresholds if thresholds is not None else derive_thresholds(all_similarity_scores)
    counts = {
        threshold: {"tp": 0, "fp": 0, "fn": 0, "retrieved": 0, "relevant": 0}
        for threshold in thresholds
    }

    for scored_candidates, relevant_ids in query_results:
        for threshold in thresholds:
            predicted_ids = [
                entry.id
                for entry, score in scored_candidates
                if score >= threshold
            ][:5]
            true_positives = len(set(predicted_ids) & relevant_ids)
            metric_counts = counts[threshold]
            metric_counts["tp"] += true_positives
            metric_counts["fp"] += len(predicted_ids) - true_positives
            metric_counts["fn"] += len(relevant_ids) - true_positives
            metric_counts["retrieved"] += len(predicted_ids)
            metric_counts["relevant"] += len(relevant_ids)

    return {
        threshold: {
            **calculate_metrics(values["tp"], values["fp"], values["fn"]),
            "retrieved": values["retrieved"],
            "relevant": values["relevant"],
        }
        for threshold, values in counts.items()
    }


def main():
    parser = argparse.ArgumentParser(description="Evaluate weekly journal retrieval thresholds")
    parser.add_argument("--dataset", default=DEFAULT_DATASET)
    parser.add_argument(
        "--thresholds",
        type=parse_thresholds,
        default=None,
        help="Optional comma-separated cosine thresholds; defaults to observed score boundaries",
    )
    args = parser.parse_args()

    with open(args.dataset, encoding="utf-8") as dataset_file:
        dataset = json.load(dataset_file)

    api = _load_api()
    results = evaluate(dataset, api, args.thresholds)
    best_threshold, best_metrics = max(
        results.items(),
        key=lambda item: (item[1]["f1"], item[1]["precision"], item[0]),
    )
    print(f"Evaluated {len(results)} thresholds derived from candidate cosine scores")
    print("threshold  precision  recall  f1    retrieved/relevant")
    for threshold, metrics in results.items():
        print(
            f"{threshold:9.6f}  {metrics['precision']:9.3f}  "
            f"{metrics['recall']:6.3f}  {metrics['f1']:5.3f}  "
            f"{metrics['retrieved']}/{metrics['relevant']}"
        )
    print(
        "Best F1 on this dataset: "
        f"threshold={best_threshold:.6f}, "
        f"precision={best_metrics['precision']:.3f}, "
        f"recall={best_metrics['recall']:.3f}, "
        f"f1={best_metrics['f1']:.3f}"
    )


if __name__ == "__main__":
    main()