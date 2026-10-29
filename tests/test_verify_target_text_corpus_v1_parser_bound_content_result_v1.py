import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from scripts.verify_target_text_corpus_v1_parser_bound_content_result_v1 import (
    LOCAL_QA,
    RELEASE,
    verify_result,
)


H40 = "a" * 40
H64 = "b" * 64


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def structured_output(resource_id: str) -> dict:
    return {
        "PBC01":{"sha":H40, "html_url":"https://github.com/example", "author_date":None, "committer_date":None, "tree_sha":H40, "parent_shas":[]},
        "PBC02":{"sha":H40, "truncated":False, "entries":[]},
        "PBC03":{"release_version":"v1", "generated_at":None, "files":[]},
        "PBC04":{"entries":[]},
        "PBC05":{"status":"PDF_VALIDATED_PENDING_BUNDLED_BACKEND_AND_VISUAL_REVIEW", "sha256":H64, "bytes":100},
        "PBC06":{"id":"owner/repo", "sha":H40, "lastModified":None, "private":False, "gated":False, "disabled":False, "tags":[], "license":None, "sibling_paths":[]},
        "PBC07":{"sections":{"files":"bounded documentation"}},
        "PBC08":{"commits":[]},
    }[resource_id]


def valid_result() -> dict:
    release = json.loads(RELEASE.read_text(encoding="utf-8"))
    rows = []
    for resource in release["resources"]:
        final_url = resource["url"]
        if resource["resource_id"] == "PBC07":
            final_url = "https://huggingface.co/datasets/trannguyenthaituan/vietnamese_sms_dataset/resolve/a90e2bd7e8df2376939658075ba8094dcee488ad/QUICKSTART_GUIDE.md"
        rows.append({
            "resource_id":resource["resource_id"],
            "source_endpoint_id":resource["source_endpoint_id"],
            "url":resource["url"],
            "final_url":final_url,
            "parser":resource["parser"],
            "outcome":"SUCCESS",
            "http_status":200,
            "content_type":resource["content_types"][0],
            "response_bytes":100,
            "response_sha256":H64,
            "structured_output":structured_output(resource["resource_id"]),
            "raw_response_retained":False,
        })
    return {
        "result_id":"SYNTHETIC_PARSER_BOUND_RESULT_V1",
        "inputs":[
            {"role":"release", "path":str(RELEASE.relative_to(RELEASE.parents[1])).replace("\\", "/"), "sha256":sha256(RELEASE)},
            {"role":"release_qa", "path":str(LOCAL_QA.relative_to(LOCAL_QA.parents[2])).replace("\\", "/"), "sha256":sha256(LOCAL_QA)},
        ],
        "resources":rows,
        "summary":{"resources":8, "success":8, "parser_rejected":0, "http_error":0, "transport_error":0, "skipped_after_failure":0, "response_bytes":800},
        "safety_contract":{"raw_responses_retained":0, "dataset_files_downloaded":0, "candidate_domain_access_operations":0, "labels_created":0, "validation_or_test_rows_opened":0, "model_operations":0, "training_allowed":False},
        "decision":{"evidence_acceptance_allowed":False, "dataset_acquisition_allowed":False, "training_allowed":False},
    }


