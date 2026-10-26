import json
import tempfile
import unittest
from pathlib import Path

from scripts.verify_sec_edgar_iapd_v11_metadata_recovery_release import verify


class V11MetadataRecoveryReleaseVerifierTests(unittest.TestCase):
    def test_forbidden_gate_is_detected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "release.json"
            path.write_text(json.dumps({"release_id": "wrong", "decision": {"training_allowed": True}}), encoding="utf-8")
            result = verify(path)
            self.assertEqual(result["status"], "FAIL")
            self.assertTrue(result["errors"])


if __name__ == "__main__":
    unittest.main()
