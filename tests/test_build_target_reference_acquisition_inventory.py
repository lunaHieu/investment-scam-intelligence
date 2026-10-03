import tempfile
import unittest
from pathlib import Path

from scripts.build_target_reference_acquisition_inventory import artifact


class BuildTargetReferenceAcquisitionInventoryTests(unittest.TestCase):
    def test_artifact_records_exact_size_and_hash(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sample.bin"
            path.write_bytes(b"reference bytes")
            value = artifact(path, "sample")
            self.assertEqual(value["bytes"], 15)
            self.assertEqual(len(value["sha256"]), 64)
            self.assertEqual(value["role"], "sample")


if __name__ == "__main__":
    unittest.main()
