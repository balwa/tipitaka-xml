"""Index TEI XML paragraphs into Elasticsearch with one field per script."""
from __future__ import annotations

import os
from pathlib import Path
from elasticsearch import Elasticsearch, helpers

from translit import ALL_SCRIPTS
from xml_parser import list_books, parse_paragraphs

INDEX_NAME = os.environ.get("INDEX_NAME", "tipitaka")
CORPUS_ROOT = Path(os.environ.get("CORPUS_ROOT", "/corpus"))


def _analyzer_for(script: str) -> dict:
    # ICU normalization handles diacritic / case / NFC issues across scripts.
    # An edge_ngram on top would let us serve prefix wildcards without the
    # leading-wildcard penalty, but we keep it simple: rely on ES wildcard
    # query, which is fine at 10 QPS.
    return {
        "type": "custom",
        "tokenizer": "icu_tokenizer",
        "filter": ["icu_folding", "lowercase"],
    }


def index_mapping() -> dict:
    properties: dict = {
        "book": {"type": "keyword"},
        "p_idx": {"type": "integer"},
        "rend": {"type": "keyword"},
    }
    analyzers: dict = {}
    for s in ALL_SCRIPTS:
        analyzers[f"a_{s}"] = _analyzer_for(s)
        properties[f"text_{s}"] = {
            "type": "text",
            "analyzer": f"a_{s}",
            "term_vector": "with_positions_offsets",
        }
    return {
        "settings": {
            "analysis": {"analyzer": analyzers},
            "number_of_shards": 1,
            "number_of_replicas": 0,
        },
        "mappings": {"properties": properties},
    }


def ensure_index(es: Elasticsearch, recreate: bool = False) -> None:
    if recreate and es.indices.exists(index=INDEX_NAME):
        es.indices.delete(index=INDEX_NAME)
    if not es.indices.exists(index=INDEX_NAME):
        es.indices.create(index=INDEX_NAME, body=index_mapping())


def _docs(limit: int | None):
    """Yield one document per (book, paragraph), with all 15 script fields populated.

    Alignment assumption: VRI generates every script folder from the Devanagari
    master, so paragraph N of book B has the same content across folders.
    We use romn/ as the canonical book list (any folder would do).
    """
    canonical = CORPUS_ROOT / "romn"
    books = list_books(canonical, limit=limit)

    # Pre-load paragraph lists per script. Memory: ~15 × ~1MB per file =
    # negligible; we process one book at a time.
    for book in books:
        per_script: dict[str, list] = {}
        for s in ALL_SCRIPTS:
            path = CORPUS_ROOT / s / f"{book}.xml"
            if not path.exists():
                per_script[s] = []
                continue
            per_script[s] = parse_paragraphs(path)

        # Use the longest list as the paragraph count; if scripts disagree,
        # we still emit a doc and leave missing fields blank.
        n = max((len(ps) for ps in per_script.values()), default=0)
        for i in range(n):
            doc: dict = {
                "book": book,
                "p_idx": i,
                "rend": "",
            }
            for s in ALL_SCRIPTS:
                ps = per_script[s]
                if i < len(ps):
                    doc[f"text_{s}"] = ps[i].text
                    if not doc["rend"]:
                        doc["rend"] = ps[i].rend
            yield {
                "_op_type": "index",
                "_index": INDEX_NAME,
                "_id": f"{book}#p{i}",
                "_source": doc,
            }


def reindex(es: Elasticsearch, limit: int | None = None) -> dict:
    ensure_index(es, recreate=True)
    ok, errs = helpers.bulk(es, _docs(limit), chunk_size=500, raise_on_error=False)
    es.indices.refresh(index=INDEX_NAME)
    return {"indexed": ok, "errors": len(errs) if isinstance(errs, list) else errs}
