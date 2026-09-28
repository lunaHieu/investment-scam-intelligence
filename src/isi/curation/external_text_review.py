"""Offline evidence comparison for SEC-linked external website captures."""

from __future__ import annotations

import gzip
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import urlparse

from src.isi.normalization.external_text import identity_token_check, normalize_identity


def normalize_host(value: str) -> str | None:
    candidate = value.strip()
    if not candidate:
        return None
    if "://" not in candidate:
        candidate = "https://" + candidate
    parsed = urlparse(candidate)
    host = (parsed.hostname or "").casefold().rstrip(".")
    if host.startswith("www."):
        host = host[4:]
    return host or None


def extract_sec_firm_profiles(path: Path, crd_numbers: set[str]) -> dict[str, dict[str, object]]:
    """Stream only requested firms from the immutable SEC/IAPD gzip feed."""

    profiles: dict[str, dict[str, object]] = {}
    with gzip.open(path, "rb") as handle:
        for _, element in ET.iterparse(handle, events=("end",)):
            if element.tag.rsplit("}", 1)[-1] != "Firm":
                continue
            info = next(
                (
                    child
                    for child in element.iter()
                    if child.tag.rsplit("}", 1)[-1] == "Info"
                    and child.attrib.get("FirmCrdNb") in crd_numbers
                ),
                None,
            )
            if info is not None:
                crd = str(info.attrib["FirmCrdNb"])
                registration = next(
                    (child for child in element if child.tag.rsplit("}", 1)[-1] == "Rgstn"),
                    None,
                )
                filing = next(
                    (child for child in element if child.tag.rsplit("}", 1)[-1] == "Filing"),
                    None,
                )
                address = next(
                    (child for child in element if child.tag.rsplit("}", 1)[-1] == "MainAddr"),
                    None,
                )
                web_addresses = [
                    (child.text or "").strip()
                    for child in element.iter()
                    if child.tag.rsplit("}", 1)[-1] == "WebAddr" and (child.text or "").strip()
                ]
                profiles[crd] = {
                    "crd": crd,
                    "sec_number": info.attrib.get("SECNb"),
                    "business_name": info.attrib.get("BusNm"),
                    "legal_name": info.attrib.get("LegalNm"),
                    "registration": dict(registration.attrib) if registration is not None else {},
                    "filing": dict(filing.attrib) if filing is not None else {},
                    "main_address": dict(address.attrib) if address is not None else {},
                    "web_addresses": web_addresses,
                    "normalized_web_hosts": sorted(
                        {host for value in web_addresses if (host := normalize_host(value))}
                    ),
                }
            element.clear()
    missing = sorted(crd_numbers - set(profiles))
    if missing:
        raise ValueError(f"SEC/IAPD feed is missing requested CRD numbers: {missing}")
    return profiles


def _contact_matches(address: dict[str, str], text: str) -> dict[str, object]:
    normalized_text = normalize_identity(text)
    text_digits = re.sub(r"\D", "", text)
    checks: dict[str, bool] = {}
    for source_field, label in (
        ("Strt1", "street"),
        ("City", "city"),
        ("PostlCd", "postal_code"),
    ):
        value = address.get(source_field)
        if value:
            checks[label] = normalize_identity(value) in normalized_text
    phone = re.sub(r"\D", "", address.get("PhNb", ""))
    if phone:
        checks["phone"] = phone[-10:] in text_digits
    fax = re.sub(r"\D", "", address.get("FaxNb", ""))
    if fax:
        checks["fax"] = fax[-10:] in text_digits
    return {
        "checks": checks,
        "matched_count": sum(checks.values()),
        "available_count": len(checks),
    }


def assess_capture_record(record: dict[str, object], sec_profile: dict[str, object]) -> dict[str, object]:
    artifact = record["artifact"]
    text = str(artifact["text"])
    artifact_host = normalize_host(str(artifact["url"]))
    names = list(
        dict.fromkeys(
            str(value)
            for value in (sec_profile.get("business_name"), sec_profile.get("legal_name"))
            if value
        )
    )
    identity = identity_token_check(names, text)
    host_exact = artifact_host in sec_profile.get("normalized_web_hosts", [])
    registration = sec_profile.get("registration", {})
    approved_registered = (
        registration.get("FirmType") == "Registered"
        and registration.get("St") == "APPROVED"
    )
    contacts = _contact_matches(sec_profile.get("main_address", {}), text)
    identity_likely = bool(host_exact and identity["any_full_token_match"] and approved_registered)
    if identity_likely and contacts["matched_count"] >= 2:
        recommendation_confidence = "HIGH"
    elif identity_likely:
        recommendation_confidence = "MEDIUM_HIGH"
    else:
        recommendation_confidence = "LOW"
    return {
        "case_id": record.get("case_id"),
        "current_state": {
            "ground_truth_status": record.get("ground_truth_status"),
            "label_confidence": record.get("label_confidence"),
            "review_status": record.get("review_status"),
        },
        "sec_profile": sec_profile,
        "comparison": {
            "artifact_host": artifact_host,
            "host_exactly_listed_in_sec_filing": host_exact,
            "registered_and_approved": approved_registered,
            "identity_token_check": identity,
            "contact_field_check": contacts,
            "visible_text_characters": len(text),
        },
        "ai_first_pass": {
            "recommended_identity_relationship": "SAME_ENTITY_LIKELY" if identity_likely else "UNCLEAR",
            "recommended_evidence_assessment": "REGISTRATION_RELEVANT" if host_exact else "INSUFFICIENT_EVIDENCE",
            "recommended_outcome_for_human_review": "LEGITIMATE" if identity_likely else "UNCERTAIN",
            "recommendation_confidence": recommendation_confidence,
            "counts_as_label": False,
            "counts_as_human_review": False,
            "rationale": (
                "The captured host is exactly listed in the SEC filing, the firm name is present in "
                "the captured page text, and the filing reports Registered/APPROVED status. "
                "Human review must still confirm identity/control and resolve contradictory evidence."
                if identity_likely
                else "The automatic identity and registration checks are insufficient for a legitimate recommendation."
            ),
        },
        "human_review_required": [
            "Inspect the exact raw HTML capture and extracted text.",
            "Confirm the SEC/IAPD record, CRD, legal name, and filed website.",
            "Check for evidence of impersonation, compromise, or contradictory regulator action.",
            "Only then decide LEGITIMATE/HIGH/RECONCILED or leave UNCERTAIN.",
        ],
    }
