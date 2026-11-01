import unittest

from scripts.verify_pbc_diagnostic_executor_preflight_v1 import (
    EXPECTED_RESOURCE_IDS,
    EXPECTED_RATIONALES,
    EXPECTED_URLS,
    canonical_json_sha256,
    sha256_file,
    verify_candidate_bundle,
)
from scripts.verify_target_text_corpus_v1_parser_bound_content_diagnostic_release_v1 import ROOT


def synthetic_candidate():
    release = {
        "release_id": "ISI_TARGET_TEXT_CORPUS_V1_PARSER_BOUND_CONTENT_DIAGNOSTIC_RELEASE_V2",
        "status": "FROZEN_PREPARATION_EXECUTION_CLOSED",
        "prior_release_id": "ISI_TARGET_TEXT_CORPUS_V1_PARSER_BOUND_CONTENT_DIAGNOSTIC_RELEASE_V1",
        "prior_result_sha256": "5fcddbb84bb27867c139b972206e5483d78d8fefa91836cb5ffabf4f200fb07a",
        "created_at": "2026-11-01T08:00:00+07:00",
        "not_before": "2026-11-02T08:00:00+07:00",
        "resources": [
            {
                "resource_id": rid,
                "url": EXPECTED_URLS[rid],
                "technical_rationale_code": EXPECTED_RATIONALES[rid],
            }
            for rid in EXPECTED_RESOURCE_IDS
        ],
        "diagnostic_tooling": {
            "safe_contract_sha256": sha256_file(ROOT / "scripts/pbc_safe_diagnostic_contract_v1.py"),
            "offline_harness_sha256": sha256_file(ROOT / "scripts/pbc_offline_diagnostic_harness_v1.py"),
        },
        "execution_contract": {
            "maximum_get_requests": 2,
            "maximum_attempts_per_resource": 1,
            "minimum_request_interval_seconds": 60,
            "repeat_prior_release_allowed": False,
            "automatic_retry_allowed": False,
            "automatic_resume_allowed": False,
            "no_overwrite": True,
            "continue_after_row_local_parser_failure": True,
            "stop_on_transport_error": True,
            "stop_on_provider_http_error": True,
            "maximum_redirects": 0,
            "raw_response_retention_allowed": False,
            "dataset_file_download_allowed": False,
            "candidate_live_domain_access_allowed": False,
            "validation_or_test_open_allowed": False,
            "model_operations_allowed": False,
            "training_allowed": False,
        },
        "planned_output": "registry/analyses/pbc_diagnostic_preflight_synthetic_v2.json",
        "planned_partial": "registry/analyses/pbc_diagnostic_preflight_synthetic_v2.json.partial",
        "decision": {
            "network_execution_allowed_now": False,
            "evidence_acceptance_allowed": False,
            "dataset_acquisition_allowed": False,
            "labeling_allowed": False,
            "training_allowed": False,
        },
    }
    release_hash = canonical_json_sha256(release)
    qa = {
        "status": "PASS_CANDIDATE_RELEASE_PREFLIGHT_ONLY",
        "release_canonical_sha256": release_hash,
        "independent_verifier_passed": True,
        "decision": {"network_execution_allowed_now": False},
    }
    authorization = {
        "authorization": {
            "received": True,
            "scope": "EXECUTE_NEW_PBC_DIAGNOSTIC_RELEASE_V2",
            "release_id": release["release_id"],
            "release_canonical_sha256": release_hash,
            "resource_ids": EXPECTED_RESOURCE_IDS,
            "maximum_requests": 2,
            "maximum_attempts_per_resource": 1,
            "repeat_prior_release_allowed": False,
            "retry_after_failure_allowed": False,
        },
        "constraints": {
            "candidate_live_domain_access_allowed": False,
            "dataset_file_download_allowed": False,
            "raw_response_retention_allowed": False,
            "validation_or_test_open_allowed": False,
            "labeling_allowed": False,
            "model_operations_allowed": False,
            "training_allowed": False,
        },
    }
    return release, qa, authorization


