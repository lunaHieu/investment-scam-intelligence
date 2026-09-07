import unittest
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from src.isi.contracts import assert_feature_columns, assert_gold_is_untouched
from src.isi.collection.mendeley import SOURCE_ID, ingest_csv


class ContractTests(unittest.TestCase):
    def test_safe_feature_columns_pass(self):
        assert_feature_columns({"text_embedding", "url_length", "ocr_token_count", "claim_roi"})

    def test_leakage_feature_is_rejected(self):
        with self.assertRaises(ValueError):
            assert_feature_columns({"text_embedding", "source_id"})

    def test_gold_cannot_be_used_for_tuning(self):
        with self.assertRaises(ValueError):
            assert_gold_is_untouched("gold", "select_threshold")

    def test_internal_test_remains_valid_for_evaluation(self):
        assert_gold_is_untouched("internal_test", "evaluate")

    def test_source_readiness_audit_exists(self):
        root = Path(__file__).resolve().parents[1]
        self.assertTrue((root / "registry" / "source_readiness.md").is_file())

    def test_mendeley_ingest_creates_immutable_raw_manifest_and_profile(self):
        workspace_root = Path(__file__).resolve().parents[1]
        with TemporaryDirectory(dir=workspace_root) as temp_dir:
            root = Path(temp_dir)
            source = root / "source.csv"
            source.write_text("record_id,text,label\n1,hello,0\n2,,1\n", encoding="utf-8")
            raw, manifest, report = ingest_csv(source, root / "raw", root / "manifests", root / "reports")
            self.assertTrue(raw.is_file())
            self.assertEqual(json.loads(manifest.read_text(encoding="utf-8"))["source_id"], SOURCE_ID)
            profile = json.loads(report.read_text(encoding="utf-8"))
            self.assertEqual(profile["row_count"], 2)
            self.assertEqual(profile["missing_value_count_by_column"]["text"], 1)


if __name__ == "__main__":
    unittest.main()
