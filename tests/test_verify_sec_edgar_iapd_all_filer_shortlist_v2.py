import unittest

from scripts.verify_sec_edgar_iapd_all_filer_shortlist_v2 import canonical_host, dotted_value, rank_digest


class VerifySecEdgarIapdAllFilerShortlistV2Tests(unittest.TestCase):
    def test_dotted_value_supports_nested_fields(self) -> None:
        self.assertEqual(dotted_value({"a": {"b": "host.test"}}, "a.b"), "host.test")

    def test_canonical_host_parses_url(self) -> None:
        self.assertEqual(canonical_host("https://www.Example.test/a"), "example.test")

    def test_rank_digest_is_namespace_bound(self) -> None:
        row = {"cik": "1", "iapd_source_record_id": "2", "normalized_host_sha256": "f" * 64}
        self.assertNotEqual(rank_digest("s", "DEV", "C", row), rank_digest("s", "HOLDOUT", "C", row))


if __name__ == "__main__":
    unittest.main()
