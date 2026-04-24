"""FastAPI sidecar over Typesense — same query-fan-out pattern as the ES build."""
from __future__ import annotations

import os
from typing import Literal

import typesense
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse

from indexer import COLLECTION, reindex
from translit import ALL_SCRIPTS, detect_script, fan_out

TS_HOST = os.environ.get("TYPESENSE_HOST", "typesense")
TS_PORT = int(os.environ.get("TYPESENSE_PORT", "8108"))
TS_KEY = os.environ.get("TYPESENSE_API_KEY", "devkey")

client = typesense.Client({
    "nodes": [{"host": TS_HOST, "port": TS_PORT, "protocol": "http"}],
    "api_key": TS_KEY,
    "connection_timeout_seconds": 30,
})

app = FastAPI(title="Tipitaka multi-script search (Typesense)")


@app.get("/health")
def health() -> dict:
    try:
        client.collections[COLLECTION].retrieve()
        exists = True
    except typesense.exceptions.ObjectNotFound:
        exists = False
    return {"typesense": True, "collection_exists": exists}


@app.post("/index")
def post_index(limit: int | None = Query(None, description="Index only the first N books")) -> dict:
    return reindex(client, limit=limit)


@app.get("/search")
def search(
    q: str = Query(..., min_length=1),
    input_script: str | None = Query(None),
    ui_script: str = Query("deva"),
    mode: Literal["exact", "wildcard", "fuzzy"] = Query("fuzzy"),
    size: int = Query(20, ge=1, le=100),
) -> dict:
    if input_script and input_script not in ALL_SCRIPTS:
        raise HTTPException(400, f"Unknown input_script {input_script!r}")
    if ui_script not in ALL_SCRIPTS:
        raise HTTPException(400, f"Unknown ui_script {ui_script!r}")

    src = input_script or detect_script(q)
    expanded = fan_out(q, src=src)

    # Typesense does multi-search natively: one HTTP call, N independent
    # queries, results merged client-side. Each per-script query searches its
    # own field with the script-specific query string.
    queries: list[dict] = []
    for script, q_str in expanded.items():
        per_query = {
            "collection": COLLECTION,
            "q": q_str,
            "query_by": f"text_{script}",
            "include_fields": f"id,book,p_idx,rend,text_{script},text_{ui_script}",
            "highlight_fields": f"text_{script},text_{ui_script}",
            "highlight_full_fields": f"text_{script},text_{ui_script}",
            "per_page": size,
        }
        if mode == "exact":
            per_query["num_typos"] = 0
            per_query["prefix"] = False
        elif mode == "wildcard":
            per_query["num_typos"] = 0
            per_query["prefix"] = True       # Typesense's idiom for trailing-wildcard
            per_query["q"] = q_str.replace("*", "")
        else:  # fuzzy
            per_query["num_typos"] = 2
            per_query["prefix"] = True
        queries.append(per_query)

    res = client.multi_search.perform({"searches": queries}, {})

    # Merge: dedupe by id, keep best text_match score across the per-script results.
    merged: dict[str, dict] = {}
    for sub, script in zip(res["results"], expanded.keys()):
        for h in sub.get("hits", []):
            doc = h["document"]
            doc_id = doc["id"]
            score = h.get("text_match", 0)
            existing = merged.get(doc_id)
            if existing and existing["_score"] >= score:
                continue
            hl = {item.get("field"): item for item in h.get("highlights", [])}
            src_field = f"text_{src}"
            ui_field = f"text_{ui_script}"
            merged[doc_id] = {
                "id": doc_id,
                "_score": score,
                "_matched_via_script": script,
                "book": doc.get("book"),
                "p_idx": doc.get("p_idx"),
                "rend": doc.get("rend"),
                "input_script_text": doc.get(src_field, ""),
                "ui_script_text": doc.get(ui_field, ""),
                "input_script_highlight": (hl.get(src_field) or {}).get("snippet"),
                "ui_script_highlight": (hl.get(ui_field) or {}).get("snippet"),
            }

    hits = sorted(merged.values(), key=lambda d: d["_score"], reverse=True)[:size]
    return {
        "query": q,
        "detected_script": src,
        "ui_script": ui_script,
        "mode": mode,
        "expanded_queries": expanded,
        "total": len(hits),
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
<h1>Tipiṭaka multi-script search <small>(Typesense)</small></h1>
<form onsubmit="go(event)">
<input id="q" size="40" placeholder="vipassana / विपस्सना / ৱিপস্সনা ..." autofocus>
<select id="ui">{options}</select>
<select id="mode"><option>fuzzy</option><option>exact</option><option>wildcard</option></select>
<button>Search</button>
</form>
<p><small>Try: <code>vipassana</code>, <code>vipassanā</code>, <code>विपस्सना</code>, <code>dhammacakka</code> + wildcard mode for prefix.</small></p>
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
  out.innerHTML=`<p class="meta">${{j.total}} hits — input=${{j.detected_script}}, ui=${{j.ui_script}}, mode=${{j.mode}}</p>`+
    j.hits.map(h=>`<div class="hit">
      <div class="meta">${{h.book}} · p${{h.p_idx}} · ${{h.rend}} · matched-via ${{h._matched_via_script}} · score ${{h._score}}</div>
      <div><b>${{j.detected_script}}:</b> ${{(h.input_script_highlight||h.input_script_text||'').slice(0,400)}}</div>
      <div><b>${{j.ui_script}}:</b> ${{(h.ui_script_highlight||h.ui_script_text||'').slice(0,400)}}</div>
    </div>`).join('');
}}
</script></body></html>"""
