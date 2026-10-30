"""Extract bounded ScamBench paper sections; run with the bundled PDF runtime."""

from __future__ import annotations

import argparse
import importlib
import json
from pathlib import Path


SECTION_TERMS = ("data source", "data construction", "annotation", "human validation", "ethic", "privacy", "rewrite")
SAFE_DIAGNOSTIC_CODES = {
    "PDF_INVALID_MAGIC",
    "PDF_OPEN_OR_PARSE_ERROR",
    "PDF_PAGE_LIMIT_EXCEEDED",
    "PDF_PAGE_TEXT_EXTRACTION_ERROR",
    "PDF_EXTRACTION_RUNTIME_ERROR",
}


class PdfExtractionError(RuntimeError):
    def __init__(self, diagnostic_code: str):
        if diagnostic_code not in SAFE_DIAGNOSTIC_CODES:
            diagnostic_code = "PDF_EXTRACTION_RUNTIME_ERROR"
        self.diagnostic_code = diagnostic_code
        super().__init__(diagnostic_code)


def self_check() -> dict:
    # These packages intentionally belong to the pinned workspace PDF runtime,
    # not the project's core virtual environment.
    pdfplumber = importlib.import_module("pdfplumber")
    pypdf = importlib.import_module("pypdf")
    return {"status":"PASS_PDF_BACKEND","pypdf":pypdf.__version__,"pdfplumber":pdfplumber.__version__}


def extract(path: Path, maximum_pages: int = 24) -> dict:
    pdfplumber = importlib.import_module("pdfplumber")

    if not path.read_bytes()[:5] == b"%PDF-":
        raise PdfExtractionError("PDF_INVALID_MAGIC")
    sections = []
    try:
        with pdfplumber.open(path) as document:
            if len(document.pages) > maximum_pages:
                raise PdfExtractionError("PDF_PAGE_LIMIT_EXCEEDED")
            for page_number, page in enumerate(document.pages, start=1):
                try:
                    text = page.extract_text() or ""
                except Exception as error:
                    raise PdfExtractionError("PDF_PAGE_TEXT_EXTRACTION_ERROR") from error
                lowered = text.lower()
                matched = [term for term in SECTION_TERMS if term in lowered]
                if matched:
                    sections.append({"page":page_number,"matched_terms":matched,"text":text[:12000]})
    except PdfExtractionError:
        raise
    except Exception as error:
        raise PdfExtractionError("PDF_OPEN_OR_PARSE_ERROR") from error
    return {"page_count":len(document.pages),"sections":sections,"visual_review_status":"PENDING_REQUIRED"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("path", nargs="?", type=Path)
    parser.add_argument("--self-check", action="store_true")
    args = parser.parse_args()
    if args.self_check:
        output = self_check()
    else:
        try:
            output = extract(args.path)
        except Exception as error:
            # Emit only a fixed code. Never print exception text or PDF data.
            code = error.diagnostic_code if isinstance(error, PdfExtractionError) else "PDF_EXTRACTION_RUNTIME_ERROR"
            output = {
                "status": "PDF_EXTRACTION_REJECTED",
                "diagnostic_code": code,
            }
            print(json.dumps(output, ensure_ascii=False))
            raise SystemExit(2)
    print(json.dumps(output, ensure_ascii=False))
