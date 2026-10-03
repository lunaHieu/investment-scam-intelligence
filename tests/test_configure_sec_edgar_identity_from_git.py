import json
import tempfile
import unittest
from pathlib import Path

from scripts.configure_sec_edgar_identity_from_git import (
    validate_contact_email,
    write_private_identity,
)


class ConfigureSecEdgarIdentityTests(unittest.TestCase):
    def test_writes_exact_private_contract_without_printing(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "identity.json"
            write_private_identity(
                path,
                project="Research Project",
                email="researcher@example.org",
                purpose="academic investment research",
            )
            value = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(
                set(value),
                {"organization_or_project", "contact_email", "purpose"},
            )

    def test_refuses_noreply_address(self):
        with self.assertRaises(ValueError):
            validate_contact_email("12345+user@users.noreply.github.com")

    def test_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "identity.json"
            path.write_text("{}", encoding="utf-8")
            with self.assertRaises(FileExistsError):
                write_private_identity(
                    path,
                    project="Research Project",
                    email="researcher@example.org",
                    purpose="academic investment research",
                )


if __name__ == "__main__":
    unittest.main()
