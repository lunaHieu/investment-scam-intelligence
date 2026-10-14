import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.audit_raw_source_manifest_coverage_v1 import manifest_set_sha256, raw_inventory


class RawSourceManifestCoverageV1Tests(unittest.TestCase):
    def test_manifest_set_digest_is_order_sensitive_and_reproducible(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = root / "a.json"
            second = root / "b.json"
            first.write_text("{}\n", encoding="utf-8")
            second.write_text("{\"x\":1}\n", encoding="utf-8")
            expected_text = f"a.json\t{hashlib.sha256(first.read_bytes()).hexdigest()}\n"
            expected_text += f"b.json\t{hashlib.sha256(second.read_bytes()).hexdigest()}\n"
            self.assertEqual(manifest_set_sha256([first, second]), hashlib.sha256(expected_text.encode("utf-8")).hexdigest())

    def test_inventory_counts_covered_files_without_hashing_unregistered_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            branch = root / "source"
            branch.mkdir()
            covered = branch / "covered.bin"
            other = branch / "other.bin"
            covered.write_bytes(b"abc")
            other.write_bytes(b"12345")
            with patch("pathlib.Path.resolve", autospec=True, side_effect=lambda value: value.absolute()):
                directories, total_files, total_bytes = raw_inventory(root, {covered.absolute()})
            self.assertEqual(total_files, 2)
            self.assertEqual(total_bytes, 8)
            self.assertEqual(directories[0]["source_manifest_covered_files"], 1)
            self.assertEqual(directories[0]["outside_source_manifest_scope_files"], 1)


if __name__ == "__main__":
    unittest.main()
