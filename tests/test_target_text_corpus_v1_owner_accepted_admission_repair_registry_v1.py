import json
import unittest
from pathlib import Path

from scripts.verify_target_text_corpus_v1_source_capacity_amendment_protocol import sha256_file


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "registry" / "analyses" / "target_text_corpus_v1_owner_accepted_admission_repair_v1.json"


class OwnerAcceptedAdmissionRepairRegistryV1Tests(unittest.TestCase):
    def test_registry_pins_protocol_result_qa_and_closed_gates(self) -> None:
        data = json.loads(REGISTRY.read_text(encoding="utf-8"))
        self.assertEqual(data["status"], "PASS_A4_PROTOCOL_AND_READINESS_QA_ZERO_RECORDS_ADMITTED")
        for item in data["inputs"] + data["implementation"] + data["outputs"]:
            path = Path(item["path"])
            if not path.is_absolute():
                path = ROOT / path
            self.assertTrue(path.is_file(), item)
            self.assertEqual(sha256_file(path), item["sha256"], item)
        self.assertEqual(data["result"]["records_audited"], 42)
        self.assertEqual(data["result"]["blockers_classified"], 9)
        self.assertEqual(data["result"]["fields_credited_now"], 0)
        self.assertEqual(data["result"]["v1_core_admitted_records"], 0)
        self.assertFalse(data["decision"]["repaired_manifest_created"])
        self.assertFalse(data["decision"]["training_allowed"])


if __name__ == "__main__":
    unittest.main()
