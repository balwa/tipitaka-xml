# Tipiṭaka multi-script search — strategy evaluation

## Inputs that shape the design

- **Corpus**: 217 TEI XML files × 15 scripts ≈ 3.5 GB raw, UTF-16 LE.
- **Logical unit**: each `<p>` element is the natural search hit (paragraph / verse / heading).
- **Aligned across scripts**: VRI generates all 15 script folders from the Devanagari master, so paragraph N of `abh01a.att.xml` is the same passage in every script folder.
- **Hosting**: self-hosted, single VPS or container.
- **Input scripts accepted**: any of the 15.
- **Output scripts returned**: the script the user typed in **and** the script the UI is set to.
- **Query semantics**: exact + wildcard (`dhammacakka*`) + fuzzy/typo tolerance. Semantic = stretch goal.
- **Peak load**: ~10 QPS.
- **Index design constraint**: native scripts preserved in the index — no canonicalisation to a single Roman form.

## The shared design pattern

Because the index must preserve native scripts but the user can type in any script, the only viable pattern is **query-time fan-out via transliteration**:

```
user query ──► transliteration sidecar (Aksharamukha) ──► 15 script-specific query strings
                                                           │
                                                           ▼
                                            search engine matches against per-script fields
                                                           │
                                                           ▼
                                            return the hit's text in (search-script, ui-script)
```

Each engine document looks like:

```
{
  id:          "abh01a.att#p17",
  book:        "abh01a.att",
  p_idx:       17,
  rend:        "gatha1",
  text_deva:   "विपस्सना ...",
  text_romn:   "vipassanā ...",
  text_beng:   "ৱিপস্সনা ...",
  ... 12 more script fields ...
}
```

The transliteration library (Aksharamukha, MIT-licensed) is the same for every option below — so what varies between options is the **engine**, not the language layer.

## Options compared

| # | Engine                        | Flexibility | RAM @ 3.5 GB | Self-host $/mo (DigitalOcean-ish) | Wildcard | Fuzzy | Notes |
|---|-------------------------------|-------------|--------------|----------------------------------|----------|-------|-------|
| 1 | **Apache Solr** (current)     | High        | 4–8 GB       | $24–48                           | yes      | yes   | What you have. Drop-in upgrade path: add ICU + per-script analyzers. Old admin UI. |
| 2 | **Elasticsearch / OpenSearch**| **Highest** | 4–8 GB       | $24–48                           | yes      | yes (Damerau-Levenshtein) | Best linguistic toolbox: ICU plugin, edge-ngram, multi_match, highlighting, score boosts per field, future-proof for hybrid (dense_vector) search if you ever add semantic. |
| 3 | **Meilisearch**               | Med-High    | 200–500 MB   | $5–10                            | prefix   | yes (built-in)  | Tiny, fast, dead-simple. Wildcard limited to prefix; weaker on heavy boolean queries. |
| 4 | **Typesense**                 | Med-High    | 200–500 MB   | **$5–10**                        | prefix   | yes (built-in, configurable) | Same envelope as Meilisearch but C++, more predictable latency, multi-field weighting, decent typo tuning. |
| 5 | **Manticore Search**          | Medium      | 500 MB–1 GB  | $5–10                            | yes      | yes   | Sphinx fork, lean, MySQL-protocol. Smaller community, fewer linguistic plugins. |
| 6 | **PostgreSQL FTS + pg_trgm**  | Low-Med     | 500 MB       | $5                               | trigram  | trigram | Fine for a 3.5 GB corpus at 10 QPS. But you lose multi-script analyzers, scoring is crude, and adding fields means schema migrations. |
| 7 | **Vector / hybrid (Qdrant + multilingual embedder)** | **Semantic+** | 4 GB + GPU helpful | $50+             | n/a      | n/a   | Stretch-goal only. Embeds all 15 scripts in one vector space → cross-script semantic match for free. Heavy at index time, ongoing model cost. Best as an *augmentation* of #2 or #4, not a replacement. |

### Why these rank where they do

**Flexibility ranking** (1 = most flexible):

1. **Elasticsearch / OpenSearch** — query DSL lets you do `multi_match` across 15 fields with per-field boosts, mix wildcard + fuzzy + phrase in one request, return per-field highlights so you can show both the input-script hit and the UI-script hit from the same response. ICU normalization handles the diacritic-equivalence problem (`vipassana` ≈ `vipassanā`) cleanly.
2. **Solr** — same Lucene engine, same capability, but more ceremony to wire up and the surrounding tooling is older.
3. **Typesense / Meilisearch** — multi-field search works, but you give up regex, complex boolean nesting, and fine-grained analyzer chains. Fine for the current Solr feature set + fuzzy.
4. **Manticore** — capable but less ergonomic for the per-script multi-field pattern.
5. **Postgres FTS** — works, but you'd be hand-rolling much of what ES gives you free.

**Cost ranking** (1 = cheapest):

1. **Typesense** — single 200–500 MB process, runs comfortably on a $5/mo droplet, no JVM, no GC tuning. Slight edge over Meilisearch for predictability under load.
2. **Meilisearch** — basically tied with Typesense on cost, slightly more developer-friendly.
3. **Postgres** — if you already have one, nearly free; if not, comparable to Typesense.
4. **Manticore** — similar footprint, smaller ecosystem.
5. **Solr / Elasticsearch / OpenSearch** — JVM-based, want 4 GB+ heap, push you to the $24+/mo tier.
6. **Vector hybrid** — by far the most expensive both at index time and at query time.

## Picks

- **Top flexibility → Elasticsearch (option 2)**. OpenSearch is interchangeable here (Apache 2 fork); use it instead if you want to dodge Elastic's SSPL. Choose ES because it gives you ICU analyzers, wildcard + fuzzy + phrase in one query, per-field highlight, and a clean upgrade path to dense_vector for the semantic stretch goal — without ever pulling the index off-engine.
- **Top cost → Typesense (option 4)**. Runs on the smallest VPS, ships typo tolerance and prefix wildcard out of the box, no JVM. Loses some of the heavy linguistic kit from ES, but for the stated query semantics that's an acceptable trade. Meilisearch is a near-tie and you should swap it in if the Typesense API is awkward.

In both cases the **transliteration sidecar (FastAPI + Aksharamukha) is identical** — that's where the multi-script flexibility actually lives. Swapping engines later is mostly a few hundred lines.

## What's in this directory

```
search-experiments/
├── STRATEGY.md                       (this file)
├── flexibility-elasticsearch/        (option 2)
│   ├── docker-compose.yml
│   ├── Dockerfile                    (FastAPI sidecar: indexer + query API)
│   ├── requirements.txt
│   └── app/
│       ├── api.py                    (GET /search, POST /index)
│       ├── indexer.py                (reads UTF-16 XML, indexes per-script fields)
│       ├── translit.py               (Aksharamukha wrappers + script detection)
│       └── xml_parser.py             (TEI <p> extractor)
└── cost-typesense/                   (option 4)
    ├── docker-compose.yml
    ├── Dockerfile
    ├── requirements.txt
    └── app/
        ├── api.py
        ├── indexer.py
        ├── translit.py
        └── xml_parser.py
```

Both stacks accept an env var `INDEX_LIMIT=N` so you can index just N files first to validate the round-trip before committing to all 217.
