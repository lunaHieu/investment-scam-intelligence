import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from scripts.verify_target_text_corpus_v1_source_capacity_amendment_protocol import verify


ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = ROOT / "configs" / "target_text_corpus_v1_source_capacity_amendment_protocol_v1.json"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class TargetTextCorpusSourceCapacityAmendmentProtocolTests(unittest.TestCase):
    def test_protocol_opens_only_sec_plan_preparation(self) -> None:
        result = verify(PROTOCOL)
        self.assertTrue(result["sec_bulk_plan_may_be_prepared"])
        self.assertFalse(result["sec_bulk_network_execution_allowed_now"])
        self.assertTrue(result["dfpi_status"].startswith("CONDITIONAL_"))
        self.assertTrue(result["vietnam_status"].startswith("BLOCKED_"))
        self.assertFalse(result["candidate_enumeration_allowed"])
        self.assertFalse(result["training_allowed"])

    def test_protocol_rejects_premature_vietnamese_collection(self) -> None:
        protocol = json.loads(PROTOCOL.read_text(encoding="utf-8"))
        changed = copy.deepcopy(protocol)
        for item in changed["basis"]:
            path = Path(item["path"])
            if not path.is_absolute():
                item["path"] = str(ROOT / path)
        changed["vietnam_official_issuer_references"]["automated_collection_allowed"] = True
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "protocol.json"
            path.write_text(json.dumps(changed), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Vietnamese reference"):
                verify(path)

    def test_registered_protocol_and_implementation_hashes_are_current(self) -> None:
        registry_path = (
            ROOT
            / "registry"
            / "analyses"
            / "target_text_corpus_v1_source_capacity_amendment_protocol_v1.json"
        )
        registry = json.loads(registry_path.read_text(encoding="utf-8"))
        self.assertFalse(registry["decision"]["network_execution_allowed"])
        self.assertFalse(registry["decision"]["training_allowed"])
        for item in registry["inputs"] + registry["implementation"]:
            path = ROOT / item["path"]
            self.assertTrue(path.is_file(), item["path"])
            self.assertEqual(sha256_file(path), item["sha256"], item["path"])


if __name__ == "__main__":
    unittest.main()
