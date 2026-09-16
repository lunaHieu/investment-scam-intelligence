import csv
import sys
import unittest
import zipfile
from pathlib import Path
from tempfile import TemporaryDirectory


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from audit_mendeley_image_readiness import audit_csv, inspect_xlsx


class MendeleyImageReadinessTests(unittest.TestCase):
    def test_default_profile_image_flag_is_not_an_asset_reference(self):
        with TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "sample.csv"
            with path.open("w", encoding="utf-8", newline="") as file:
                writer = csv.DictWriter(
                    file,
                    fieldnames=[
                        "record_id",
                        "source_modality",
                        "text_content",
                        "has_metadata",
                        "label",
                        "default_profile_image_flag",
                    ],
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "record_id": "1",
                        "source_modality": "text_plus_metadata",
                        "text_content": "example",
                        "has_metadata": "true",
                        "label": "1",
                        "default_profile_image_flag": "1",
                    }
                )
            profile = audit_csv(path)
            self.assertEqual(profile["actual_image_reference_count_by_column"], {})

    def test_xlsx_media_entry_is_detected(self):
        with TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "sample.xlsx"
            with zipfile.ZipFile(path, "w") as archive:
                archive.writestr("xl/media/image1.png", b"png")
            profile = inspect_xlsx(path)
            self.assertEqual(profile["embedded_media_entry_count"], 1)


if __name__ == "__main__":
    unittest.main()
