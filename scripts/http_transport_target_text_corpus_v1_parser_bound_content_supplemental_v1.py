"""Fail-closed live transport for the supplemental PBC05-PBC08 workflow."""

from __future__ import annotations

import json
import subprocess
import urllib.request

from scripts.http_transport_target_text_corpus_v1_parser_bound_content_v1 import NoRedirectHandler, fetch_with_injected_opener
from scripts.verify_target_text_corpus_v1_parser_bound_content_execution_amendment_v1 import tracked
from scripts.verify_target_text_corpus_v1_parser_bound_content_release_v1 import ROOT
from scripts.verify_target_text_corpus_v1_parser_bound_content_supplemental_execution_authorization_v1 import (
    AMENDMENT,
    AMENDMENT_PASS,
    AMENDMENT_QA,
    RELEASE_QA,
    PROTOCOL_PASS,
    verify_optional_amendment,
    verify_protocol,
)
from scripts.verify_target_text_corpus_v1_parser_bound_content_supplemental_release_v1 import RELEASE, verify as verify_release


_LIVE_CAPABILITY = object()


def _git(*arguments: str) -> str:
    return subprocess.run(["git", *arguments], cwd=ROOT, check=True, capture_output=True, text=True, encoding="utf-8").stdout.strip()


def execution_preflight() -> dict:
    protocol = verify_protocol()
    amendment = verify_optional_amendment()
    release = verify_release()
    status_lines = [line for line in _git("status", "--porcelain=v1").splitlines() if line]
    head = _git("rev-parse", "HEAD")
    origin = _git("rev-parse", "origin/main")
    release_tracked = tracked(RELEASE)
    release_qa_tracked = RELEASE_QA.is_file() and tracked(RELEASE_QA)
    amendment_tracked = AMENDMENT.is_file() and tracked(AMENDMENT)
    qa_tracked = AMENDMENT_QA.is_file() and tracked(AMENDMENT_QA)
    allowed = all((
        protocol.get("status") == PROTOCOL_PASS,
        amendment.get("status") == AMENDMENT_PASS,
        release.get("status") == "PASS_EXACT_PBC05_PBC08_SUPPLEMENTAL_RELEASE_EXECUTION_CLOSED",
        release_tracked,
        release_qa_tracked,
        amendment_tracked,
        qa_tracked,
        not status_lines,
        head == origin,
        release.get("checks", {}).get("outputs_absent") is True,
    ))
    return {
        "status": "PASS_SUPPLEMENTAL_EXECUTION_PREFLIGHT_OPEN" if allowed else "SUPPLEMENTAL_EXECUTION_PREFLIGHT_CLOSED",
        "protocol_verified": protocol.get("status") == PROTOCOL_PASS,
        "owner_amendment_verified": amendment.get("status") == AMENDMENT_PASS,
        "release_tracked": release_tracked,
        "release_qa_tracked": release_qa_tracked,
        "amendment_tracked": amendment_tracked,
        "amendment_qa_tracked": qa_tracked,
        "working_tree_clean": not status_lines,
        "head_equals_origin_main": head == origin,
        "planned_outputs_absent": release.get("checks", {}).get("outputs_absent"),
        "execution_allowed": allowed,
    }


def authorize_live_transport() -> object:
    if execution_preflight()["execution_allowed"] is not True:
        raise PermissionError("Supplemental live transport is closed by execution preflight")
    return _LIVE_CAPABILITY


def live_transport(resource: dict, capability: object):
    if capability is not _LIVE_CAPABILITY:
        raise PermissionError("Missing supplemental live transport capability")
    opener = urllib.request.build_opener(NoRedirectHandler())
    return fetch_with_injected_opener(resource, opener)


if __name__ == "__main__":
    print(json.dumps(execution_preflight(), ensure_ascii=False, indent=2))
