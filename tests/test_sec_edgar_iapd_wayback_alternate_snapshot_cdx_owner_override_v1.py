import copy
import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from scripts.execute_sec_edgar_iapd_wayback_alternate_snapshot_cdx_owner_override_v1 import execute
from scripts.verify_sec_edgar_iapd_wayback_alternate_snapshot_cdx_owner_override_result_v1 import verify as verify_result
from scripts.verify_sec_edgar_iapd_wayback_alternate_snapshot_cdx_owner_override_v1 import PASS_STATUS, verify


ROOT = Path(__file__).resolve().parents[1]
OVERRIDE = ROOT / "configs" / "sec_edgar_iapd_wayback_alternate_snapshot_cdx_owner_timing_override_v1.json"


class AlternateSnapshotCdxOwnerOverrideV1Tests(unittest.TestCase):
    def test_real_override_changes_only_timing_and_verifies(self) -> None:
        result = verify(OVERRIDE)
        self.assertEqual(result["status"], PASS_STATUS)
        self.assertEqual(result["checks"]["scope"], "NOT_BEFORE_ONLY")
        self.assertEqual(result["checks"]["maximum_logical_requests"], 1)
        self.assertTrue(result["checks"]["non_timing_safety_contracts_unchanged"])

    def test_expanded_scope_is_rejected(self) -> None:
        value = json.loads(OVERRIDE.read_text(encoding="utf-8"))
        value["timing_override"]["scope"] = "ALL_SAFETY_GATES"
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", dir=ROOT / "configs", encoding="utf-8", delete=False) as handle:
            json.dump(value, handle, ensure_ascii=False, indent=2)
            path = Path(handle.name)
        try:
            result = verify(path)
        finally:
            path.unlink(missing_ok=True)
        self.assertEqual(result["status"], "FAIL")
        self.assertTrue(any("scope/request budget" in error for error in result["errors"]))

    def test_early_execution_and_result_are_hash_bound_without_page_download(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            override_qa = directory / "override_qa.json"
            qa = verify(OVERRIDE)
            override_qa.write_text(json.dumps(qa, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            output = directory / "report.json"

            def fetcher(url, contract, counter):
                counter[0] += 1
                fields = contract["query"]["fields"]
                payload = json.dumps([
                    fields,
                    ["20260209193325", "https://lionpoint.com/", "200", "text/html", "A" * 32],
                ]).encode("utf-8")
                return payload, {"http_status": 200, "content_type": "application/json", "response_bytes": len(payload)}

            report = execute(
                OVERRIDE,
                override_qa,
                datetime.fromisoformat("2026-10-23T21:31:00+07:00"),
                fetcher=fetcher,
                output_override=output,
            )
            result = verify_result(OVERRIDE, override_qa, output, require_frozen_output_path=False)
        self.assertEqual(report["network_request_count"], 1)
        self.assertEqual(report["safety_contract"]["archived_page_download_operations"], 0)
        self.assertEqual(result["status"], "PASS_OWNER_OVERRIDE_ALTERNATE_CANDIDATE_SELECTED_SEPARATE_CAPTURE_RELEASE_MAY_BE_PREPARED")
        self.assertFalse(result["decision"]["capture_authorized_by_this_qa"])


if __name__ == "__main__":
    unittest.main()
