import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from scripts.verify_external_text_reconciled_pilot_v2 import verify


ROOT = Path(__file__).resolve().parents[1]
PILOT_REGISTRY = ROOT / "registry" / "pilots" / "external_text_reconciled_pilot_v1.json"
V2_REGISTRY = ROOT / "registry" / "analyses" / "external_text_reconciled_pilot_verifier_v2.json"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class ExternalTextReconciledPilotVerifierV2Tests(unittest.TestCase):
    def test_v2_recomputes_and_preserves_review_limitations(self) -> None:
        result = verify(PILOT_REGISTRY)
        self.assertTrue(result["valid"], result["errors"])
        self.assertEqual(result["record_count"], 21)
        self.assertEqual(result["confirmed_count"], 10)
        self.assertEqual(result["legitimate_count"], 11)
        self.assertEqual(result["eligible_count"], 21)
        self.assertFalse(result["independent_human_evidence_rereview"])
        self.assertFalse(result["double_reviewed_gold_benchmark"])

    def test_v2_rejects_false_human_rereview_claim(self) -> None:
        registry = json.loads(PILOT_REGISTRY.read_text(encoding="utf-8"))
        changed = copy.deepcopy(registry)
        changed["review_provenance"]["independent_human_evidence_rereview"] = True
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "registry.json"
            path.write_text(json.dumps(changed), encoding="utf-8")
            result = verify(path, repo_root=ROOT)
        self.assertFalse(result["valid"])
        self.assertIn("Independent human rereview must remain false", result["errors"])

    def test_historical_v1_verifier_remains_hash_pinned_and_unchanged(self) -> None:
        registry = json.loads(PILOT_REGISTRY.read_text(encoding="utf-8"))
        entry = next(
            item for item in registry["implementation"] if item["role"] == "pilot_verifier"
        )
        self.assertEqual(
            sha256_file(ROOT / entry["path"]),
            entry["sha256"],
        )

    def test_v2_registry_hashes_are_current(self) -> None:
        registry = json.loads(V2_REGISTRY.read_text(encoding="utf-8"))
        self.assertFalse(registry["decision"]["labels_changed"])
        self.assertFalse(registry["decision"]["training_allowed"])
        for item in registry["inputs"] + registry["implementation"]:
            path = ROOT / item["path"]
            self.assertTrue(path.is_file(), item["path"])
            self.assertEqual(sha256_file(path), item["sha256"], item["path"])


if __name__ == "__main__":
    unittest.main()
