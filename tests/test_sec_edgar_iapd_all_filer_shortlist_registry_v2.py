import hashlib
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "registry" / "analyses" / "sec_edgar_iapd_all_filer_shortlist_v2.json"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class SecEdgarIapdAllFilerShortlistRegistryV2Tests(unittest.TestCase):
    def test_registry_pins_artifacts_and_keeps_execution_gates_closed(self) -> None:
        registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
        self.assertEqual(registry["status"], "FROZEN_INDEPENDENTLY_VERIFIED_BOUNDED_DISJOINT_REVIEW_SHORTLIST_CAPTURE_BLOCKED")
        for item in registry["inputs"] + registry["implementation"] + registry["outputs"]:
            path = Path(item["path"])
            if not path.is_absolute():
                path = ROOT / path
            self.assertTrue(path.is_file(), item["path"])
            self.assertEqual(sha256_file(path), item["sha256"], item["path"])
        self.assertEqual(registry["findings"]["shortlist_rows"], 134)
        self.assertEqual(registry["findings"]["development_rows"], 107)
        self.assertEqual(registry["findings"]["external_holdout_rows"], 27)
        self.assertEqual(registry["findings"]["prior_host_overlap_count"], 0)
        self.assertEqual(registry["findings"]["cross_cohort_host_overlap_count"], 0)
        for gate in ("candidate_live_domain_access_allowed", "wayback_query_allowed", "artifact_capture_allowed", "labeling_allowed", "training_allowed"):
            self.assertFalse(registry["decision"][gate])


if __name__ == "__main__":
    unittest.main()
