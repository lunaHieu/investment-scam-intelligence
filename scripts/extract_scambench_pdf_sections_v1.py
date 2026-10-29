"""Extract bounded ScamBench paper sections; run with the bundled PDF runtime."""

from __future__ import annotations

import argparse
import importlib
import json
from pathlib import Path


SECTION_TERMS = ("data source", "data construction", "annotation", "human validation", "ethic", "privacy", "rewrite")


def self_check() -> dict:
    # These packages intentionally belong to the pinned workspace PDF runtime,
    # not the project's core virtual environment.
    pdfplumber = importlib.import_module("pdfplumber")
    pypdf = importlib.import_module("pypdf")
    return {"status":"PASS_PDF_BACKEND","pypdf":pypdf.__version__,"pdfplumber":pdfplumber.__version__}


def extract(path: Path, maximum_pages: int = 24) -> dict:
    pdfplumber = importlib.import_module("pdfplumber")

    if not path.read_bytes()[:5] == b"%PDF-":
        raise ValueError("PDF magic mismatch")
    sections = []
    with pdfplumber.open(path) as document:
        if len(document.pages) > maximum_pages:
            raise ValueError("PDF page limit exceeded")
        for page_number, page in enumerate(document.pages, start=1):
            text = page.extract_text() or ""
            lowered = text.lower()
            matched = [term for term in SECTION_TERMS if term in lowered]
            if matched:
                sections.append({"page":page_number,"matched_terms":matched,"text":text[:12000]})
    return {"page_count":len(document.pages),"sections":sections,"visual_review_status":"PENDING_REQUIRED"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("path", nargs="?", type=Path)
    parser.add_argument("--self-check", action="store_true")
    args = parser.parse_args()
    print(json.dumps(self_check() if args.self_check else extract(args.path), ensure_ascii=False))