class VerifyPbcDiagnosticExecutorPreflightV1Tests(unittest.TestCase):
    def test_consistent_candidate_passes_paperwork_preflight_but_execution_stays_closed(self):
        release, qa, authorization = synthetic_candidate()
        result = verify_candidate_bundle(release, qa, authorization)
        self.assertEqual(result["status"], "PASS_CANDIDATE_PREFLIGHT_EXECUTION_STILL_CLOSED")
        self.assertTrue(result["decision"]["candidate_package_consistent"])
        self.assertFalse(result["decision"]["network_execution_allowed"])
        self.assertTrue(result["decision"]["separate_execution_gate_still_required"])
        self.assertEqual(result["safety_contract"]["network_operations"], 0)
        self.assertFalse((ROOT / release["planned_output"]).exists())
        self.assertFalse((ROOT / release["planned_partial"]).exists())

    def test_old_release_id_is_rejected(self):
        release, qa, authorization = synthetic_candidate()
        release["release_id"] = release["prior_release_id"]
        result = verify_candidate_bundle(release, qa, authorization)
        self.assertIn("CANDIDATE_RELEASE_ID_NOT_NEW_V2", result["errors"])
        self.assertFalse(result["decision"]["network_execution_allowed"])

    def test_release_mutation_invalidates_qa_and_owner_hash_binding(self):
        release, qa, authorization = synthetic_candidate()
        release["resources"][0]["technical_rationale_code"] = "OTHER"
        result = verify_candidate_bundle(release, qa, authorization)
        self.assertIn("INDEPENDENT_QA_RELEASE_HASH_MISMATCH", result["errors"])
        self.assertIn("OWNER_AUTHORIZATION_RELEASE_HASH_MISMATCH", result["errors"])

    def test_reused_or_existing_output_path_fails_closed(self):
        release, qa, authorization = synthetic_candidate()
        release["planned_output"] = "registry/analyses/target_text_corpus_v1_parser_bound_content_diagnostic_result_v1.json"
        result = verify_candidate_bundle(release, qa, authorization)
        self.assertIn("PLANNED_OUTPUT_REUSES_IMMUTABLE_PATH", result["errors"])
        self.assertIn("PLANNED_OUTPUT_ALREADY_EXISTS", result["errors"])

    def test_unsafe_attempt_and_retention_settings_fail_closed(self):
        release, qa, authorization = synthetic_candidate()
        release["execution_contract"]["automatic_retry_allowed"] = True
        release["execution_contract"]["no_overwrite"] = False
        result = verify_candidate_bundle(release, qa, authorization)
        self.assertIn("EXECUTION_CONTRACT_NOT_CLOSED:automatic_retry_allowed", result["errors"])
        self.assertIn("NO_OVERWRITE_NOT_REQUIRED", result["errors"])

    def test_wrong_endpoint_or_weak_pacing_fails_closed(self):
        release, qa, authorization = synthetic_candidate()
        release["resources"][1]["url"] = "https://example.invalid/"
        release["execution_contract"]["minimum_request_interval_seconds"] = 30
        result = verify_candidate_bundle(release, qa, authorization)
        self.assertIn("RESOURCE_URL_NOT_PINNED_TO_APPROVED_ENDPOINT", result["errors"])
        self.assertIn("REQUEST_PACING_BELOW_MINIMUM", result["errors"])

    def test_missing_separate_owner_authorization_fails_closed(self):
        release, qa, authorization = synthetic_candidate()
        authorization["authorization"]["received"] = False
        result = verify_candidate_bundle(release, qa, authorization)
        self.assertIn("SEPARATE_OWNER_AUTHORIZATION_MISSING", result["errors"])
        self.assertFalse(result["decision"]["network_execution_allowed"])

    def test_missing_stop_policy_or_redirect_bound_fails_closed(self):
        release, qa, authorization = synthetic_candidate()
        release["execution_contract"]["stop_on_provider_http_error"] = False
        release["execution_contract"]["maximum_redirects"] = 1
        result = verify_candidate_bundle(release, qa, authorization)
        self.assertIn("FAIL_CLOSED_STOP_POLICY_MISSING:stop_on_provider_http_error", result["errors"])
        self.assertIn("REDIRECTS_MUST_BE_DISABLED", result["errors"])

    def test_path_traversal_and_naive_timestamp_are_rejected(self):
        release, qa, authorization = synthetic_candidate()
        release["planned_output"] = "registry/analyses/../../outside.json"
        release["created_at"] = "2026-11-01T08:00:00"
        result = verify_candidate_bundle(release, qa, authorization)
        self.assertIn("RELEASE_TIMESTAMPS_MUST_BE_TIMEZONE_AWARE", result["errors"])
        self.assertIn("PLANNED_PATH_INVALID_OR_ESCAPES_ROOT", result["errors"])
        self.assertFalse(result["decision"]["network_execution_allowed"])

    def test_not_before_cannot_precede_release_creation(self):
        release, qa, authorization = synthetic_candidate()
        release["not_before"] = "2026-10-31T08:00:00+07:00"
        result = verify_candidate_bundle(release, qa, authorization)
        self.assertIn("NOT_BEFORE_PRECEDES_RELEASE_CREATION", result["errors"])


if __name__ == "__main__":
    unittest.main()
