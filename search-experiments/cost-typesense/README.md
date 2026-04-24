# Cost option — Typesense + Aksharamukha

Typesense is a single C++ binary that holds the index in memory, with built-in
typo tolerance and prefix search. The same FastAPI sidecar from the ES build
runs Aksharamukha to fan a query out across all 15 scripts.

## Run

```bash
cd search-experiments/cost-typesense
docker compose up --build
```

First boot takes ~30 s (Typesense is fast to start).

## Index the corpus

```bash
# Smoke test:
curl -X POST 'http://localhost:8000/index?limit=5'

# Full corpus:
curl -X POST 'http://localhost:8000/index'
```

Expect ~3 min for the full corpus and ~700 MB of disk.

## Try it

```bash
open http://localhost:8000
# or:
curl 'http://localhost:8000/search?q=vipassana&ui_script=deva' | jq
curl 'http://localhost:8000/search?q=विपस्सना&ui_script=romn&mode=exact' | jq
curl 'http://localhost:8000/search?q=dhammacakka&mode=wildcard&ui_script=thai' | jq
```

## Where this gives up vs. Elasticsearch

| Feature                | ES build                    | Typesense build              |
|------------------------|-----------------------------|------------------------------|
| Memory @ full corpus   | ~2–3 GB                     | **~400–700 MB**              |
| Cold start             | ~90 s                       | **~5 s**                     |
| Wildcard               | full glob (`*foo*`)         | **prefix only** (`foo*`)     |
| Fuzzy                  | edit-distance (`AUTO`)      | num_typos (1 or 2)           |
| Per-script analyzers   | yes (custom + ICU)          | one built-in tokenizer       |
| Highlighting           | per-field, multi-fragment   | per-field, single snippet    |
| Stretch: vector search | dense_vector field          | hybrid search since v0.25    |

For a 3.5 GB corpus + ~10 QPS peak, the Typesense option fits on a $5–10/mo
VPS. The ES option needs $24+/mo because of JVM heap.

## Tuning knobs

| Env var               | Default       | Notes                              |
|-----------------------|---------------|------------------------------------|
| `TYPESENSE_API_KEY`   | `devkey`      | Set this in any non-toy deployment.|
| `COLLECTION`          | `tipitaka`    |                                    |
| `CORPUS_ROOT`         | `/corpus`     | Where script folders live in container. |
