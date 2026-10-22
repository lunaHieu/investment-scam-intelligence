import hashlib
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "registry" / "analyses" / "target_text_corpus_v1_capacity_gap_v4.json"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


class TargetTextCorpusV1CapacityGapV4Tests(unittest.TestCase):
    def test_capacity_matrix_recomputes_all_denominators(self) -> None:
        data = load_json(REGISTRY)
        for item in data["inputs"] + data["implementation"]:
            path = Path(item["path"])
            if not path.is_absolute():
                path = ROOT / path
            self.assertTrue(path.is_file(), item["role"])
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), item["sha256"], item["role"])

        matrix = load_json(ROOT / data["inputs"][0]["path"])
        v3 = load_json(ROOT / data["inputs"][1]["path"])
        targets = {
            row["channel_id"]: {
                "DEVELOPMENT": row["development_accepted_group_quota"],
                "EXTERNAL_HOLDOUT": row["external_holdout_accepted_group_quota"],
            }
            for row in matrix["channel_quotas"]
        }
        supply = v3["observed_owner_accepted_candidate_supply"]
        channels = data["capacity_matrix"]["by_channel"]
        for channel_id, target in targets.items():
            observed = channels[channel_id]
            for cohort in ("DEVELOPMENT", "EXTERNAL_HOLDOUT"):
                self.assertEqual(observed[cohort]["target"], target[cohort])
                self.assertEqual(observed[cohort]["admitted"], 0)
                self.assertEqual(observed[cohort]["conditional_supply"], supply[channel_id][cohort])
                self.assertEqual(
                    observed[cohort]["conditional_gap"],
                    target[cohort] - supply[channel_id][cohort],
                )

        totals = data["capacity_matrix"]["totals"]
        self.assertEqual(totals["required"], 300)
        self.assertEqual(totals["admitted"], 0)
        self.assertEqual(totals["conditional_supply"], 42)
        self.assertEqual(totals["conditional_gap"], 258)

    def test_language_and_asset_layers_cannot_be_silently_credited(self) -> None:
        data = load_json(REGISTRY)
        language = data["language_overlay"]
        self.assertEqual(language["required_non_english_groups"], 30)
        self.assertEqual(language["required_vietnamese_groups"], 16)
        self.assertEqual(language["audited_language_credit"], 0)
        self.assertIsNone(language["english_gap"])

        layers = data["non_admissible_asset_layers"]
        self.assertEqual(layers["historical_baseline_train_rows"]["count"], 3916)
        self.assertEqual(layers["integrity_verified_raw_files"]["count"], 278)
        self.assertEqual(layers["crimson_unlabeled_domains"]["count"], 43572)
        self.assertEqual(layers["usable_image_assets"]["count"], 0)
        self.assertTrue(all(item["v1_core_credit"] == 0 for item in layers.values()))
        self.assertFalse(data["decision"]["training_allowed"])


if __name__ == "__main__":
    unittest.main()
