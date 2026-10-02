import unittest

from scripts.merge_wayback_candidate_queues_v2 import merge_queues


class MergeWaybackCandidateQueuesV2Tests(unittest.TestCase):
    def test_merge_preserves_unlabeled_state(self):
        row1 = {"candidate_id": "C1", "candidate_host": "a.test", "label_created": False, "training_eligible": "NO"}
        row2 = {"candidate_id": "C2", "candidate_host": "b.test", "label_created": False, "training_eligible": "NO"}
        self.assertEqual(len(merge_queues([[row1], [row2]])), 2)

    def test_duplicate_host_is_rejected(self):
        row1 = {"candidate_id": "C1", "candidate_host": "a.test", "label_created": False, "training_eligible": "NO"}
        row2 = {"candidate_id": "C2", "candidate_host": "A.TEST.", "label_created": False, "training_eligible": "NO"}
        with self.assertRaises(ValueError):
            merge_queues([[row1], [row2]])


if __name__ == "__main__":
    unittest.main()
