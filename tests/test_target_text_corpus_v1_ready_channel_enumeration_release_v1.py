import copy
import json
import tempfile
import unittest
from pathlib import Path

from scripts.verify_target_text_corpus_v1_ready_channel_enumeration_release_v1 import verify


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs" / "target_text_corpus_v1_ready_channel_enumeration_release_v1.json"


class ReadyChannelEnumerationReleaseV1Tests(unittest.TestCase):
    def test_real_release_has_capacity_and_keeps_queue_unmaterialized(self) -> None:
        result = verify(CONFIG)
        self.assertEqual(result["status"], "PASS_TWO_READY_CHANNELS_CAPACITY_SUFFICIENT_QUEUE_MAY_BE_MATERIALIZED")
        self.assertEqual(result["checks"]["channel_count"], 2)
        self.assertEqual(result["checks"]["required_per_channel"], 35)
        self.assertTrue(all(count >= 35 for count in result["checks"]["eligible_after_all_exclusions"].values()))
        self.assertFalse(result["decision"]["candidate_queue_created"])
        self.assertEqual(result["safety_contract"]["candidates_selected"], 0)
        self.assertFalse(result["decision"]["training_allowed"])

    def test_open_network_gate_is_rejected(self) -> None:
        config = json.loads(CONFIG.read_text(encoding="utf-8"))
        tampered = copy.deepcopy(config)
        tampered["decision"]["network_access_allowed"] = True
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", dir=ROOT / "configs", encoding="utf-8", delete=False) as handle:
            json.dump(tampered, handle)
            path = Path(handle.name)
        try:
            with self.assertRaisesRegex(PermissionError, "network_access_allowed"):
                verify(path)
        finally:
            path.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
