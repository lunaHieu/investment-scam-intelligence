import importlib.util
import sys
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

SKLEARN_AVAILABLE = importlib.util.find_spec("sklearn") is not None

if SKLEARN_AVAILABLE:
    import numpy as np

    from analyze_crimson_domains_unsupervised import select_review_queue


@unittest.skipUnless(SKLEARN_AVAILABLE, "scikit-learn is not installed")
class CrimsonUnsupervisedTests(unittest.TestCase):
    def test_review_queue_is_unique_and_balanced(self):
        records = [
            {"artifact_id": f"ART_{index}", "domain": f"d{index}.test", "features": {"x": index}}
            for index in range(20)
        ]
        labels = np.asarray([index % 2 for index in range(20)])
        anomalies = np.asarray([float(index) for index in range(20)])
        distances = np.asarray([abs(10 - index) for index in range(20)], dtype=float)
        queue = select_review_queue(
            records, labels, anomalies, distances, outlier_count=4, representative_count=6
        )
        self.assertEqual(len(queue), 10)
        self.assertEqual(len({item["domain"] for item in queue}), 10)
        self.assertEqual(sum(item["queue_reason"] == "LEXICAL_OUTLIER" for item in queue), 4)
        self.assertEqual(sum(item["queue_reason"] == "CLUSTER_REPRESENTATIVE" for item in queue), 6)
        self.assertTrue(all(item["review_status"] == "UNREVIEWED" for item in queue))


if __name__ == "__main__":
    unittest.main()
