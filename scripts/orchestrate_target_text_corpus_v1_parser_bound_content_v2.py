"""Owner-authorized parser-bound orchestrator with a committed-QA preflight."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone

from scripts.http_transport_target_text_corpus_v1_parser_bound_content_v2 import (
    authorize_live_transport_v2,
    execution_preflight_v2,
    live_transport_v2,
)
from scripts.orchestrate_target_text_corpus_v1_parser_bound_content_v1 import (
    execute_with_injected_transport_for_test,
)
from scripts.process_target_text_corpus_v1_parser_bound_pdf_lifecycle_v1 import process_pdf_lifecycle
from scripts.verify_target_text_corpus_v1_parser_bound_content_release_v1 import RELEASE, ROOT


def execute_live_v2() -> dict:
    capability = authorize_live_transport_v2()
    release = json.loads(RELEASE.read_text(encoding="utf-8"))
    return execute_with_injected_transport_for_test(
        lambda resource: live_transport_v2(resource, capability),
        ROOT / release["planned_output"],
        ROOT / release["planned_partial"],
        pdf_processor=process_pdf_lifecycle,
        created_at=datetime.now(timezone.utc).astimezone().isoformat(),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--verify-only", action="store_true")
    group.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    if args.verify_only:
        print(json.dumps(execution_preflight_v2(), ensure_ascii=False, indent=2))
        return 0
    result = execute_live_v2()
    print(json.dumps(result["verification"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
