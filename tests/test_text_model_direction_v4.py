import unittest

from scripts.synthesize_text_model_direction_v4 import aggregate_external, class_f1


class TextModelDirectionV4Tests(unittest.TestCase):
    def test_class_f1(self):
        self.assertAlmostEqual(class_f1(12, 5, 3), 0.75)
        self.assertEqual(class_f1(0, 0, 0), 0.0)

    def test_external_aggregate_is_descriptive_and_reproduces_confusion(self):
        v2 = {"metrics": {"confusion_matrix": {"tn": 10, "fp": 9, "fn": 4, "tp": 15}}}
        v3 = {"metrics": {"confusion_matrix": {"tn": 10, "fp": 5, "fn": 3, "tp": 12}}}
        result = aggregate_external(v2, v3)
        self.assertTrue(result["descriptive_only_not_a_pooled_preregistered_benchmark"])
        self.assertEqual(result["row_count"], 68)
        self.assertEqual(result["confusion_matrix"], {"tn": 20, "fp": 14, "fn": 7, "tp": 27})
        self.assertEqual(result["macro_f1"], 0.687869)


if __name__ == "__main__":
    unittest.main()
