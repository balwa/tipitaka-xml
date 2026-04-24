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


def _read_utf16(path: Path) -> bytes:
    """Read raw bytes; lxml will detect BOM and decode."""
    return path.read_bytes()


def parse_paragraphs(path: Path) -> list[Paragraph]:
    """Return one Paragraph per <p> element, in document order."""
    root = etree.fromstring(_read_utf16(path))
    out: list[Paragraph] = []
    for i, p in enumerate(root.iter("p")):
        # itertext flattens out <pb/>, <hi>, etc. — gives us the visible text.
        text = "".join(p.itertext()).strip()
        if not text:
            continue
        rend = p.get("rend") or ""
        out.append(Paragraph(p_idx=i, rend=rend, text=text))
    return out


def list_books(script_dir: Path, limit: int | None = None) -> list[str]:
    """Sorted list of book ids (filename stem) under one script directory."""
    files = sorted(script_dir.glob("*.xml"))
    if limit is not None:
        files = files[:limit]
    return [f.stem for f in files]
