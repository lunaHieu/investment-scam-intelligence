import unittest

from scripts.normalize_existing_target_reference_indices import clean_host, entity_name


class NormalizeExistingTargetReferenceIndicesTests(unittest.TestCase):
    def test_clean_host_requires_one_nonplatform_host(self):
        self.assertEqual(clean_host({"observed_hosts": ["Example.COM."]}), "example.com")
        self.assertIsNone(clean_host({"observed_hosts": ["one.example", "two.example"]}))
        self.assertIsNone(clean_host({"observed_hosts": ["facebook.com"]}))

    def test_entity_name_is_deterministic(self):
        self.assertEqual(entity_name({"entity_name_keys": ["Zulu", "Alpha"]}), "Alpha")
        self.assertIsNone(entity_name({"entity_name_keys": []}))


if __name__ == "__main__":
    unittest.main()
