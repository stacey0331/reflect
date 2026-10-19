# Weekly Retrieval Evaluation

`evaluate_weekly_retrieval.py` evaluates whether semantic search finds past journal entries that a person has labeled relevant to a query week. It embeds each query and eligible candidate once using Gemini, computes cosine similarity locally, and evaluates the top five predictions at every distinct observed similarity score. It reports precision, recall, F1, and the threshold with the best F1 on the supplied dataset. It evaluates retrieval only; it does not generate weekly insights.

`dataset.example.json` is a fictional sample to demonstrate the format and can be run directly. For a meaningful evaluation, copy it to `dataset.local.json` and replace the sample text with manually labeled examples. Keep candidates to entries dated before each query's `cutoff_date`; set `relevant` to `true` or `false` for each candidate. `dataset.local.json` is git-ignored so private journal text is not committed accidentally.

From the repository root, load the Gemini key and run either dataset. Thresholds are derived automatically, so a threshold list is not required:

```bash
set -a
source backend/.env.local
set +a
.venv/bin/python -m eval.evaluate_weekly_retrieval \
  --dataset eval/dataset.example.json
```

For your own labeled data:

```bash
cp eval/dataset.example.json eval/dataset.local.json
.venv/bin/python -m eval.evaluate_weekly_retrieval \
  --dataset eval/dataset.local.json
```

The script applies the date cutoff and newest-80 candidate limit, matching the production candidate pool, then evaluates up to five predictions per query. Precision, recall, and F1 are micro-averaged across queries. The highest-F1 threshold is selected on this same dataset, so treat it as a tuning result and validate the selected threshold on separate labeled examples before relying on it.

Running the evaluator calls Gemini's embedding API and may incur usage charges. The ordinary unit tests need no key and make no network calls.
