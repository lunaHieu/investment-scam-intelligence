import hashlib
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "registry" / "analyses" / "gate_failure_diagnostic_and_adaptive_recovery_v1.json"


class GateFailureDiagnosticAndAdaptiveRecoveryV1Tests(unittest.TestCase):
    def test_policy_is_hash_pinned_and_preserves_invariants(self) -> None:
        data = json.loads(REGISTRY.read_text(encoding="utf-8"))
        policy = data["implementation"][0]
        path = ROOT / policy["path"]
        self.assertTrue(path.is_file())
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), policy["sha256"])

        required = set(data["required_failure_report_fields"])
        self.assertIn("confirmed_facts_vs_hypotheses", required)
        self.assertIn("root_cause_and_alternatives", required)
        self.assertIn("affected_scope_and_dependencies", required)
        self.assertIn("ranked_recovery_options", required)
        self.assertIn("independent_work_that_remains_open", required)

        invariants = data["non_relaxable_invariants"]
        self.assertTrue(invariants["no_overwrite"])
        self.assertTrue(invariants["hash_and_identity_preservation"])
        self.assertTrue(invariants["no_live_candidate_domain_access"])
        self.assertTrue(invariants["no_label_from_availability"])
        self.assertTrue(invariants["validation_and_test_remain_closed"])

        adaptive = data["adaptive_recovery_contract"]
        self.assertTrue(adaptive["smallest_dependent_scope_only"])
        self.assertTrue(adaptive["versioned_amendment_required"])
        self.assertTrue(adaptive["repeated_retry_requires_new_diagnostic_justification"])


if __name__ == "__main__":
    unittest.main()
