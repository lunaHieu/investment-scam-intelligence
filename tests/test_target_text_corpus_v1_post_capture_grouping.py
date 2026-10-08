import unittest

from scripts.build_target_text_corpus_v1_post_capture_grouping import (
    component_map,
    is_near_duplicate,
    normalize_entity,
    shingles,
    similarity,
)
from scripts.verify_target_text_corpus_v1_post_capture_grouping import bfs_components


METHOD = {
    "jaccard_threshold": 0.8,
    "containment_threshold": 0.95,
    "minimum_shorter_shingles_for_containment_rule": 20,
}


class TargetTextCorpusPostCaptureGroupingTests(unittest.TestCase):
    def test_normalization_masks_urls_emails_and_numbers(self) -> None:
        left = shingles("Invest 250 at https://a.example and mail x@a.example today")
        right = shingles("Invest 999 at https://b.example and mail y@b.example today")
        self.assertEqual(left, right)

    def test_near_duplicate_threshold_is_frozen(self) -> None:
        base = " ".join(f"token{i}" for i in range(40))
        same = shingles(base)
        jaccard, containment, shorter = similarity(same, same)
        self.assertTrue(is_near_duplicate(jaccard, containment, shorter, METHOD))
        unrelated = shingles("completely different words with no shared template at all")
        metrics = similarity(same, unrelated)
        self.assertFalse(is_near_duplicate(*metrics, METHOD))

    def test_transitive_components_join_chained_edges(self) -> None:
        result = component_map(["a", "b", "c", "d"], [("a", "b"), ("b", "c")])
        self.assertEqual(result["a"], ["a", "b", "c"])
        self.assertEqual(result["c"], ["a", "b", "c"])
        self.assertEqual(result["d"], ["d"])
        self.assertEqual(bfs_components(["a", "b", "c", "d"], [("a", "b"), ("b", "c")]), result)

    def test_entity_terminal_legal_suffix_is_removed(self) -> None:
        self.assertEqual(normalize_entity("Example Capital, LLC"), "example capital")
        self.assertEqual(normalize_entity("Example Capital"), "example capital")


if __name__ == "__main__":
    unittest.main()
