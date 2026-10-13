import unittest

from scripts.build_sec_edgar_iapd_all_filer_shortlist_v2 import nested_value, require_host, selection_key


class BuildSecEdgarIapdAllFilerShortlistV2Tests(unittest.TestCase):
    def test_nested_value_reads_declared_host_field(self) -> None:
        self.assertEqual(nested_value({"candidate_identity": {"normalized_host": "example.test"}}, "candidate_identity.normalized_host"), "example.test")

    def test_selection_key_is_namespace_bound(self) -> None:
        row = {"cik": "0000000001", "iapd_source_record_id": "1", "normalized_host_sha256": "a" * 64}
        self.assertNotEqual(selection_key("seed", "DEV", "CHANNEL", row), selection_key("seed", "HOLDOUT", "CHANNEL", row))

    def test_require_host_parses_url_and_removes_www(self) -> None:
        self.assertEqual(require_host("https://www.Example.test/path"), "example.test")


if __name__ == "__main__":
    unittest.main()
