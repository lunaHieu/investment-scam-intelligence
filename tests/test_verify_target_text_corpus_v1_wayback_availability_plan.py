import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "verify_target_text_corpus_v1_wayback_availability_plan.py"
SPEC = importlib.util.spec_from_file_location("wayback_availability_plan_verifier", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class WaybackAvailabilityPlanVerifierTests(unittest.TestCase):
    def test_frozen_plan_registry_passes(self) -> None:
        registry = (
            ROOT
            / "registry"
            / "analyses"
            / "target_text_corpus_v1_wayback_availability_plan_v1.json"
        )
        result = MODULE.verify_registry(registry)
        self.assertTrue(result["valid"], result["errors"])
        self.assertEqual(result["candidate_count"], 40)

    def test_open_capture_gate_fails(self) -> None:
        source = (
            ROOT
            / "registry"
            / "analyses"
            / "target_text_corpus_v1_wayback_availability_plan_v1.json"
        )
        payload = json.loads(source.read_text(encoding="utf-8"))
        payload["decision"]["candidate_capture_allowed"] = True
        with tempfile.TemporaryDirectory() as directory:
            copied = Path(directory) / "registry" / "analyses" / source.name
            copied.parent.mkdir(parents=True)
            copied.write_text(json.dumps(payload), encoding="utf-8")
            result = MODULE.verify_registry(copied)
        self.assertFalse(result["valid"])
        self.assertIn("Candidate capture must remain blocked", result["errors"])


if __name__ == "__main__":
    unittest.main()
