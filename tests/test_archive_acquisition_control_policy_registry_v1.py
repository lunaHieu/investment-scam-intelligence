import json
import unittest
from pathlib import Path

from scripts.execute_sec_edgar_iapd_v11_metadata_recovery_v2 import validate_amendment
from scripts.verify_target_text_corpus_v1_source_capacity_amendment_protocol import sha256_file


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "registry" / "analyses" / "archive_acquisition_control_policy_v1.json"
AMENDMENT = ROOT / "configs" / "sec_edgar_iapd_v11_metadata_recovery_execution_amendment_v2.json"
RELEASE = ROOT / "configs" / "sec_edgar_iapd_v11_metadata_recovery_release_v1.json"


class ArchiveAcquisitionControlPolicyRegistryV1Tests(unittest.TestCase):
    def test_registry_hashes_and_nonblocking_controls(self) -> None:
        registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
        self.assertEqual(registry["status"], "ACTIVE_NONBLOCKING_ADAPTIVE_RETRY_POLICY")
        self.assertFalse(registry["controls"]["project_blocked_by_quarantined_supplemental_artifact"])
        self.assertEqual(registry["controls"]["maximum_network_attempts_per_artifact_family"], 3)
        for item in registry["implementation"]:
            self.assertEqual(sha256_file(ROOT / item["path"]), item["sha256"])

    def test_v2_amendment_is_self_consistent(self) -> None:
        amendment = validate_amendment(AMENDMENT, RELEASE)
        self.assertTrue(amendment["execution_contract"]["historical_v1_executor_forbidden"])
        self.assertFalse(amendment["execution_contract"]["acquisition_lane_blocks_project"])


if __name__ == "__main__":
    unittest.main()