class ParserBoundResultVerifierV1Tests(unittest.TestCase):
    def verify_fixture(self, value: dict) -> dict:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "result.json"
            path.write_text(json.dumps(value), encoding="utf-8")
            return verify_result(path)

    def test_valid_synthetic_result_passes(self):
        result = self.verify_fixture(valid_result())
        self.assertEqual(result["status"], "PASS_PARSER_BOUND_CONTENT_RESULT_VERIFIED")
        self.assertEqual(result["success"], 8)

    def test_resource_reordering_fails_closed(self):
        value = valid_result()
        value["resources"][0], value["resources"][1] = value["resources"][1], value["resources"][0]
        with self.assertRaises(ValueError):
            self.verify_fixture(value)

    def test_raw_body_field_fails_closed(self):
        value = valid_result()
        value["resources"][0]["response_body"] = "forbidden"
        with self.assertRaises(ValueError):
            self.verify_fixture(value)

    def test_record_like_field_fails_closed(self):
        value = valid_result()
        value["resources"][5]["structured_output"]["rows"] = []
        with self.assertRaises(ValueError):
            self.verify_fixture(value)

    def test_byte_ceiling_fails_closed(self):
        value = valid_result()
        value["resources"][3]["response_bytes"] = 1025
        value["summary"]["response_bytes"] = 1725
        with self.assertRaises(ValueError):
            self.verify_fixture(value)

    def test_pdf_visual_review_gate_cannot_be_bypassed(self):
        value = valid_result()
        value["resources"][4]["structured_output"]["status"] = "ACCEPTED"
        with self.assertRaises(ValueError):
            self.verify_fixture(value)

    def test_pdf_structured_identity_must_match_response(self):
        value = valid_result()
        value["resources"][4]["structured_output"]["sha256"] = "c" * 64
        with self.assertRaises(ValueError):
            self.verify_fixture(value)

    def test_release_hash_mismatch_fails_closed(self):
        value = valid_result()
        value["inputs"][0]["sha256"] = "0" * 64
        with self.assertRaises(ValueError):
            self.verify_fixture(value)

    def test_training_gate_cannot_open(self):
        value = valid_result()
        value["decision"]["training_allowed"] = True
        with self.assertRaises(ValueError):
            self.verify_fixture(value)

    def test_success_cannot_retain_diagnostic(self):
        value = valid_result()
        value["resources"][0]["diagnostic_code"] = "WARNING"
        with self.assertRaises(ValueError):
            self.verify_fixture(value)

    def test_http_error_cannot_claim_status_200(self):
        value = valid_result()
        failed = value["resources"][-1]
        failed["outcome"] = "HTTP_ERROR"
        failed["diagnostic_code"] = "HTTP_200"
        failed["structured_output"] = None
        value["summary"].update({"success":7, "http_error":1})
        with self.assertRaises(ValueError):
            self.verify_fixture(value)

    def test_transport_error_cannot_retain_response_metadata(self):
        value = valid_result()
        failed = value["resources"][-1]
        failed["outcome"] = "TRANSPORT_ERROR"
        failed["diagnostic_code"] = "TRANSPORT_OSERROR"
        failed["structured_output"] = None
        value["summary"].update({"success":7, "transport_error":1})
        with self.assertRaises(ValueError):
            self.verify_fixture(value)

    def test_parser_rejection_requires_diagnostic(self):
        value = valid_result()
        failed = value["resources"][-1]
        failed["outcome"] = "PARSER_REJECTED"
        failed["structured_output"] = None
        value["summary"].update({"success":7, "parser_rejected":1})
        with self.assertRaises(ValueError):
            self.verify_fixture(value)

    def test_success_after_failure_fails_closed(self):
        value = valid_result()
        failed = value["resources"][0]
        failed["outcome"] = "PARSER_REJECTED"
        failed["diagnostic_code"] = "CONTENT_TYPE_MISMATCH"
        failed["structured_output"] = None
        value["summary"]["success"] = 7
        value["summary"]["parser_rejected"] = 1
        with self.assertRaises(ValueError):
            self.verify_fixture(value)

    def test_skipped_row_cannot_claim_response_bytes(self):
        value = valid_result()
        failed = value["resources"][0]
        failed["outcome"] = "PARSER_REJECTED"
        failed["diagnostic_code"] = "CONTENT_TYPE_MISMATCH"
        failed["structured_output"] = None
        for row in value["resources"][1:]:
            row.update({
                "outcome":"SKIPPED_AFTER_FAILURE",
                "final_url":None,
                "http_status":None,
                "content_type":None,
                "response_bytes":0,
                "response_sha256":None,
                "structured_output":None,
                "diagnostic_code":"EARLIER_RESOURCE_FAILED",
            })
        value["resources"][1]["response_bytes"] = 1
        value["summary"].update({"success":0, "parser_rejected":1, "skipped_after_failure":7, "response_bytes":101})
        with self.assertRaises(ValueError):
            self.verify_fixture(value)


if __name__ == "__main__":
    unittest.main()
