import unittest

from scripts.build_sec_edgar_iapd_wayback_availability_plan_v1 import archive_query_url, plan_id


class BuildSecEdgarIapdWaybackAvailabilityPlanV1Tests(unittest.TestCase):
    def test_archive_query_url_encodes_candidate_as_parameter(self) -> None:
        value = archive_query_url("https://archive.org/wayback/available", "https://example.test/a?q=1", "20261003")
        self.assertTrue(value.startswith("https://archive.org/wayback/available?"))
        self.assertIn("example.test%2Fa%3Fq%3D1", value)

    def test_archive_query_url_rejects_non_archive_endpoint(self) -> None:
        with self.assertRaises(ValueError):
            archive_query_url("https://example.test/wayback/available", "https://candidate.test/", "20261003")

    def test_plan_ids_are_cohort_separated(self) -> None:
        self.assertNotEqual(plan_id("DEVELOPMENT", 1), plan_id("EXTERNAL_HOLDOUT", 1))


if __name__ == "__main__":
    unittest.main()
