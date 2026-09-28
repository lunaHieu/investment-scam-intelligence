import json
import tempfile
import unittest
from pathlib import Path

import numpy as np

from scripts.evaluate_text_baseline_v2_external_pilot import (
    bootstrap_intervals,
    prepare_output_paths,
    validate_gate,
)


class TextBaselineV2ExternalPilotTests(unittest.TestCase):
    def test_bootstrap_is_deterministic(self):
        truth = np.asarray([0, 0, 1, 1], dtype=np.int64)
        predictions = np.asarray([0, 1, 1, 1], dtype=np.int64)
        first = bootstrap_intervals(truth, predictions, iterations=100, seed=7)
        second = bootstrap_intervals(truth, predictions, iterations=100, seed=7)
        self.assertEqual(first, second)

    def test_output_paths_refuse_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            prepare_output_paths(root)
            (root / "external_pilot_results_v1.json").write_text("{}", encoding="utf-8")
            with self.assertRaises(FileExistsError):
                prepare_output_paths(root)

    def test_gate_requires_all_21_cases(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            intake = root / "intake.json"
            validation = root / "validation.json"
            intake.write_text(
                json.dumps({"batch_id": "BATCH", "status": "RECONCILED", "records": []}),
                encoding="utf-8",
            )
            import hashlib

            digest = hashlib.sha256(intake.read_bytes()).hexdigest()
            validation.write_text(
                json.dumps(
                    {
                        "input_sha256": digest,
                        "batch_id": "BATCH",
                        "reporting_allowed": True,
                        "structural_error_count": 0,
                        "eligible_count": 21,
                        "eligible_confirmed": 10,
                        "eligible_legitimate": 11,
                        "record_results": [],
                    }
                ),
                encoding="utf-8",
            )
            with self.assertRaises(ValueError):
                validate_gate(intake, validation)


if __name__ == "__main__":
    unittest.main()

