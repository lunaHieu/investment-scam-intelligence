"""Run the eight-resource parser-bound pipeline with synthetic responses only."""

from __future__ import annotations

import hashlib
import json
import tempfile
from collections import Counter
from pathlib import Path

from scripts.execute_target_text_corpus_v1_parser_bound_content_v1 import (
    LOCAL_QA,
    TransportResponse,
    run_injected_transport_harness,
)
from scripts.verify_target_text_corpus_v1_parser_bound_content_release_v1 import (
    RELEASE,
    ROOT,
)
from scripts.verify_target_text_corpus_v1_parser_bound_content_result_v1 import (
    verify_result,
)


H40 = "a" * 40
H64 = "b" * 64


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def synthetic_payload(resource_id: str) -> bytes:
    payloads: dict[str, bytes] = {
        "PBC01":json.dumps({
            "sha":H40,
            "html_url":"https://github.com/NexvisionLab/example/commit/" + H40,
            "commit":{"author":{"date":"2026-01-01T00:00:00Z"}, "committer":{"date":"2026-01-01T00:00:00Z"}, "tree":{"sha":H40}},
            "parents":[],
        }).encode(),
        "PBC02":json.dumps({
            "sha":H40,
            "truncated":False,
            "tree":[
                {"path":"metadata/checksums.json", "mode":"100644", "type":"blob", "sha":H40, "size":64},
                {"path":"data/records.jsonl", "mode":"100644", "type":"blob", "sha":H40, "size":999},
            ],
        }).encode(),
        "PBC03":json.dumps({"release_version":"v1", "generated_at":"2026-01-01", "files":[{"path":"metadata/file.json", "sha256":H64, "size":64}]}).encode(),
        "PBC04":json.dumps({"metadata/file.json":H64}).encode(),
        "PBC05":b"%PDF-1.7\nsynthetic dry-run bytes only\n%%EOF",
        "PBC06":json.dumps({
            "id":"owner/synthetic-metadata-only",
            "sha":H40,
            "lastModified":"2026-01-01T00:00:00Z",
            "private":False,
            "gated":False,
            "disabled":False,
            "tags":["language:vi"],
            "cardData":{"license":"unknown"},
            "siblings":[{"rfilename":"QUICKSTART_GUIDE.md"}],
        }).encode(),
        "PBC07":b"# Files\nMetadata files only.\n\n# Splits\nSplit names are documented without records.\n\n# License\nUnknown in dry run.\n",
        "PBC08":json.dumps([{"id":H40, "title":"Synthetic metadata commit", "createdAt":"2026-01-01T00:00:00Z", "authors":[{"username":"synthetic"}]}]).encode(),
    }
    return payloads[resource_id]


def synthetic_transport(resource: dict) -> TransportResponse:
    final_url = resource["url"]
    redirects = 0
    if resource["resource_id"] == "PBC07":
        final_url = (
            "https://huggingface.co/datasets/trannguyenthaituan/"
            "vietnamese_sms_dataset/resolve/"
            "a90e2bd7e8df2376939658075ba8094dcee488ad/QUICKSTART_GUIDE.md"
        )
        redirects = 1
    return TransportResponse(
        status_code=200,
        final_url=final_url,
        headers={"Content-Type":resource["content_types"][0]},
        body=synthetic_payload(resource["resource_id"]),
        redirect_count=redirects,
    )


def assemble_result(rows: list[dict]) -> dict:
    counts = Counter(row["outcome"] for row in rows)
    return {
        "result_id":"SYNTHETIC_END_TO_END_DRY_RUN_NOT_A_PROJECT_ARTIFACT",
        "inputs":[
            {"role":"release", "path":str(RELEASE.relative_to(ROOT)).replace("\\", "/"), "sha256":sha256_file(RELEASE)},
            {"role":"release_qa", "path":str(LOCAL_QA.relative_to(ROOT)).replace("\\", "/"), "sha256":sha256_file(LOCAL_QA)},
        ],
        "resources":rows,
        "summary":{
            "resources":len(rows),
            "success":counts["SUCCESS"],
            "parser_rejected":counts["PARSER_REJECTED"],
            "http_error":counts["HTTP_ERROR"],
            "transport_error":counts["TRANSPORT_ERROR"],
            "skipped_after_failure":counts["SKIPPED_AFTER_FAILURE"],
            "response_bytes":sum(row["response_bytes"] for row in rows),
        },
        "safety_contract":{
            "raw_responses_retained":0,
            "dataset_files_downloaded":0,
            "candidate_domain_access_operations":0,
            "labels_created":0,
            "validation_or_test_rows_opened":0,
            "model_operations":0,
            "training_allowed":False,
        },
        "decision":{
            "evidence_acceptance_allowed":False,
            "dataset_acquisition_allowed":False,
            "training_allowed":False,
        },
    }


def run_dry_run() -> dict:
    release = json.loads(RELEASE.read_text(encoding="utf-8"))
    with tempfile.TemporaryDirectory(prefix="isi-parser-bound-dry-run-") as directory:
        root = Path(directory)
        journal = root / "journal.jsonl"
        result_path = root / "result.json"
        rows = run_injected_transport_harness(
            release["resources"], synthetic_transport, journal
        )
        result_path.write_text(
            json.dumps(assemble_result(rows), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        verification = verify_result(result_path)
        journal_events = [
            json.loads(line)
            for line in journal.read_text(encoding="utf-8").splitlines()
        ]
        if len(journal_events) != 10:
            raise ValueError("Unexpected dry-run journal cardinality")
        if journal_events[0]["event"] != "RESERVED" or journal_events[-1]["event"] != "HARNESS_COMPLETE":
            raise ValueError("Dry-run journal lifecycle mismatch")
    return {
        "status":"PASS_SYNTHETIC_END_TO_END_DRY_RUN",
        "resources":verification["resources"],
        "success":verification["success"],
        "journal_events":10,
        "network_operations":0,
        "real_result_created":False,
        "evidence_acceptance_allowed":False,
        "dataset_acquisition_allowed":False,
        "training_allowed":False,
    }


def main() -> None:
    print(json.dumps(run_dry_run(), ensure_ascii=False))


if __name__ == "__main__":
    main()
