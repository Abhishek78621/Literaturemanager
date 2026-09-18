"""
pdf_processor.py
-----------------
Extracts title, authors, year, DOI, and abstract text from a PDF so that
the rest of the pipeline (classification, summarization, embeddings) has
something to work with.

Strategy:
1. Try the PDF's embedded metadata (fast, often present for exported papers).
2. Fall back to reading the first page of text and using simple heuristics
   (first non-empty line = title candidate, "Abstract" keyword search, etc).

This intentionally stays heuristic and dependency-light (PyMuPDF only) so it
works fully offline, matching the "no API required for basic ingestion"
requirement in the spec. AI classification/summary happens in ai_service.py,
as a separate, optional step.
"""

import re
try:
    import pymupdf as fitz  # PyMuPDF's newer import name
except ImportError:
    import fitz  # older PyMuPDF versions


def extract(pdf_path: str) -> dict:
    doc = fitz.open(pdf_path)
    meta = doc.metadata or {}

    first_page_text = doc[0].get_text() if doc.page_count > 0 else ""
    full_text_sample = "\n".join(
        doc[i].get_text() for i in range(min(3, doc.page_count))
    )  # first ~3 pages is plenty for abstract + intro

    title = (meta.get("title") or "").strip()
    if not title or title.lower() in ("untitled", ""):
        title = _guess_title(first_page_text)

    authors = (meta.get("author") or "").strip()

    doi = _find_doi(full_text_sample)
    year = _find_year(full_text_sample)
    abstract = _find_abstract(full_text_sample)

    doc.close()

    return {
        "title": title or "Untitled",
        "authors": authors or None,
        "year": year,
        "journal": None,  # left for AI/manual enrichment; rarely reliable via regex
        "doi": doi,
        "abstract": abstract,
        "full_text_sample": full_text_sample[:6000],  # capped for downstream AI calls
    }


def _guess_title(first_page_text: str) -> str:
    lines = [l.strip() for l in first_page_text.splitlines() if l.strip()]
    for line in lines[:8]:
        # Skip obvious non-title lines (headers, page numbers, arXiv banners)
        if re.match(r"^(arxiv|preprint|page \d+|doi:)", line, re.I):
            continue
        # A title is usually 15-200 chars and not all-uppercase (which is a header)
        if 15 < len(line) < 200 and not line.isupper():
            return line
    return lines[0] if lines else "Untitled"


def _find_doi(text: str):
    m = re.search(r"10\.\d{4,9}/[-._;()/:A-Za-z0-9]+", text)
    return m.group(0).rstrip(".,") if m else None


def _find_year(text: str):
    years = re.findall(r"\b(19|20)\d{2}\b", text)
    # heuristic: first 4-digit year found in a 19xx/20xx range near the top of the doc
    m = re.search(r"\b(19|20)\d{2}\b", text)
    return m.group(0) if m else None


def _find_abstract(text: str):
    m = re.search(r"abstract[:\-]?\s*(.+?)(?:\n\s*\n|1\.?\s*introduction|keywords)",
                   text, re.I | re.S)
    if m:
        candidate = m.group(1).strip()
        candidate = re.sub(r"\s+", " ", candidate)
        if 40 < len(candidate) < 3000:
            return candidate
    return None
