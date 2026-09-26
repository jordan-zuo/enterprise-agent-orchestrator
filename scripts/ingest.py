"""Inbox ingest. Converts data/inbox files into corpus entries.

Scans data/inbox for .txt and .md plus .pdf files. Doc id is the file stem.
Merges into data/corpus.json without dropping existing docs.
PDF text comes from pypdf. Scanned images with no text layer stay empty
and are reported as skipped.

Usage (repo root):
    python scripts/ingest.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

INBOX = ROOT / "data" / "inbox"
CORPUS_PATH = ROOT / "data" / "corpus.json"


def _read_pdf_text(path: Path) -> tuple[str, str]:
    try:
        from pypdf import PdfReader
    except ImportError:
        return "", "pypdf missing so PDF skipped"
    try:
        reader = PdfReader(str(path))
        parts = [(page.extract_text() or "") for page in reader.pages]
    except Exception as exc:
        return "", f"PDF read failed with {type(exc).__name__}"
    text = "\n".join(part.strip() for part in parts if part and part.strip())
    if not text.strip():
        return "", "no text layer found, scanned image likely"
    return text.strip(), ""


def main() -> dict:
    INBOX.mkdir(parents=True, exist_ok=True)
    try:
        corpus = json.loads(CORPUS_PATH.read_text(encoding="utf-8"))
    except FileNotFoundError:
        corpus = {}
    added = 0
    skipped: list[str] = []
    for path in sorted(INBOX.glob("*")):
        suffix = path.suffix.lower()
        if suffix not in (".txt", ".md", ".pdf"):
            continue
        doc_id = path.stem.strip().lower().replace(" ", "-")
        if not doc_id:
            continue
        if suffix == ".pdf":
            text, reason = _read_pdf_text(path)
            if not text:
                skipped.append(f"{path.name} with {reason}")
                continue
        else:
            text = path.read_text(encoding="utf-8", errors="strict").strip()
            if not text:
                continue
        if corpus.get(doc_id) != text:
            corpus[doc_id] = text
            added += 1
    CORPUS_PATH.write_text(json.dumps(corpus, indent=2), encoding="utf-8")
    print(f"inbox={INBOX} added_or_updated={added} total_docs={len(corpus)}")
    for item in skipped:
        print(f"skipped {item}")
    return {"added_or_updated": added, "total_docs": len(corpus), "skipped": skipped}


if __name__ == "__main__":
    main()
