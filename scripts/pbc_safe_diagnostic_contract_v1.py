"""Hash-only, allowlisted diagnostics for a future PBC parser attempt.

This module is deliberately separate from the frozen V1 parser/executors. It
never performs I/O and returns no source values, key names, paths, or messages.
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any


SAFE_PDF_STAGES = frozenset({"PDFINFO", "SECTION_EXTRACTION", "PDFTOPPM_RENDER"})
SAFE_EXTRACTOR_CODES = frozenset(
    {
        "PDF_INVALID_MAGIC",
        "PDF_OPEN_OR_PARSE_ERROR",
        "PDF_PAGE_LIMIT_EXCEEDED",
        "PDF_PAGE_TEXT_EXTRACTION_ERROR",
        "PDF_EXTRACTION_RUNTIME_ERROR",
    }
)
SAFE_EXCEPTION_CLASSES = frozenset(
    {
        "AttributeError",
        "EOFError",
        "FileNotFoundError",
        "ImportError",
        "IndexError",
        "KeyError",
        "MemoryError",
        "ModuleNotFoundError",
        "OSError",
        "PermissionError",
        "PdfExtractionError",
        "RuntimeError",
        "SystemError",
        "SystemExit",
        "TimeoutError",
        "TypeError",
        "UnicodeDecodeError",
        "UnicodeError",
        "ValueError",
    }
)

SAFE_KEY_CATEGORIES = {
    "rows": "RECORD_COLLECTION",
    "row": "RECORD_FIELD",
    "content": "CONTENT_FIELD",
    "text": "CONTENT_FIELD",
    "message": "FREEFORM_MESSAGE",
    "examples": "EXAMPLE_COLLECTION",
    "preview": "PREVIEW_FIELD",
}

MAX_STDOUT_JSON_PARSE_BYTES = 64 * 1024
MAX_STDERR_CLASS_PARSE_BYTES = 4 * 1024
_EXCEPTION_LINE = re.compile(r"^([A-Za-z_][A-Za-z0-9_.]*):")


def _safe_bytes(value: str | bytes | None) -> bytes:
    if value is None:
        return b""
    if isinstance(value, bytes):
        return value
    return value.encode("utf-8", errors="replace")


def _configured_keys(value: Any, found: set[str] | None = None, seen: set[int] | None = None) -> set[str]:
    found = found if found is not None else set()
    seen = seen if seen is not None else set()
    if isinstance(value, (dict, list)):
        identity = id(value)
        if identity in seen:
            return found
        seen.add(identity)
    if isinstance(value, dict):
        for key, child in value.items():
            if isinstance(key, str):
                found.add(key.lower())
            _configured_keys(child, found, seen)
    elif isinstance(value, list):
        for child in value:
            _configured_keys(child, found, seen)
    return found


def classify_forbidden_key_categories(value: Any, forbidden_keys: list[str]) -> dict[str, Any]:
    """Return only safe categories; never return a matched key, path, or value."""

    forbidden = {key.lower() for key in forbidden_keys if isinstance(key, str)}
    matches = _configured_keys(value).intersection(forbidden)
    categories = sorted(
        {
            SAFE_KEY_CATEGORIES.get(key, "UNKNOWN_CONFIGURED_KEY")
            for key in matches
        }
    )
    return {
        "diagnostic_code": "FORBIDDEN_DATASET_KEY_PRESENT" if matches else None,
        "key_categories": categories,
    }


def _exception_class(stderr: bytes) -> str | None:
    text = stderr[-MAX_STDERR_CLASS_PARSE_BYTES:].decode("utf-8", errors="replace")
    final_line = next((line.strip() for line in reversed(text.splitlines()) if line.strip()), "")
    match = _EXCEPTION_LINE.match(final_line)
    if not match:
        return None
    class_name = match.group(1).rsplit(".", 1)[-1]
    return class_name if class_name in SAFE_EXCEPTION_CLASSES else "OTHER_EXCEPTION"


def diagnose_pdf_child_failure(stage: str, completed: Any) -> dict[str, Any]:
    """Build a bounded child-process diagnostic without retaining text output."""

    stdout = _safe_bytes(getattr(completed, "stdout", None))
    stderr = _safe_bytes(getattr(completed, "stderr", None))
    returncode = getattr(completed, "returncode", None)
    try:
        normalized_returncode = int(returncode)
    except (TypeError, ValueError):
        normalized_returncode = None

    child_code = None
    if len(stdout) <= MAX_STDOUT_JSON_PARSE_BYTES:
        try:
            payload = json.loads(stdout.decode("utf-8", errors="strict"))
            candidate = payload.get("diagnostic_code") if isinstance(payload, dict) else None
            if (
                isinstance(payload, dict)
                and payload.get("status") == "PDF_EXTRACTION_REJECTED"
                and candidate in SAFE_EXTRACTOR_CODES
            ):
                child_code = candidate
        except (UnicodeError, json.JSONDecodeError, TypeError, AttributeError):
            pass

    normalized_stage = stage if isinstance(stage, str) and stage in SAFE_PDF_STAGES else "UNKNOWN_STAGE"
    return {
        "status": "PDF_CHILD_FAILURE",
        "stage": normalized_stage,
        "returncode": normalized_returncode,
        "diagnostic_code": child_code or "PDF_CHILD_NONZERO_NO_STRUCTURED_DIAGNOSTIC",
        "child_exception_class": _exception_class(stderr),
        "stdout_bytes": len(stdout),
        "stdout_sha256": hashlib.sha256(stdout).hexdigest(),
        "stderr_bytes": len(stderr),
        "stderr_sha256": hashlib.sha256(stderr).hexdigest(),
    }
