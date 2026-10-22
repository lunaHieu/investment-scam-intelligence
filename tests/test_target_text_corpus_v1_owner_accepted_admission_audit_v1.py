import hashlib
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "registry" / "analyses" / "target_text_corpus_v1_owner_accepted_admission_audit_v1.json"


class OwnerAcceptedAdmissionAuditV1Tests(unittest.TestCase):
    def test_audit_pins_inputs_and_keeps_all_records_outside_release(self) -> None:
        data = json.loads(REGISTRY.read_text(encoding="utf-8"))
        for item in data["inputs"] + data["implementation"]:
            path = Path(item["path"])
            if not path.is_absolute():
                path = ROOT / path
            self.assertTrue(path.is_file(), item["role"])
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), item["sha256"], item["role"])
        accepted = json.loads(Path(data["inputs"][1]["path"]).read_text(encoding="utf-8"))["records"]
        self.assertEqual(len(accepted), 42)
        self.assertTrue(all(row["ground_truth_status"] == "LEGITIMATE" for row in accepted))
        self.assertEqual(data["result"]["fully_v1_core_compliant_now"], 0)
        self.assertEqual(data["result"]["owner_accepted_labels_preserved"], 42)
        self.assertFalse(data["decision"]["group_split_allowed"])
        self.assertFalse(data["decision"]["training_allowed"])


if __name__ == "__main__":
    unittest.main()
