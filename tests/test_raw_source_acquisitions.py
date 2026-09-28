import csv
import gzip
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from scripts.profile_external_reference_sources import profile_iosco, profile_sec
from scripts.verify_raw_data import compact_profile


ROOT = Path(__file__).resolve().parents[1]


class RawSourceAcquisitionTests(unittest.TestCase):
    def test_iosco_manifest_is_pinned_without_claiming_conviction(self):
        path = ROOT / "registry" / "manifests" / "iosco_i_scan__export__2026-09-23.json"
        manifest = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(manifest["source_id"], "iosco_i_scan")
        self.assertEqual(len(manifest["raw_file_sha256"]), 64)
        self.assertIn("not proof of a criminal conviction", manifest["raw_label_semantics"])

    def test_sec_manifest_is_reference_only(self):
        path = (
            ROOT
            / "registry"
            / "manifests"
            / "sec_iapd__ia_firm_sec_feed_2026-09-22__2026-09-23.json"
        )
        manifest = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(manifest["source_id"], "sec_iapd")
        self.assertEqual(manifest["source_version"], "IA_FIRM_SEC_Feed_09_22_2026")
        self.assertIn("not a content-safety label", manifest["raw_label_semantics"])

    def test_sec_homepage_capture_profile_is_html_without_label_inference(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "capture.html"
            path.write_text("<!doctype html><html><body>Observed content</body></html>", encoding="utf-8")
            profile = compact_profile("sec_iapd_homepage_capture_2026_09_24", path)
        self.assertEqual(profile["format"], "HTML")
        self.assertTrue(profile["html_marker_present"])
        self.assertEqual(profile["utf8_replacement_character_count"], 0)

    def test_wayback_capture_profile_supports_transport_gzip(self):
        html = b"<!doctype html><html><body>Archived observed text</body></html>"
        with TemporaryDirectory() as directory:
            path = Path(directory) / "capture.html"
            path.write_bytes(gzip.compress(html))
            profile = compact_profile("wayback_confirmed_capture_2026_09_24", path)
        self.assertEqual(profile["format"], "GZIP_HTML")
        self.assertEqual(profile["decoded_size_bytes"], len(html))
        self.assertTrue(profile["html_marker_present"])

    def test_wayback_reviewable_manifests_remain_unlabeled(self):
        manifests = sorted(
            (ROOT / "registry" / "manifests").glob("wayback_confirmed_capture__*.json")
        )
        self.assertEqual(len(manifests), 10)
        for path in manifests:
            manifest = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(
                manifest["source_id"], "wayback_confirmed_capture_2026_09_24"
            )
            self.assertIn("not an automatic scam label", manifest["raw_label_semantics"])
            self.assertEqual(len(manifest["raw_file_sha256"]), 64)

    def test_official_warning_manifests_are_evidence_only(self):
        manifests = sorted(
            (ROOT / "registry" / "manifests").glob("official_warning_capture__*.json")
        )
        self.assertEqual(len(manifests), 12)
        for path in manifests:
            manifest = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(manifest["source_id"], "official_warning_capture_2026_09_24")
            self.assertIn("not model input", manifest["raw_label_semantics"])
            self.assertIn("not automatically", manifest["raw_label_semantics"])

    def test_iosco_csv_profile_is_read_only_and_counts_rows(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "iosco.csv"
            with path.open("w", encoding="utf-8-sig", newline="") as file:
                writer = csv.writer(file)
                writer.writerow(["id", "nca_name", "validation_date"])
                writer.writerow(["1", "Regulator A", "2026-09-01"])
                writer.writerow(["2", "Regulator B", "2026-09-02"])
            profile = compact_profile("iosco_i_scan", path)
        self.assertEqual(profile["format"], "CSV")
        self.assertEqual(profile["row_count"], 2)
        self.assertEqual(profile["column_count"], 3)

    def test_sec_gzip_xml_profile_streams_firm_elements(self):
        xml = b"<IAPDFirmSECReport><Firm/><Firm><Info/></Firm></IAPDFirmSECReport>"
        with TemporaryDirectory() as directory:
            path = Path(directory) / "sec.xml.gz"
            with gzip.open(path, "wb") as file:
                file.write(xml)
            profile = compact_profile("sec_iapd", path)
        self.assertEqual(profile["format"], "GZIP_XML")
        self.assertEqual(profile["root_element"], "IAPDFirmSECReport")
        self.assertEqual(profile["firm_count"], 2)

    def test_iosco_profile_reports_missingness_without_labels(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "iosco.csv"
            with path.open("w", encoding="utf-8-sig", newline="") as file:
                writer = csv.DictWriter(
                    file,
                    fieldnames=[
                        "id",
                        "nca_name",
                        "nca_jurisdiction",
                        "categories_detailed",
                        "url",
                        "other_urls",
                        "domain_name",
                        "fqdn",
                        "email",
                        "social_media",
                        "regulator_claims",
                        "additional_information",
                        "validation_date",
                        "modification_date",
                    ],
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "id": "1",
                        "nca_name": "Regulat\ufffdr",
                        "nca_jurisdiction": "Country",
                        "categories_detailed": "Warning",
                        "url": "https://example.invalid",
                        "validation_date": "2026-09-01",
                        "modification_date": "bad-date",
                    }
                )
            profile = profile_iosco(path)
        self.assertEqual(profile["row_count"], 1)
        self.assertEqual(profile["date_ranges"]["validation_date"]["max"], "2026-09-01")
        self.assertEqual(profile["date_ranges"]["modification_date"]["invalid_count"], 1)
        self.assertEqual(profile["encoding_anomalies"]["unicode_replacement_character_count"], 1)
        self.assertEqual(profile["encoding_anomalies"]["rows_with_unicode_replacement_character"], 1)
        self.assertEqual(profile["encoding_anomalies"]["replacement_characters_by_column"], {"nca_name": 1})
        self.assertIn("not conviction labels", profile["interpretation"])

    def test_sec_profile_counts_reference_fields_without_emitting_names(self):
        xml = (
            b'<IAPDFirmSECReport><Firms><Firm><Info FirmCrdNb="1" SECNb="801-1" '
            b'BusNm="Firm A" LegalNm="Firm A LLC"/><MainAddr State="NY" Cntry="United States"/>'
            b'<Rgstn FirmType="SEC" St="APPROVED" Dt="2020-01-02"/><Filing FormVrsn="10/2023"/>'
            b'<FormInfo><WebAddrs><WebAddr>https://example.invalid</WebAddr></WebAddrs></FormInfo>'
            b'</Firm></Firms></IAPDFirmSECReport>'
        )
        with TemporaryDirectory() as directory:
            path = Path(directory) / "sec.xml.gz"
            with gzip.open(path, "wb") as file:
                file.write(xml)
            profile = profile_sec(path)
        self.assertEqual(profile["firm_count"], 1)
        self.assertEqual(profile["firms_with_web_address"], 1)
        self.assertEqual(profile["duplicate_nonempty_crd_count"], 0)
        self.assertNotIn("Firm A", json.dumps(profile))


if __name__ == "__main__":
    unittest.main()
