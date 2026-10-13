import unittest

from scripts.verify_sec_edgar_iapd_wayback_availability_result_v1 import valid_snapshot_url


class VerifySecEdgarIapdWaybackAvailabilityResultV1Tests(unittest.TestCase):
    def test_snapshot_url_must_be_https_archive_replay(self) -> None:
        self.assertTrue(valid_snapshot_url("https://web.archive.org/web/20260102030405/https://example.test/", "20260102030405"))
        self.assertFalse(valid_snapshot_url("https://example.test/web/20260102030405/https://x.test/", "20260102030405"))


if __name__ == "__main__":
    unittest.main()
