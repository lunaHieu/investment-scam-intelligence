import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "verify_target_text_corpus_v1_candidate_enumeration_v1.py"
SPEC = importlib.util.spec_from_file_location("candidate_enumeration_registry_verifier", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class CandidateEnumerationRegistryVerifierTests(unittest.TestCase):
    def test_frozen_registry_passes(self) -> None:
        registry = (
            ROOT
            / "registry"
            / "analyses"
            / "target_text_corpus_v1_candidate_enumeration_v1.json"
        )
        result = MODULE.verify_registry(registry)
        self.assertTrue(result["valid"], result["errors"])
        self.assertEqual(result["candidate_count"], 40)

    def test_changed_analysis_id_fails(self) -> None:
        source = (
            ROOT
            / "registry"
            / "analyses"
            / "target_text_corpus_v1_candidate_enumeration_v1.json"
        )
        payload = json.loads(source.read_text(encoding="utf-8"))
        payload["analysis_id"] = "CHANGED"
        with tempfile.TemporaryDirectory() as directory:
            copied = Path(directory) / "registry" / "analyses" / source.name
            copied.parent.mkdir(parents=True)
            copied.write_text(json.dumps(payload), encoding="utf-8")
            result = MODULE.verify_registry(copied)
        self.assertFalse(result["valid"])
        self.assertIn("Unexpected analysis ID", result["errors"])


if __name__ == "__main__":
    unittest.main()
