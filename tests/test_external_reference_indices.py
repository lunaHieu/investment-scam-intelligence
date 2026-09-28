import csv
import gzip
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from scripts.build_external_reference_indices import ensure_outputs_do_not_exist
from src.isi.normalization.external_references import (
    build_iosco_index,
    build_sec_index,
    canonicalize_host,
    extract_hosts,
    normalize_entity_name,
)


ROOT = Path(__file__).resolve().parents[1]


class ExternalReferenceIndexTests(unittest.TestCase):
    @staticmethod
    def nested_keys(value):
        if isinstance(value, dict):
            return set(value).union(*(ExternalReferenceIndexTests.nested_keys(item) for item in value.values()))
        if isinstance(value, list):
            return set().union(*(ExternalReferenceIndexTests.nested_keys(item) for item in value))
        return set()

    def test_entity_name_normalization_is_unicode_aware_and_rejects_replacement_character(self):
        self.assertEqual(normalize_entity_name("  Công ty—ABC, LLC  "), "công ty abc llc")
        self.assertEqual(normalize_entity_name("ＡＢＣ Capital"), "abc capital")
        self.assertIsNone(normalize_entity_name("Broken \ufffd name"))

    def test_host_canonicalization_is_offline_and_conservative(self):
        self.assertEqual(canonicalize_host("HTTPS://WWW.Example.COM/path?q=1"), "example.com")
        self.assertEqual(canonicalize_host("t\u00e9st.example"), "xn--tst-bma.example")
        self.assertEqual(canonicalize_host("192.0.2.1:443"), "192.0.2.1")
        self.assertIsNone(canonicalize_host("user@example.com"))
        self.assertIsNone(canonicalize_host("not a host"))

    def test_host_extraction_handles_noisy_multi_url_fields_without_query_false_positive(self):
        hosts = extract_hosts([
            "https://client.capfins.com/, https://trading.capfins.com/",
            "https://ctongstock.com and https://outpacein.xyz",
            "https://play.google.com/store/apps/details?id=com.pionex.client",
        ])
        self.assertEqual(
            hosts,
            ["client.capfins.com", "ctongstock.com", "outpacein.xyz", "play.google.com", "trading.capfins.com"],
        )
        self.assertNotIn("com.pionex.client", hosts)

    def test_iosco_index_excludes_narratives_and_creates_no_labels(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            raw = root / "iosco.csv"
            output = root / "iosco.jsonl"
            fields = [
                "id", "nca_name", "nca_jurisdiction", "commercial_name",
                "other_commercial_names", "corporate_names", "url", "other_urls",
                "domain_name", "fqdn", "categories", "categories_detailed",
                "validation_date", "modification_date", "nca_url", "additional_information",
            ]
            with raw.open("w", encoding="utf-8-sig", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=fields)
                writer.writeheader()
                writer.writerow({
                    "id": "7", "nca_name": "Regulator", "nca_jurisdiction": "Country",
                    "commercial_name": "Example Capital LLC", "url": "https://www.example.com/a",
                    "categories": "1", "categories_detailed": "Warning",
                    "validation_date": "2026-09-01", "nca_url": "https://regulator.example/7",
                    "additional_information": "DO NOT COPY THIS NARRATIVE",
                })
            summary = build_iosco_index(raw, output, source_version="test", raw_sha256="a" * 64)
            record = json.loads(output.read_text(encoding="utf-8").strip())
        self.assertEqual(summary["record_count"], 1)
        self.assertEqual(record["entity_name_keys"], ["example capital llc"])
        self.assertEqual(record["observed_hosts"], ["example.com"])
        serialized = json.dumps(record)
        self.assertNotIn("DO NOT COPY", serialized)
        self.assertFalse(any("label" in key.casefold() for key in self.nested_keys(record)))

    def test_sec_index_keeps_public_identity_reference_but_excludes_contact_data(self):
        xml = (
            b'<IAPDFirmSECReport><Firms><Firm><Info FirmCrdNb="1" SECNb="801-1" '
            b'BusNm="Firm A" LegalNm="Firm A LLC"/><MainAddr PhNb="555-0100" Strt1="Secret"/>'
            b'<Rgstn FirmType="SEC" St="APPROVED" Dt="2020-01-02"/>'
            b'<Filing Dt="2026-09-22" FormVrsn="10/2023"/><WebAddrs>'
            b'<WebAddr>https://www.example.com</WebAddr></WebAddrs></Firm></Firms></IAPDFirmSECReport>'
        )
        with TemporaryDirectory() as directory:
            root = Path(directory)
            raw = root / "sec.xml.gz"
            output = root / "sec.jsonl"
            with gzip.open(raw, "wb") as handle:
                handle.write(xml)
            summary = build_sec_index(raw, output, source_version="test", raw_sha256="b" * 64)
            record = json.loads(output.read_text(encoding="utf-8").strip())
        self.assertEqual(summary["record_count"], 1)
        self.assertEqual(record["source_record_id"], "1")
        self.assertEqual(record["observed_hosts"], ["example.com"])
        serialized = json.dumps(record)
        self.assertNotIn("555-0100", serialized)
        self.assertNotIn("Secret", serialized)
        self.assertFalse(any("label" in key.casefold() for key in self.nested_keys(record)))

    def test_builder_refuses_to_overwrite_any_frozen_output(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "exists.jsonl"
            path.write_text("frozen\n", encoding="utf-8")
            with self.assertRaises(FileExistsError):
                ensure_outputs_do_not_exist([path])

    def test_checked_in_registries_keep_all_automatic_decisions_blocked(self):
        for name, source_id, count in (
            ("iosco_warning_reference_index_v1.json", "iosco_i_scan", 47001),
            ("sec_iapd_reference_index_v1.json", "sec_iapd", 23927),
        ):
            registry = json.loads((ROOT / "registry" / "analyses" / name).read_text(encoding="utf-8"))
            self.assertEqual(registry["source_id"], source_id)
            self.assertEqual(registry["coverage"]["record_count"], count)
            self.assertFalse(registry["safety_contract"]["training_allowed"])
            self.assertFalse(registry["safety_contract"]["domain_access_allowed"])
            self.assertFalse(registry["safety_contract"]["automatic_entity_resolution_allowed"])
            self.assertTrue(registry["safety_contract"]["manual_evidence_review_required"])


if __name__ == "__main__":
    unittest.main()
