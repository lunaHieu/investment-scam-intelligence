"""Capability-gated transport adapter for the owner-authorized V1 amendment."""

from __future__ import annotations

import json
import subprocess
import urllib.request
from pathlib import Path

from scripts.http_transport_target_text_corpus_v1_parser_bound_content_v1 import (
    NoRedirectHandler,
    fetch_with_injected_opener,
)
from scripts.verify_target_text_corpus_v1_parser_bound_content_execution_amendment_v1 import (
    AMENDMENT,
    PASS_STATUS,
    QA,
    ROOT,
    sha256_file,
    verify,
    verify_registered_qa,
)


_LIVE_CAPABILITY_V2 = object()


def _git(*arguments: str) -> str:
    return subprocess.run(
        ["git", *arguments], cwd=ROOT, check=True, capture_output=True, text=True, encoding="utf-8"
    ).stdout.strip()


def execution_preflight_v2() -> dict:
    result = verify()
    status_lines = [line for line in _git("status", "--porcelain=v1").splitlines() if line]
    head = _git("rev-parse", "HEAD")
    origin = _git("rev-parse", "origin/main")
    amendment = json.loads(AMENDMENT.read_text(encoding="utf-8"))
    qa_matches = verify_registered_qa()["valid"]
    ancestor = subprocess.run(
        ["git", "merge-base", "--is-ancestor", amendment["execution_binding"]["implementation_commit"], "HEAD"],
        cwd=ROOT,
    ).returncode == 0
    allowed = all((
        result.get("status") == PASS_STATUS,
        result.get("checks", {}).get("amendment_tracked") is True,
        result.get("checks", {}).get("independent_qa_tracked") is True,
        qa_matches,
        not status_lines,
        head == origin,
        ancestor,
        result.get("checks", {}).get("planned_outputs_absent") is True,
    ))
    return {
        "status": "PASS_EXECUTION_PREFLIGHT_OPEN" if allowed else "EXECUTION_PREFLIGHT_CLOSED",
        "amendment_verified": result.get("status") == PASS_STATUS,
        "amendment_tracked": result.get("checks", {}).get("amendment_tracked"),
        "independent_qa_tracked": result.get("checks", {}).get("independent_qa_tracked"),
        "independent_qa_matches": qa_matches,
        "working_tree_clean": not status_lines,
        "head_equals_origin_main": head == origin,
        "implementation_commit_is_ancestor": ancestor,
        "planned_outputs_absent": result.get("checks", {}).get("planned_outputs_absent"),
        "execution_allowed": allowed,
    }


def authorize_live_transport_v2() -> object:
    if execution_preflight_v2()["execution_allowed"] is not True:
        raise PermissionError("Parser-bound V2 live transport is closed by execution preflight")
    return _LIVE_CAPABILITY_V2


def live_transport_v2(resource: dict, capability: object):
    if capability is not _LIVE_CAPABILITY_V2:
        raise PermissionError("Missing parser-bound V2 live transport capability")
    opener = urllib.request.build_opener(NoRedirectHandler())
    return fetch_with_injected_opener(resource, opener)


def main() -> int:
    result = execution_preflight_v2()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["amendment_verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
