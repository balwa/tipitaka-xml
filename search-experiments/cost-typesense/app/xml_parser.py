"""TEI XML reader for VRI Tipitaka files (UTF-16 LE encoded)."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from lxml import etree


@dataclass
class Paragraph:
    p_idx: int
    rend: str
    text: str


def parse_paragraphs(path: Path) -> list[Paragraph]:
    root = etree.fromstring(path.read_bytes())
    out: list[Paragraph] = []
    for i, p in enumerate(root.iter("p")):
        text = "".join(p.itertext()).strip()
        if not text:
            continue
        out.append(Paragraph(p_idx=i, rend=p.get("rend") or "", text=text))
    return out


def list_books(script_dir: Path, limit: int | None = None) -> list[str]:
    files = sorted(script_dir.glob("*.xml"))
    if limit is not None:
        files = files[:limit]
    return [f.stem for f in files]
