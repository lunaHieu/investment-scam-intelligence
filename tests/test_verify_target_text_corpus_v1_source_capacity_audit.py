import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from scripts.verify_target_text_corpus_v1_source_capacity_audit import verify


ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / "configs" / "target_text_corpus_v1_source_capacity_audit_v1.json"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class TargetTextCorpusSourceCapacityAuditTests(unittest.TestCase):
    def test_frozen_audit_reproduces_capacity_and_closed_gates(self) -> None:
        result = verify(AUDIT)
        self.assertEqual(result["channels_audited"], 4)
        self.assertEqual(result["channels_capacity_pass"], 2)
        self.assertEqual(result["channels_capacity_fail"], 2)
        self.assertTrue(result["source_or_channel_amendment_required"])
        self.assertFalse(result["candidate_enumeration_allowed"])
        self.assertFalse(result["training_allowed"])

    def test_audit_cannot_authorize_network_execution(self) -> None:
        audit = json.loads(AUDIT.read_text(encoding="utf-8"))
        changed = copy.deepcopy(audit)
        for item in changed["basis"]:
            path = Path(item["path"])
            if not path.is_absolute():
                item["path"] = str(ROOT / path)
        changed["decision"]["sec_bulk_download_allowed_by_this_audit"] = True
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "audit.json"
            path.write_text(json.dumps(changed), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "prohibited execution"):
                verify(path)

    def test_registered_audit_and_implementation_hashes_are_current(self) -> None:
        registry_path = (
            ROOT / "registry" / "analyses" / "target_text_corpus_v1_source_capacity_audit_v1.json"
        )
        registry = json.loads(registry_path.read_text(encoding="utf-8"))
        self.assertFalse(registry["decision"]["candidate_enumeration_allowed"])
        self.assertFalse(registry["decision"]["training_allowed"])
        for item in registry["inputs"] + registry["implementation"]:
            path = ROOT / item["path"]
            self.assertTrue(path.is_file(), item["path"])
            self.assertEqual(sha256_file(path), item["sha256"], item["path"])


if __name__ == "__main__":
    unittest.main()
