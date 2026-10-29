import json
import unittest
from pathlib import Path

from scripts.verify_target_text_corpus_v1_sanitized_text_source_discovery_release_v1 import DEFAULT_RELEASE, verify_release


class SanitizedTextSourceDiscoveryReleaseV1Tests(unittest.TestCase):
    def test_release_verifies_with_exact_bounds(self) -> None:
        result = verify_release()
        self.assertEqual(result["status"], "PASS_RELEASE_VERIFIED")
        self.assertEqual(result["query_count"], 12)

    def test_queries_cover_both_labels_and_vietnamese(self) -> None:
        value = json.loads(DEFAULT_RELEASE.read_text(encoding="utf-8"))
        strata = {item["stratum"] for item in value["queries"]}
        self.assertTrue({"EN_CONFIRMED", "EN_LEGITIMATE", "VI_CONFIRMED", "VI_LEGITIMATE", "MULTILINGUAL"}.issubset(strata))

    def test_no_network_side_effect_is_performed_by_verifier(self) -> None:
        output = Path(verify_release()["planned_output"])
        existed_before = output.exists()
        verify_release()
        self.assertEqual(output.exists(), existed_before)


if __name__ == "__main__":
    unittest.main()
