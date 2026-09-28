import json
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from select_mendeley_financial_claims_ablation_v1 import (
    CLAIM_COLUMNS,
    EXPECTED_PROTOCOL_SHA256,
    load_feature_records,
    load_frozen_protocol,
    promotion_decision,
)


def variant_report(source_mean, worst, pooled, by_source):
    return {
        "validation_source_summary": {
            "unweighted_mean_macro_f1_across_sources": source_mean,
            "worst_source_macro_f1": worst,
        },
        "validation": {"macro_f1": pooled},
        "validation_by_source_dataset": {
            source: {"macro_f1": value} for source, value in by_source.items()
        },
    }


class MendeleyFinancialClaimsAblationV1Tests(unittest.TestCase):
    def test_protocol_hash_and_contract_are_frozen(self):
        protocol_path = (
            ROOT / "configs" / "mendeley_financial_claims_ablation_v1_protocol.json"
        )
        protocol = load_frozen_protocol(protocol_path)
        self.assertEqual(
            protocol["data_contract"]["feature_artifact_sha256"],
            "8e222b3cace3f6c922da8044c34e9481badb73ac52fdc8b44b64449f1656badc",
        )
        self.assertEqual(len(CLAIM_COLUMNS), 11)
        self.assertEqual(EXPECTED_PROTOCOL_SHA256, "e9fa5fa6dbcdf51e93671f327af5606141a7b1fd639102cf52f6eadb43555de2")

    def test_feature_reader_rejects_test_partition(self):
        record = {
            "record_id": "test_1",
            "partition": "test",
            "split_group_id": "G1",
            "feature_version": "MENDELEY_FINANCIAL_CLAIMS_V4",
            "features": {column: False for column in CLAIM_COLUMNS},
        }
        with TemporaryDirectory(dir=ROOT) as temp_dir:
            path = Path(temp_dir) / "features.jsonl"
            path.write_text(json.dumps(record) + "\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "prohibited partition"):
                load_feature_records(
                    path,
                    require_frozen_hash=False,
                    expected_counts={"train": 0, "validation": 0},
                )

    def test_feature_reader_requires_boolean_presence_fields(self):
        features = {column: False for column in CLAIM_COLUMNS}
        features[CLAIM_COLUMNS[0]] = 1
        record = {
            "record_id": "train_1",
            "partition": "train",
            "split_group_id": "G1",
            "feature_version": "MENDELEY_FINANCIAL_CLAIMS_V4",
            "features": features,
        }
        with TemporaryDirectory(dir=ROOT) as temp_dir:
            path = Path(temp_dir) / "features.jsonl"
            path.write_text(json.dumps(record) + "\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "must be boolean"):
                load_feature_records(
                    path,
                    require_frozen_hash=False,
                    expected_counts={"train": 1, "validation": 0},
                )

    def test_promotion_requires_every_predeclared_gate(self):
        baseline = variant_report(
            0.70,
            0.50,
            0.70,
            {"a": 0.70, "b": 0.70, "c": 0.70, "d": 0.70},
        )
        passing = variant_report(
            0.72,
            0.51,
            0.71,
            {"a": 0.72, "b": 0.71, "c": 0.72, "d": 0.71},
        )
        failing_source_guard = variant_report(
            0.72,
            0.50,
            0.71,
            {"a": 0.76, "b": 0.76, "c": 0.71, "d": 0.67},
        )
        self.assertTrue(promotion_decision(baseline, passing)["passes_all_promotion_gates"])
        failed = promotion_decision(baseline, failing_source_guard)
        self.assertFalse(failed["passes_all_promotion_gates"])
        self.assertEqual(failed["selected_variant"], "text_only")


if __name__ == "__main__":
    unittest.main()
