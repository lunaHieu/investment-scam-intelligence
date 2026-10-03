import unittest

from scripts.remove_reserved_hosts_from_reference_pool import remove_reserved_hosts


class RemoveReservedHostsFromReferencePoolTests(unittest.TestCase):
    def test_removes_every_reserved_host_without_mutating_other_rows(self):
        pool = [
            {"normalized_host": "one.example", "id": 1},
            {"normalized_host": "two.example", "id": 2},
        ]
        reserved = [{"normalized_host": "ONE.EXAMPLE."}]
        output, hosts = remove_reserved_hosts(pool, reserved)
        self.assertEqual(output, [{"normalized_host": "two.example", "id": 2}])
        self.assertEqual(hosts, {"one.example"})


if __name__ == "__main__":
    unittest.main()
