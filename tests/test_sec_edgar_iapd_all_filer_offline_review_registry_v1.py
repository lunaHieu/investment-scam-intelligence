import hashlib
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "registry" / "analyses" / "sec_edgar_iapd_all_filer_offline_review_v1.json"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class SecEdgarIapdAllFilerOfflineReviewRegistryV1Tests(unittest.TestCase):
    def test_registry_pins_review_and_keeps_network_label_model_gates_closed(self) -> None:
        registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
        self.assertEqual(registry["status"], "FROZEN_INDEPENDENTLY_VERIFIED_OFFLINE_PROVENANCE_AND_IDENTITY_REVIEW_NO_LABELS")
        for item in registry["inputs"] + registry["implementation"] + registry["outputs"]:
            path = Path(item["path"])
            if not path.is_absolute():
                path = ROOT / path
            self.assertTrue(path.is_file(), item["path"])
            self.assertEqual(sha256_file(path), item["sha256"], item["path"])
        self.assertEqual(registry["findings"]["exact_extracted_member_count"], 134)
        self.assertEqual(registry["findings"]["advance_to_capture_planning_review"], 115)
        self.assertEqual(registry["findings"]["hold_for_deeper_identity_review"], 19)
        self.assertEqual(registry["findings"]["ground_truth_labels_created"], 0)
        for gate in ("candidate_live_domain_access_allowed", "wayback_query_allowed", "artifact_capture_allowed", "labeling_allowed", "validation_or_test_opening_allowed", "training_allowed"):
            self.assertFalse(registry["decision"][gate])


if __name__ == "__main__":
    unittest.main()
