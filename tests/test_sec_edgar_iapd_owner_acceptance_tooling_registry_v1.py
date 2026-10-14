import hashlib
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "registry" / "analyses" / "sec_edgar_iapd_owner_acceptance_tooling_v1.json"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class SecEdgarIapdOwnerAcceptanceToolingRegistryV1Tests(unittest.TestCase):
    def test_registry_pins_owner_acceptance_and_preserves_training_gates(self) -> None:
        registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
        for item in registry["inputs"] + registry["implementation"]:
            path = ROOT / item["path"]
            self.assertEqual(sha256_file(path), item["sha256"], item["path"])
        self.assertTrue(registry["findings"]["explicit_owner_attestation_required"])
        self.assertTrue(registry["findings"]["pending_packet_contains_no_preacceptance"])
        self.assertTrue(registry["findings"]["cohort_is_inherited_not_owner_supplied"])
        self.assertTrue(registry["findings"]["external_holdout_never_training_eligible"])
        self.assertFalse(registry["decision"]["real_owner_acceptance_allowed_now"])
        self.assertFalse(registry["decision"]["training_allowed"])


if __name__ == "__main__":
    unittest.main()
