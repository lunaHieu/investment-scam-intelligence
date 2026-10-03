import tempfile
import unittest
from pathlib import Path

from scripts.normalize_cftc_red_reference_artifacts import parse_detail


class NormalizeCftcRedReferenceArtifactsTests(unittest.TestCase):
    def test_parses_exact_entity_host_and_node_id(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "detail_12345_2026-10-03.html"
            path.write_text(
                '<h1 class="page-header"><span>RED List: Example Capital</span></h1>'
                '<liclass="web-address"><b>Web address:</b> www.example-capital.test</li>'
                '<li><b>RED List date:</b> 10/03/2026</li>',
                encoding="utf-8",
            )
            value = parse_detail(path)
            self.assertEqual(value["source_record_id"], "12345")
            self.assertEqual(value["entity_name"], "Example Capital")
            self.assertEqual(value["candidate_host"], "example-capital.test")

    def test_rejects_multiple_candidate_hosts(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "detail_12345_2026-10-03.html"
            path.write_text(
                '<h1 class="page-header"><span>RED List: Example</span></h1>'
                '<li><b>Web address:</b> one.example.test, two.example.test</li>'
                '<li><b>RED List date:</b> 10/03/2026</li>',
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "exactly one"):
                parse_detail(path)


if __name__ == "__main__":
    unittest.main()
