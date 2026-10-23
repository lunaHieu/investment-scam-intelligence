import copy
import json
import tempfile
import unittest
from pathlib import Path

from scripts.verify_target_text_corpus_v1_parallel_c_workstream_v1 import verify


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs" / "target_text_corpus_v1_parallel_c_workstream_v1.json"


class ParallelCWorkstreamV1Tests(unittest.TestCase):
    def test_real_c1_scope_recomputes_current_gaps_and_closed_gates(self) -> None:
        result = verify(CONFIG)
        self.assertEqual(result["status"], "PASS_C1_OFFLINE_SCOPE_FROZEN_EXTERNAL_GATES_PRESERVED")
        self.assertEqual(result["checks"]["scope_items"], 5)
        self.assertEqual(result["checks"]["required_groups"], 300)
        self.assertEqual(result["checks"]["admitted_groups"], 0)
        self.assertEqual(result["checks"]["conditional_residual_gap"], 258)
        self.assertFalse(result["decision"]["network_execution_allowed"])
        self.assertFalse(result["decision"]["training_allowed"])

    def _tampered(self, mutate) -> Path:
        data = copy.deepcopy(json.loads(CONFIG.read_text(encoding="utf-8")))
        mutate(data)
        handle = tempfile.NamedTemporaryFile(mode="w", suffix=".json", dir=ROOT / "configs", encoding="utf-8", delete=False)
        with handle:
            json.dump(data, handle, ensure_ascii=False, indent=2)
        return Path(handle.name)

    def test_rejects_premature_network_permission(self) -> None:
        path = self._tampered(lambda data: data["decision"].update({"network_execution_allowed": True}))
        try:
            result = verify(path)
        finally:
            path.unlink(missing_ok=True)
        self.assertEqual(result["status"], "FAIL")
        self.assertTrue(any("network_execution_allowed" in error for error in result["errors"]))

    def test_rejects_language_or_cftc_target_drift(self) -> None:
        def mutate(data):
            for item in data["c1_scope"]:
                if item["source_or_task"] == "CFTC_RED_REFERENCE_CAPACITY":
                    item["target_groups"] = 74
        path = self._tampered(mutate)
        try:
            result = verify(path)
        finally:
            path.unlink(missing_ok=True)
        self.assertEqual(result["status"], "FAIL")
        self.assertTrue(any("target counts" in error for error in result["errors"]))

    def test_rejects_branch_mutation_permission(self) -> None:
        path = self._tampered(lambda data: data["branch_isolation"].update({"b5_may_be_executed_by_c_workstream": True}))
        try:
            result = verify(path)
        finally:
            path.unlink(missing_ok=True)
        self.assertEqual(result["status"], "FAIL")
        self.assertTrue(any("branch isolation" in error for error in result["errors"]))


if __name__ == "__main__":
    unittest.main()
