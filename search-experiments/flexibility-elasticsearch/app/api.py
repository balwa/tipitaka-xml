"""FastAPI sidecar: query-time fan-out across 15 per-script fields."""
from __future__ import annotations

import os
from typing import Literal

from elasticsearch import Elasticsearch
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse

from indexer import INDEX_NAME, reindex
from translit import ALL_SCRIPTS, detect_script, fan_out

ES_URL = os.environ.get("ES_URL", "http://elasticsearch:9200")
es = Elasticsearch(ES_URL, request_timeout=30)
app = FastAPI(title="Tipitaka multi-script search (Elasticsearch)")


@app.get("/health")
def health() -> dict:
    return {"es": es.ping(), "index_exists": es.indices.exists(index=INDEX_NAME)}


@app.post("/index")
def post_index(limit: int | None = Query(None, description="Index only the first N books")) -> dict:
    return reindex(es, limit=limit)


@app.get("/search")
def search(
    q: str = Query(..., min_length=1, description="Query in any of the 15 scripts"),
    input_script: str | None = Query(None, description="Override script detection"),
    ui_script: str = Query("deva", description="Script for the result snippet"),
    mode: Literal["exact", "wildcard", "fuzzy"] = Query("fuzzy"),
    size: int = Query(20, ge=1, le=100),
) -> dict:
    if input_script and input_script not in ALL_SCRIPTS:
        raise HTTPException(400, f"Unknown input_script {input_script!r}")
    if ui_script not in ALL_SCRIPTS:
        raise HTTPException(400, f"Unknown ui_script {ui_script!r}")

    src = input_script or detect_script(q)
    expanded = fan_out(q, src=src)

    # Build one clause per script field so each script searches its own index
    # field directly (no canonicalisation). multi_match is concise but doesn't
    # let us vary the *query string* per field, so we OR explicit clauses.
    should: list[dict] = []
    for script, q_str in expanded.items():
        field = f"text_{script}"
        if mode == "exact":
            should.append({"match_phrase": {field: q_str}})
        elif mode == "wildcard":
            # Allow either a user-supplied wildcard or auto-prefix.
            pat = q_str if "*" in q_str or "?" in q_str else f"{q_str}*"
            should.append({"wildcard": {field: {"value": pat, "case_insensitive": True}}})
        else:  # fuzzy
            should.append({
                "match": {
                    field: {"query": q_str, "fuzziness": "AUTO", "operator": "and"}
                }
            })

    # Highlight the field the user typed in AND the field they want to read.
    highlight_fields = {f"text_{src}": {}, f"text_{ui_script}": {}}

    body = {
        "size": size,
        "query": {"bool": {"should": should, "minimum_should_match": 1}},
        "highlight": {
            "fields": highlight_fields,
            "pre_tags": ["<mark>"],
            "post_tags": ["</mark>"],
            "fragment_size": 200,
            "number_of_fragments": 2,
        },
        "_source": ["book", "p_idx", "rend", f"text_{src}", f"text_{ui_script}"],
    }

    res = es.search(index=INDEX_NAME, body=body)
    hits = []
    for h in res["hits"]["hits"]:
        src_field = f"text_{src}"
        ui_field = f"text_{ui_script}"
        hl = h.get("highlight", {})
        hits.append({
            "id": h["_id"],
            "score": h["_score"],
            "book": h["_source"].get("book"),
            "p_idx": h["_source"].get("p_idx"),
            "rend": h["_source"].get("rend"),
            "input_script_text": h["_source"].get(src_field, ""),
            "ui_script_text": h["_source"].get(ui_field, ""),
            "input_script_highlight": hl.get(src_field, []),
            "ui_script_highlight": hl.get(ui_field, []),
        })
    return {
        "query": q,
        "detected_script": src,
        "ui_script": ui_script,
        "mode": mode,
        "expanded_queries": expanded,
        "total": res["hits"]["total"]["value"],
        "hits": hits,
    }


@app.get("/", response_class=HTMLResponse)
def home() -> str:
    options = "".join(f'<option value="{s}">{s}</option>' for s in ALL_SCRIPTS)
    return f"""<!doctype html><html><head><meta charset="utf-8"><title>Tipitaka search</title>
<style>
body{{font-family:system-ui;margin:2rem;max-width:900px}}
input,select,button{{font-size:16px;padding:6px}}
.hit{{border-bottom:1px solid #ddd;padding:0.6rem 0}}
mark{{background:#ffe9a8}}
.meta{{color:#666;font-size:0.85em}}
</style></head><body>
<h1>Tipiṭaka multi-script search</h1>
<form onsubmit="go(event)">
<input id="q" size="40" placeholder="vipassana / विपस्सना / ৱিপস্সনা ..." autofocus>
<select id="ui">{options}</select>
<select id="mode"><option>fuzzy</option><option>exact</option><option>wildcard</option></select>
<button>Search</button>
</form>
<p><small>Try: <code>vipassana</code>, <code>vipassanā</code>, <code>विपस्सना</code>, <code>dhammacakka*</code> (wildcard mode).</small></p>
<div id="r"></div>
<script>
async function go(e){{
  e.preventDefault();
  const q=document.getElementById('q').value;
  const ui=document.getElementById('ui').value;
  const mode=document.getElementById('mode').value;
  const r=await fetch(`/search?q=${{encodeURIComponent(q)}}&ui_script=${{ui}}&mode=${{mode}}`);
  const j=await r.json();
  const out=document.getElementById('r');
  out.innerHTML=`<p class="meta">${{j.total}} hits — detected input=${{j.detected_script}}, ui=${{j.ui_script}}, mode=${{j.mode}}</p>`+
    j.hits.map(h=>`<div class="hit">
      <div class="meta">${{h.book}} · p${{h.p_idx}} · ${{h.rend}} · score ${{h.score.toFixed(2)}}</div>
      <div><b>${{j.detected_script}}:</b> ${{(h.input_script_highlight[0]||h.input_script_text||'').slice(0,400)}}</div>
      <div><b>${{j.ui_script}}:</b> ${{(h.ui_script_highlight[0]||h.ui_script_text||'').slice(0,400)}}</div>
    </div>`).join('');
}}
</script></body></html>"""
