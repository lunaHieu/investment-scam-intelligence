import gzip
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from src.isi.curation.external_text_review import assess_capture_record, extract_sec_firm_profiles


class ExternalTextReviewTests(unittest.TestCase):
    def test_extract_and_assess_exact_sec_identity(self):
        xml = b'''<IAPDFirmSECReport><Firm><Info FirmCrdNb="123" SECNb="801-123"
        BusNm="PARAGON FINANCIAL SERVICES" LegalNm="PARAGON FINANCIAL SERVICES"/>
        <MainAddr Strt1="3761 WESTERRE PARKWAY" City="RICHMOND" State="VA"
        PostlCd="23233" PhNb="804-673-8888"/><Rgstn FirmType="Registered"
        St="APPROVED" Dt="2019-12-09"/><Filing Dt="2026-07-21"/>
        <FormInfo><WebAddr>HTTP://WWW.PARAGONFINANCIAL.COM/</WebAddr></FormInfo>
        </Firm></IAPDFirmSECReport>'''
        with TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "sec.xml.gz"
            with gzip.open(path, "wb") as handle:
                handle.write(xml)
            profiles = extract_sec_firm_profiles(path, {"123"})
        record = {
            "case_id": "CASE_TEST",
            "ground_truth_status": "UNCERTAIN",
            "label_confidence": "LOW",
            "review_status": "IN_REVIEW",
            "artifact": {
                "source_record_id": "123",
                "url": "https://www.paragonfinancial.com/",
                "text": (
                    "Paragon Financial Services, 3761 Westerre Parkway, Richmond VA 23233, "
                    "telephone 804-673-8888."
                ),
            },
        }
        result = assess_capture_record(record, profiles["123"])
        self.assertTrue(result["comparison"]["host_exactly_listed_in_sec_filing"])
        self.assertTrue(result["comparison"]["registered_and_approved"])
        self.assertGreaterEqual(result["comparison"]["contact_field_check"]["matched_count"], 3)
        self.assertEqual(
            result["ai_first_pass"]["recommended_identity_relationship"],
            "SAME_ENTITY_LIKELY",
        )
        self.assertEqual(
            result["ai_first_pass"]["recommended_outcome_for_human_review"],
            "LEGITIMATE",
        )
        self.assertFalse(result["ai_first_pass"]["counts_as_label"])
        self.assertFalse(result["ai_first_pass"]["counts_as_human_review"])


if __name__ == "__main__":
    unittest.main()
