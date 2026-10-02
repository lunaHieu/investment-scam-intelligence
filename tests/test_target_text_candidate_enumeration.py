import json
import unittest
from pathlib import Path

from scripts.enumerate_target_text_corpus_v1_candidates import validate_ready_ledger
from scripts.verify_target_text_corpus_v1_schema_review_pilot import validate_candidate
from src.isi.curation.target_text_candidate_enumeration import (
    CHANNELS,
    enumerate_balanced_candidates,
)


QUOTAS = {channel: 2 for channel in CHANNELS}
SEED = "frozen-test-seed"
WAVE_ID = "TTCV1_ENUM_TEST_WAVE"
ENUMERATED_AT = "2026-10-03T12:00:00+07:00"


def reference_record(channel_id: str, number: int, *, host: str | None = None, entity: str | None = None) -> dict:
    channel = CHANNELS[channel_id]
    source_id = sorted(channel["sources"])[0]
    host = host or f"{channel['candidate_prefix'].lower().replace('_', '-')}-{number}.example"
    return {
        "source_id": source_id,
        "source_record_id": f"{channel['candidate_prefix']}-{number}",
        "reference_url": f"https://reference.example/{source_id}/{number}",
        "reference_observed_at": ENUMERATED_AT,
        "reference_sha256": f"{number:064x}"[-64:],
        "entity_name_from_reference": entity or f"{channel['candidate_prefix']} Entity {number}",
        "candidate_url": f"http://{host}/",
        "normalized_host": host,
        "identity_linkage_basis": "Exact domain in frozen reference record.",
        "opened_normalized_host": "PASS",
        "opened_reference_identity": "PASS",
        "legacy_component": "PASS",
    }


def inputs(count: int = 4) -> dict[str, list[dict]]:
    return {
        channel: [reference_record(channel, index) for index in range(1, count + 1)]
        for channel in CHANNELS
    }


class TargetTextCandidateEnumerationTests(unittest.TestCase):
    def test_selection_is_balanced_deterministic_and_unlabeled(self):
        first = enumerate_balanced_candidates(
            inputs(), quotas=QUOTAS, seed=SEED, wave_id=WAVE_ID, enumerated_at=ENUMERATED_AT
        )
        second = enumerate_balanced_candidates(
            inputs(), quotas=QUOTAS, seed=SEED, wave_id=WAVE_ID, enumerated_at=ENUMERATED_AT
        )
        self.assertEqual(first, second)
        queue, report = first
        self.assertEqual(len(queue), 8)
        self.assertEqual(report["selected_counts"], QUOTAS)
        self.assertTrue(all(not validate_candidate(record) for record in queue))
        self.assertTrue(all(record["review_state"]["ground_truth_status"] == "UNCERTAIN" for record in queue))
        self.assertTrue(all(record["review_state"]["label_created"] is False for record in queue))
        self.assertEqual(report["safety_contract"]["network_operations"], 0)
        self.assertFalse(report["safety_contract"]["training_allowed"])

    def test_channel_shortfall_fails_without_reallocation(self):
        records = inputs()
        records["CONFIRMED_CFTC_RED_LINKED_WAYBACK_WEBSITE"] = records[
            "CONFIRMED_CFTC_RED_LINKED_WAYBACK_WEBSITE"
        ][:1]
        with self.assertRaisesRegex(ValueError, "shortfall"):
            enumerate_balanced_candidates(
                records, quotas=QUOTAS, seed=SEED, wave_id=WAVE_ID, enumerated_at=ENUMERATED_AT
            )

    def test_cross_channel_host_is_excluded_from_both_channels(self):
        records = inputs()
        shared_host = "shared-collision.example"
        records["CONFIRMED_REGULATOR_LINKED_WEBSITE"][0] = reference_record(
            "CONFIRMED_REGULATOR_LINKED_WEBSITE", 10, host=shared_host
        )
        records["CONFIRMED_CFTC_RED_LINKED_WAYBACK_WEBSITE"][0] = reference_record(
            "CONFIRMED_CFTC_RED_LINKED_WAYBACK_WEBSITE", 10, host=shared_host
        )
        _, report = enumerate_balanced_candidates(
            records, quotas=QUOTAS, seed=SEED, wave_id=WAVE_ID, enumerated_at=ENUMERATED_AT
        )
        self.assertEqual(report["cross_channel_host_overlap_count"], 1)
        self.assertEqual(
            report["exclusion_counts"]["CONFIRMED_REGULATOR_LINKED_WEBSITE"][
                "cross_channel_host_overlap"
            ],
            1,
        )
        self.assertEqual(
            report["exclusion_counts"]["CONFIRMED_CFTC_RED_LINKED_WAYBACK_WEBSITE"][
                "cross_channel_host_overlap"
            ],
            1,
        )

    def test_cross_stratum_entity_is_excluded(self):
        records = inputs()
        entity = "Same Entity Across Strata"
        records["CONFIRMED_REGULATOR_LINKED_WEBSITE"][0] = reference_record(
            "CONFIRMED_REGULATOR_LINKED_WEBSITE", 10, entity=entity
        )
        records["LEGITIMATE_REGISTER_LINKED_WEBSITE"][0] = reference_record(
            "LEGITIMATE_REGISTER_LINKED_WEBSITE", 10, entity=entity
        )
        _, report = enumerate_balanced_candidates(
            records, quotas=QUOTAS, seed=SEED, wave_id=WAVE_ID, enumerated_at=ENUMERATED_AT
        )
        self.assertEqual(report["cross_stratum_entity_overlap_count"], 1)

    def test_failed_exclusion_checks_never_enter_queue(self):
        records = inputs()
        records["LEGITIMATE_SEC_EDGAR_LINKED_WAYBACK_WEBSITE"][0][
            "opened_normalized_host"
        ] = "FAIL"
        _, report = enumerate_balanced_candidates(
            records, quotas=QUOTAS, seed=SEED, wave_id=WAVE_ID, enumerated_at=ENUMERATED_AT
        )
        self.assertEqual(
            report["exclusion_counts"]["LEGITIMATE_SEC_EDGAR_LINKED_WAYBACK_WEBSITE"][
                "opened_normalized_host_not_clear"
            ],
            1,
        )

    def test_current_missing_input_ledger_cannot_release_enumeration(self):
        path = Path(
            r"D:\nckh 2026-2027\ISI_Data\governance\target_text_corpus_v1"
        ) / "acquisition_prerequisite_ledger_v1.json"
        ledger = json.loads(path.read_text(encoding="utf-8"))
        with self.assertRaisesRegex(ValueError, "not ready"):
            validate_ready_ledger(ledger)


if __name__ == "__main__":
    unittest.main()
