import unittest

from scripts.audit_raw_cross_registry_provenance_v2 import finalize_v2


class RawCrossRegistryProvenanceV2Tests(unittest.TestCase):
    def base_report(self) -> dict:
        return {
            "audit_id": "V1",
            "status": "OLD",
            "summary": {
                "raw_file_count": 2,
                "verified_hash_pinned_chain_files": 2,
                "no_hash_pinned_chain_found_files": 0,
                "hash_mismatch_files": 0,
                "mismatched_raw_claim_count": 0,
                "missing_raw_claim_target_count": 1,
            },
            "decision": {},
        }

    def test_complete_existing_raw_is_separate_from_missing_historical_claim(self) -> None:
        report = finalize_v2(self.base_report())
        self.assertEqual(report["status"], "PASS_COMPLETE_EXISTING_RAW_PROVENANCE")
        self.assertTrue(report["decision"]["complete_existing_raw_file_provenance_chain"])
        self.assertFalse(report["decision"]["historical_missing_claim_targets_resolved"])
        self.assertEqual(report["decision"]["files_promoted"], 0)
        self.assertFalse(report["decision"]["training_allowed"])

    def test_any_existing_raw_gap_fails_closed(self) -> None:
        report = self.base_report()
        report["summary"]["verified_hash_pinned_chain_files"] = 1
        report["summary"]["no_hash_pinned_chain_found_files"] = 1
        finalized = finalize_v2(report)
        self.assertEqual(finalized["status"], "FAIL_EXISTING_RAW_PROVENANCE_INCOMPLETE")
        self.assertFalse(finalized["decision"]["complete_existing_raw_file_provenance_chain"])


if __name__ == "__main__":
    unittest.main()
