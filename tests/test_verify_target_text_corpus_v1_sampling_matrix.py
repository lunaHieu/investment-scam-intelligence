import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from scripts.verify_target_text_corpus_v1_sampling_matrix import verify


ROOT = Path(__file__).resolve().parents[1]
MATRIX = ROOT / "configs" / "target_text_corpus_v1_sampling_matrix_v1.json"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class TargetTextCorpusSamplingMatrixTests(unittest.TestCase):
    def test_frozen_matrix_is_balanced_and_keeps_execution_closed(self) -> None:
        result = verify(MATRIX)
        self.assertEqual(result["development_groups"], 240)
        self.assertEqual(result["external_holdout_groups"], 60)
        self.assertEqual(result["channels"], 4)
        self.assertEqual(result["channels_capacity_ready"], 2)
        self.assertEqual(result["channels_capacity_blocked"], 2)
        self.assertFalse(result["acquisition_release_allowed"])
        self.assertFalse(result["training_allowed"])

    def test_channel_shortfall_cannot_be_silently_borrowed(self) -> None:
        matrix = json.loads(MATRIX.read_text(encoding="utf-8"))
        changed = copy.deepcopy(matrix)
        for item in changed["basis"]:
            item["path"] = str(ROOT / item["path"])
        changed["channel_quotas"][0]["development_accepted_group_quota"] = 70
        changed["channel_quotas"][1]["development_accepted_group_quota"] = 50
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "matrix.json"
            path.write_text(json.dumps(changed), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "channel fraction"):
                verify(path)

    def test_registered_matrix_and_implementation_hashes_are_current(self) -> None:
        registry_path = (
            ROOT / "registry" / "analyses" / "target_text_corpus_v1_sampling_matrix_v1.json"
        )
        registry = json.loads(registry_path.read_text(encoding="utf-8"))
        self.assertFalse(registry["decision"]["candidate_acquisition_release_allowed"])
        self.assertFalse(registry["decision"]["training_allowed"])
        for item in registry["inputs"] + registry["implementation"]:
            path = ROOT / item["path"]
            self.assertTrue(path.is_file(), item["path"])
            self.assertEqual(sha256_file(path), item["sha256"], item["path"])


if __name__ == "__main__":
    unittest.main()
