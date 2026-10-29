"""Exercise one fail-closed adversarial scenario per parser-bound resource."""

from __future__ import annotations

import copy
import json
import tempfile
from pathlib import Path

from scripts.dry_run_target_text_corpus_v1_parser_bound_content_v1 import (
    assemble_result,
    synthetic_payload,
    synthetic_transport,
)
from scripts.execute_target_text_corpus_v1_parser_bound_content_v1 import (
    TransportResponse,
    run_injected_transport_harness,
)
from scripts.verify_target_text_corpus_v1_parser_bound_content_release_v1 import (
    RELEASE,
)
from scripts.verify_target_text_corpus_v1_parser_bound_content_result_v1 import (
    verify_result,
)


SCENARIOS = {
    "PBC01":"CONTENT_TYPE_MISMATCH",
    "PBC02":"TRUNCATED_TREE",
    "PBC03":"INVALID_MANIFEST",
    "PBC04":"BYTE_CEILING_EXCEEDED",
    "PBC05":"PDF_MAGIC_MISMATCH",
    "PBC06":"FORBIDDEN_RECORD_KEY",
    "PBC07":"IMMUTABLE_REDIRECT_MISMATCH",
    "PBC08":"TRANSPORT_ERROR",
}


def adversarial_transport(target_id: str):
    def transport(resource: dict) -> TransportResponse:
        if resource["resource_id"] != target_id:
            return synthetic_transport(resource)
        if target_id == "PBC08":
            raise OSError("synthetic transport failure; must never be retained")
        baseline = synthetic_transport(resource)
        if target_id == "PBC01":
            return TransportResponse(200, baseline.final_url, {"Content-Type":"text/html"}, baseline.body)
        if target_id == "PBC02":
            body = json.dumps({"sha":"a" * 40, "truncated":True, "tree":[]}).encode()
            return TransportResponse(200, baseline.final_url, baseline.headers, body)
        if target_id == "PBC03":
            return TransportResponse(200, baseline.final_url, baseline.headers, b'{"release_version":"v1"}')
        if target_id == "PBC04":
            body = b"x" * (resource["maximum_bytes"] + 1)
            return TransportResponse(200, baseline.final_url, baseline.headers, body)
        if target_id == "PBC05":
            return TransportResponse(200, baseline.final_url, baseline.headers, b"not-a-pdf")
        if target_id == "PBC06":
            body = json.dumps({"id":"owner/repo", "sha":"a" * 40, "rows":[]}).encode()
            return TransportResponse(200, baseline.final_url, baseline.headers, body)
        if target_id == "PBC07":
            return TransportResponse(
                200,
                "https://huggingface.co/datasets/wrong/revision/QUICKSTART_GUIDE.md",
                baseline.headers,
                synthetic_payload(target_id),
                1,
            )
        raise AssertionError(f"Unknown scenario: {target_id}")
    return transport


def _assert_failure_shape(rows: list[dict], target_id: str) -> None:
    index = int(target_id[-2:]) - 1
    expected_failure = "TRANSPORT_ERROR" if target_id == "PBC08" else "PARSER_REJECTED"
    if any(row["outcome"] != "SUCCESS" for row in rows[:index]):
        raise ValueError(f"Preceding resource failed unexpectedly: {target_id}")
    if rows[index]["outcome"] != expected_failure:
        raise ValueError(f"Target resource did not fail closed: {target_id}")
    if any(row["outcome"] != "SKIPPED_AFTER_FAILURE" for row in rows[index + 1:]):
        raise ValueError(f"Following resource was not skipped: {target_id}")


def run_scenario(target_id: str) -> dict:
    release = json.loads(RELEASE.read_text(encoding="utf-8"))
    with tempfile.TemporaryDirectory(prefix=f"isi-parser-bound-adversarial-{target_id.lower()}-") as directory:
        root = Path(directory)
        journal = root / "journal.jsonl"
        honest_result_path = root / "honest-result.json"
        tampered_result_path = root / "tampered-result.json"
        rows = run_injected_transport_harness(
            release["resources"], adversarial_transport(target_id), journal
        )
        _assert_failure_shape(rows, target_id)
        honest = assemble_result(rows)
        honest_result_path.write_text(
            json.dumps(honest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        verified = verify_result(honest_result_path)
        if verified["status"] != "PASS_PARSER_BOUND_CONTENT_RESULT_VERIFIED":
            raise ValueError(f"Honest failure report was not verifiable: {target_id}")

        tampered = copy.deepcopy(honest)
        index = int(target_id[-2:]) - 1
        tampered["resources"][index]["outcome"] = "SUCCESS"
        tampered_result_path.write_text(
            json.dumps(tampered, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        try:
            verify_result(tampered_result_path)
        except (KeyError, TypeError, ValueError):
            tamper_rejected = True
        else:
            tamper_rejected = False
        if not tamper_rejected:
            raise ValueError(f"Tampered success was accepted: {target_id}")

        journal_text = journal.read_text(encoding="utf-8")
        events = [json.loads(line) for line in journal_text.splitlines()]
        if len(events) != 10:
            raise ValueError(f"Journal cardinality mismatch: {target_id}")
        if "synthetic transport failure" in journal_text:
            raise ValueError("Transport error message leaked into journal")
    return {
        "target_id":target_id,
        "scenario":SCENARIOS[target_id],
        "honest_failure_report_verified":True,
        "tampered_success_rejected":True,
        "journal_events":10,
        "network_operations":0,
        "temporary_artifacts_retained":False,
    }


def run_matrix() -> dict:
    results = [run_scenario(target_id) for target_id in SCENARIOS]
    return {
        "status":"PASS_ADVERSARIAL_FAILURE_MATRIX",
        "scenarios":len(results),
        "honest_failure_reports_verified":sum(item["honest_failure_report_verified"] for item in results),
        "tampered_successes_rejected":sum(item["tampered_success_rejected"] for item in results),
        "journal_events":sum(item["journal_events"] for item in results),
        "network_operations":0,
        "temporary_artifacts_retained":False,
        "results":results,
    }


def main() -> None:
    print(json.dumps(run_matrix(), ensure_ascii=False))


if __name__ == "__main__":
    main()
