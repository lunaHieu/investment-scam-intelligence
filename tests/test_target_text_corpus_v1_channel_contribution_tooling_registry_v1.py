import hashlib
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "registry" / "analyses" / "target_text_corpus_v1_channel_contribution_tooling_v1.json"


class ChannelContributionToolingRegistryV1Tests(unittest.TestCase):
    def test_registry_pins_complete_only_channel_tooling(self) -> None:
        data = json.loads(REGISTRY.read_text(encoding="utf-8"))
        for item in data["inputs"] + data["implementation"]:
            path = ROOT / item["path"]
            self.assertTrue(path.is_file(), item["role"])
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), item["sha256"], item["role"])
        self.assertEqual(data["findings"]["required_groups_per_channel"], 75)
        self.assertTrue(data["findings"]["partial_contributions_rejected"])
        self.assertFalse(data["decision"]["real_contribution_created"])
        self.assertFalse(data["decision"]["training_allowed"])


if __name__ == "__main__":
    unittest.main()
