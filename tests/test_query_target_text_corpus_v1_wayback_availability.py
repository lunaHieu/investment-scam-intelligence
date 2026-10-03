import unittest

from scripts.query_target_text_corpus_v1_wayback_availability import (
    assert_archive_url,
    availability_url,
    normalize_snapshot_url,
    parse_availability_response,
)


class TargetTextCorpusWaybackAvailabilityTests(unittest.TestCase):
    def test_availability_url_encodes_candidate_without_accessing_it(self) -> None:
        result = availability_url(
            "https://archive.org/wayback/available",
            "https://example.test/invest?q=one",
            "20261003",
        )
        self.assertTrue(result.startswith("https://archive.org/wayback/available?"))
        self.assertIn("example.test%2Finvest", result)

    def test_network_guard_rejects_candidate_host(self) -> None:
        with self.assertRaises(ValueError):
            assert_archive_url("https://example.test/wayback/available")

    def test_snapshot_url_is_normalized_to_https(self) -> None:
        value = normalize_snapshot_url(
            "http://web.archive.org/web/20260102030405/https://example.test/"
        )
        self.assertEqual(
            value,
            "https://web.archive.org/web/20260102030405/https://example.test/",
        )

    def test_valid_available_response_is_parsed(self) -> None:
        result = parse_availability_response({
            "archived_snapshots": {
                "closest": {
                    "available": True,
                    "status": "200",
                    "timestamp": "20260102030405",
                    "url": "http://web.archive.org/web/20260102030405/https://example.test/",
                }
            }
        })
        self.assertTrue(result["available"])
        self.assertEqual(result["snapshot_timestamp"], "20260102030405")

    def test_missing_closest_is_unavailable_not_error(self) -> None:
        result = parse_availability_response({"archived_snapshots": {}})
        self.assertFalse(result["available"])
        self.assertIsNone(result["snapshot_url"])


if __name__ == "__main__":
    unittest.main()
