import unittest

from scripts.capture_balanced_wayback_plan_v2 import assert_archive_url, raw_replay_url


class CaptureBalancedWaybackPlanV2Tests(unittest.TestCase):
    def test_snapshot_url_becomes_raw_replay(self):
        url, timestamp = raw_replay_url(
            "https://web.archive.org/web/20260102030405/https://www.example.com/"
        )
        self.assertEqual(timestamp, "20260102030405")
        self.assertEqual(
            url,
            "https://web.archive.org/web/20260102030405id_/https://www.example.com/",
        )

    def test_non_archive_redirect_is_rejected(self):
        with self.assertRaises(ValueError):
            assert_archive_url("https://example.com/web/20260102030405/http://example.net/")

    def test_http_archive_url_is_rejected(self):
        with self.assertRaises(ValueError):
            assert_archive_url("http://web.archive.org/web/20260102030405/http://example.net/")


if __name__ == "__main__":
    unittest.main()
