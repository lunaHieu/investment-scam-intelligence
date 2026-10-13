import unittest

from scripts.execute_sec_edgar_iapd_wayback_availability_v1 import assert_archive_url, normalize_snapshot_url, parse_response


class ExecuteSecEdgarIapdWaybackAvailabilityV1Tests(unittest.TestCase):
    def test_network_guard_accepts_only_allowlisted_archive_hosts(self) -> None:
        allowed = {"archive.org", "web.archive.org"}
        assert_archive_url("https://archive.org/wayback/available", allowed)
        with self.assertRaises(ValueError):
            assert_archive_url("https://example.test/", allowed)

    def test_parse_response_distinguishes_unavailable(self) -> None:
        self.assertEqual(parse_response({"archived_snapshots": {}})["available"], False)

    def test_parse_response_normalizes_archive_snapshot_to_https(self) -> None:
        result = parse_response({"archived_snapshots": {"closest": {"available": True, "status": "200", "timestamp": "20260102030405", "url": "http://web.archive.org/web/20260102030405/https://example.test/"}}})
        self.assertTrue(result["available"])
        self.assertEqual(result["snapshot_url"], "https://web.archive.org/web/20260102030405/https://example.test/")
        self.assertEqual(normalize_snapshot_url(result["snapshot_url"]), result["snapshot_url"])


if __name__ == "__main__":
    unittest.main()
