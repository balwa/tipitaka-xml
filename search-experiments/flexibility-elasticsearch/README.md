# Flexibility option — Elasticsearch + Aksharamukha

What this is: Elasticsearch (with the `analysis-icu` plugin) behind a small
FastAPI sidecar that runs Aksharamukha to fan a query out across all 15 scripts.
The index keeps native scripts intact — there's one `text_<script>` field per
script per document, and the query hits the matching field directly.

## Run

```bash
cd search-experiments/flexibility-elasticsearch
docker compose up --build
```

First boot takes ~2 min (ES warmup + ICU plugin install + Python deps).

## Index the corpus

```bash
# Smoke test with the first 5 books:
curl -X POST 'http://localhost:8000/index?limit=5'

# Full index (all 217 books × 15 scripts):
curl -X POST 'http://localhost:8000/index'
```

Indexing 217 books takes ~5–10 min on a laptop and uses ~1–1.5 GB of disk in
the `es_data` volume.

## Try it

Open <http://localhost:8000> for a minimal search UI, or hit the API:

```bash
curl 'http://localhost:8000/search?q=vipassana&ui_script=deva&mode=fuzzy' | jq
curl 'http://localhost:8000/search?q=विपस्सना&ui_script=romn&mode=exact' | jq
curl 'http://localhost:8000/search?q=dhammacakka*&ui_script=thai&mode=wildcard' | jq
```

Each hit returns the snippet in **two scripts**: the one the user typed in
(detected automatically) and the one their UI is set to.

## How the moving parts fit together

```
GET /search?q=vipassana&ui_script=deva
        │
        ▼
  detect_script("vipassana") = "romn"
        │
        ▼
  Aksharamukha fan-out → { romn: "vipassana", deva: "विपस्सन", beng: "ৱিপস্সন", ... }
        │
        ▼
  bool.should = [
    { match: text_romn  "vipassana"  fuzziness:AUTO },
    { match: text_deva  "विपस्सन"     fuzziness:AUTO },
    { match: text_beng  "ৱিপস্সন"     fuzziness:AUTO },
    ... 12 more clauses ...
  ]
        │
        ▼
  highlight: { text_romn: {}, text_deva: {} }   # input + ui scripts
```

## Why ES for "flexibility"

- ICU tokenizer + `icu_folding` filter → handles diacritic / NFC equivalence
  inside each script (so `vipassana` matches `vipassanā` in `text_romn`).
- One analyzer per script field → can tune each script independently later
  (e.g. add `edge_ngram` to a particular script for fast prefix wildcards).
- `multi_match` style fan-out + per-field highlighting in one round trip.
- `dense_vector` field type is a one-line addition the day you want the
  semantic stretch goal — same engine, no second cluster.

## Tuning knobs

| Env var       | Default              | Notes                                 |
|---------------|----------------------|---------------------------------------|
| `ES_URL`      | http://elasticsearch:9200 | Point at an external cluster if you want. |
| `INDEX_NAME`  | `tipitaka`           | Lets you keep multiple indexes side by side. |
| `CORPUS_ROOT` | `/corpus`            | Where the script folders live inside the API container. |
| `ES_JAVA_OPTS`| `-Xms2g -Xmx2g`      | Drop to 1g if your VPS is small. |
