"""Markdown chunking for the clinic knowledge base (RAG ingestion).

Splits each docs/clinic/*.md file by its H2 (`## `) sections. Each chunk
keeps the document's H1 title plus its own heading for context, per the
plan agreed with Piero (Day 3, Phase 3).
"""

import re
from pathlib import Path

CLINIC_DOCS_DIR = Path(__file__).resolve().parents[1] / "docs" / "clinic"

_H2_SPLIT = re.compile(r"\n(?=## )")


def chunk_markdown_file(path: Path) -> list[dict]:
    """Split a clinic doc into one chunk per H2 (`## `) section.

    Returns a list of dicts with `source_file`, `heading`, and `content`
    (the H1 title + heading + section body, used as the embedding input).
    """
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    title = lines[0].lstrip("# ").strip()
    body = "\n".join(lines[1:]).strip()

    chunks = []
    intro = ""
    for part in _H2_SPLIT.split(body):
        part = part.strip()
        if not part:
            continue
        if part.startswith("## "):
            heading = part.splitlines()[0][3:].strip()
            section = f"{intro}\n\n{part}".strip() if intro else part
            chunks.append(
                {
                    "source_file": path.name,
                    "heading": heading,
                    "content": f"{title}\n\n{section}",
                }
            )
            intro = ""
        else:
            intro = part

    return chunks


def chunk_clinic_docs() -> list[dict]:
    """Chunk every clinic doc (excluding README.md) into RAG-ready sections."""
    chunks = []
    for path in sorted(CLINIC_DOCS_DIR.glob("*.md")):
        if path.name.lower() == "readme.md":
            continue
        chunks.extend(chunk_markdown_file(path))
    return chunks
