import hashlib
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "registry" / "analyses" / "sec_edgar_iapd_v5_review_evidence_coverage_v1.json"


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


class SecEdgarIapdV5ReviewEvidenceCoverageV1Tests(unittest.TestCase):
    def test_all_58_rows_have_consistent_local_review_evidence(self) -> None:
        data = json.loads(REGISTRY.read_text(encoding="utf-8"))
        resolved = {}
        for item in data["inputs"] + data["implementation"]:
            path = Path(item["path"])
            if not path.is_absolute():
                path = ROOT / path
            self.assertTrue(path.is_file(), item["path"])
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), item["sha256"], item["path"])
            resolved[item["role"]] = path

        plan = json.loads(resolved["capture_plan_v5"].read_text(encoding="utf-8"))
        availability = {row["availability_plan_id"]: row for row in load_jsonl(resolved["availability_plan_v1"])}
        offline = {row["shortlist_id"]: row for row in load_jsonl(resolved["offline_review_v1"])}
        iapd = {str(row["source_record_id"]): row for row in load_jsonl(resolved["normalized_iapd_v1"])}
        allowed_statuses = {
            "OFFLINE_EXACT_CORE_NAME_EVIDENCE_PASS",
            "OFFLINE_COMPATIBLE_NAME_VARIANT_EVIDENCE_PASS",
        }
        statuses = {}
        cohorts = {}
        for row in plan["results"]:
            record_id = row["availability_plan_id"]
            availability_row = availability[record_id]
            offline_row = offline[availability_row["shortlist_id"]]
            iapd_row = iapd[str(offline_row["iapd_source_record_id"])]
            expected_host = row["candidate_host"].casefold().rstrip(".")
            self.assertEqual(availability_row["candidate_host"].casefold().rstrip("."), expected_host)
            self.assertEqual(iapd_row["normalized_host"], expected_host)
            self.assertEqual(availability_row["cohort"], row["cohort"])
            self.assertEqual(offline_row["cohort"], row["cohort"])
            self.assertIn(offline_row["identity_review_status"], allowed_statuses)
            statuses[offline_row["identity_review_status"]] = statuses.get(offline_row["identity_review_status"], 0) + 1
            cohorts[row["cohort"]] = cohorts.get(row["cohort"], 0) + 1

        self.assertEqual(len(plan["results"]), 58)
        self.assertEqual(cohorts, {"DEVELOPMENT": 46, "EXTERNAL_HOLDOUT": 12})
        self.assertEqual(
            statuses,
            {"OFFLINE_EXACT_CORE_NAME_EVIDENCE_PASS": 57, "OFFLINE_COMPATIBLE_NAME_VARIANT_EVIDENCE_PASS": 1},
        )
        self.assertFalse(data["decision"]["real_review_allowed_now"])
        self.assertFalse(data["decision"]["identity_evidence_is_ground_truth"])
        self.assertFalse(data["decision"]["training_allowed"])


if __name__ == "__main__":
    unittest.main()
