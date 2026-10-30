"""Supplemental live orchestrator; execution remains closed without owner amendment."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone

from scripts.execute_target_text_corpus_v1_parser_bound_content_supplemental_v1 import execute_with_injected_transport_for_test
from scripts.http_transport_target_text_corpus_v1_parser_bound_content_supplemental_v1 import authorize_live_transport, execution_preflight, live_transport
from scripts.process_target_text_corpus_v1_parser_bound_pdf_lifecycle_v2 import process_pdf_lifecycle_v2
from scripts.verify_target_text_corpus_v1_parser_bound_content_release_v1 import ROOT
from scripts.verify_target_text_corpus_v1_parser_bound_content_supplemental_release_v1 import RELEASE


def execute_live() -> dict:
    capability = authorize_live_transport()
    release = json.loads(RELEASE.read_text(encoding="utf-8"))
    return execute_with_injected_transport_for_test(
        lambda resource: live_transport(resource, capability),
        process_pdf_lifecycle_v2,
        ROOT / release["planned_output"],
        ROOT / release["planned_partial"],
        created_at=datetime.now(timezone.utc).astimezone().isoformat(),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--verify-only", action="store_true")
    group.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    if args.verify_only:
        print(json.dumps(execution_preflight(), ensure_ascii=False, indent=2))
        return 0
    result = execute_live()
    print(json.dumps(result["verification"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
