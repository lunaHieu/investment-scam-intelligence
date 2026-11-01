"""Fixture-only integration harness for the PBC safe diagnostic contract.

This module accepts already-created synthetic objects. It does not read files,
open sockets, retain parser values, or authorize an acquisition run.
"""

from __future__ import annotations

from typing import Any

from scripts.execute_target_text_corpus_v1_parser_bound_content_v1 import (
    ParserRejection,
    parse_hf_commits,
)
from scripts.pbc_safe_diagnostic_contract_v1 import (
    classify_forbidden_key_categories,
    diagnose_pdf_child_failure,
)


SAFE_COMMIT_DIAGNOSTICS = frozenset(
    {
        "COMMIT_LIST_MISSING_OR_INVALID",
        "COMMIT_ENTRY_NOT_OBJECT",
        "COMMIT_ID_INVALID",
    }
)


def diagnose_pbc08_fixture(value: Any, forbidden_keys: list[str]) -> dict[str, Any]:
    """Exercise the existing commit parser, returning only safe diagnostics."""

    key_diagnostic = classify_forbidden_key_categories(value, forbidden_keys)
    if key_diagnostic["diagnostic_code"]:
        return {
            "status": "PARSER_REJECTED",
            "diagnostic_code": key_diagnostic["diagnostic_code"],
            "key_categories": key_diagnostic["key_categories"],
        }

    try:
        # Deliberately discard the parsed commit values; this is a diagnostic
        # preflight, not data extraction or evidence acceptance.
        parse_hf_commits(value, forbidden_keys)
    except ParserRejection as error:
        code = error.code if error.code in SAFE_COMMIT_DIAGNOSTICS else "COMMIT_METADATA_REJECTED"
        return {"status": "PARSER_REJECTED", "diagnostic_code": code, "key_categories": []}
    except (KeyError, TypeError, ValueError):
        return {
            "status": "PARSER_REJECTED",
            "diagnostic_code": "COMMIT_METADATA_SCHEMA_VALUE_ERROR",
            "key_categories": [],
        }
    return {"status": "PARSER_ACCEPTED", "diagnostic_code": None, "key_categories": []}


def diagnose_pbc05_child_fixture(stage: str, completed: Any) -> dict[str, Any]:
    """Exercise child-failure normalization without executing a subprocess."""

    return diagnose_pdf_child_failure(stage, completed)
