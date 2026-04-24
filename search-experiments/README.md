# Tipiṭaka multi-script search experiments

Two self-hosted, Dockerised prototypes for replacing the current
`search.tipitaka.org/solr/web` service with one that:

- accepts a query in **any of the 15 scripts** (deva / romn / beng / mymr /
  sinh / thai / cyrl / gujr / guru / khmr / knda / mlym / taml / telu / tibt),
- searches the **native scripts directly** (no canonicalisation — the index
  keeps each script's text in its own field),
- returns each hit in **two scripts** (the one the user typed in + the one
  their UI is set to),
- supports **exact, wildcard, and fuzzy** modes.

See **[STRATEGY.md](STRATEGY.md)** for the full evaluation of seven options
and why these two were picked.

## The two prototypes

| Folder                                                              | Pick for     | Engine          | RAM   | $/mo (typical VPS) |
|---------------------------------------------------------------------|--------------|-----------------|-------|---------------------|
| [`flexibility-elasticsearch/`](flexibility-elasticsearch/README.md) | Flexibility  | Elasticsearch 8 + ICU | 2–3 GB | $24–48 |
| [`cost-typesense/`](cost-typesense/README.md)                       | Cost         | Typesense       | 0.5 GB | **$5–10** |

Both use the **same multi-script pattern**:

```
user query ─► Aksharamukha sidecar ─► 15 transliterated query strings
                                       │
                                       ▼
                          search engine matches each against its own
                          per-script field (text_deva, text_romn, …)
                                       │
                                       ▼
                          merge / score / highlight in (input, ui) scripts
```

The transliteration sidecar code is identical between the two — engine choice
is orthogonal to language handling.

## Quick start

Pick one of the two stacks and:

```bash
cd search-experiments/flexibility-elasticsearch    # or cost-typesense
docker compose up --build

# In another terminal, smoke-test with the first 5 books:
curl -X POST 'http://localhost:8000/index?limit=5'

# Then open the toy UI:
open http://localhost:8000
```

Both stacks expose port 8000 for the search API and serve a small HTML
search box at `/`. Each container mounts the repo root read-only at
`/corpus`, so the indexer reads `deva/`, `romn/`, … directly from the
working tree.

## Sample queries to try

| Query string         | Mode      | What it should hit |
|----------------------|-----------|--------------------|
| `vipassana`          | fuzzy     | All `vipassanā`-containing passages, regardless of UI script. |
| `vipassanā`          | exact     | Diacritic-exact Roman match. |
| `विपस्सना`            | exact     | Same passages, queried in Devanagari. |
| `ৱিপস্সনা`            | exact     | Same passages, queried in Bengali. |
| `dhammacakka*`       | wildcard  | All forms starting with that prefix. |
| `dhamacakka`         | fuzzy     | Should still match `dhammacakka` (1 typo). |

## Stretch: semantic search

Both engines have a path to add this without a second cluster:

- Elasticsearch: add a `dense_vector` field, embed each paragraph with a
  multilingual model (e.g. `intfloat/multilingual-e5-large`), use
  `knn` query alongside the existing `bool/should`.
- Typesense: built-in hybrid search since v0.25.

Estimated additional cost: GPU-less embed run is a one-shot ~2–4 hour job
on a single CPU; query-time vector search adds ~30–50 ms latency at
this corpus size.
