"""Materialize the independent blinded SEC EDGAR/IAPD second review v2.

This script intentionally reads one frozen blinded packet and creates one review
artifact using exclusive-create semantics. It does not consult primary-review
materials, networks, model outputs, or validation/test data.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


INPUT_PATH = Path(
    r"D:\nckh 2026-2027\ISI_Data\derived\target_text_corpus_v1_reference_inputs"
    r"\sec_edgar_iapd_post_capture_grouping_result_v2\blind_second_review_packet_v2.json"
)
OUTPUT_PATH = Path(
    r"D:\nckh 2026-2027\ISI_Data\derived\target_text_corpus_v1_reference_inputs"
    r"\sec_edgar_iapd_post_capture_grouping_result_v2\blind_second_review_v2.json"
)
EXPECTED_INPUT_SHA256 = "b56f5f674e31eb8559cb36cdac1a661dc210fba8350fdc61f87a5ac35fd6af51"


LEGITIMATE_SERVICE_FACTS = {
    "TTCV1_EDGAR_AVAIL_DEV_005": "The capture lists institutional investment, portfolio management, mutual funds, and fund administration offerings.",
    "TTCV1_EDGAR_AVAIL_DEV_006": "The capture says Pflug Koory provides professional investment advice and counsel and is an SEC-registered investment adviser.",
    "TTCV1_EDGAR_AVAIL_DEV_008": "The capture describes management of investment accounts and retirement plans, portfolio management, and retirement planning.",
    "TTCV1_EDGAR_AVAIL_DEV_009": "The capture describes financial planning, portfolio design, retirement-income planning, and ongoing investment management.",
    "TTCV1_EDGAR_AVAIL_DEV_011": "The capture includes investment concepts and named fund offerings under the Keywise Capital Management brand.",
    "TTCV1_EDGAR_AVAIL_DEV_013": "The capture describes comprehensive wealth management, investment management, and retirement planning.",
    "TTCV1_EDGAR_AVAIL_DEV_014": "The capture describes a fee-based advisory network, investment-platform guidance, and support for advisory firms.",
    "TTCV1_EDGAR_AVAIL_DEV_015": "The capture describes private wealth management, portfolio management, fixed income, and retirement planning.",
    "TTCV1_EDGAR_AVAIL_DEV_016": "The capture identifies Petredis Investment Advisors and provides advisory-oriented navigation for its approach, solutions, disclosures, and client login.",
    "TTCV1_EDGAR_AVAIL_DEV_018": "The capture offers customized holistic retirement strategies and expressly describes fiduciary advice.",
    "TTCV1_EDGAR_AVAIL_DEV_020": "The capture says the firm manages client portfolios and identifies private-wealth, institutional, endowment, and retirement-plan services.",
    "TTCV1_EDGAR_AVAIL_DEV_026": "The capture calls Longview a registered investment advisory firm and describes wealth management and investment strategy services.",
    "TTCV1_EDGAR_AVAIL_DEV_027": "The capture lists financial planning, investment management, and protection and risk-management services.",
    "TTCV1_EDGAR_AVAIL_DEV_028": "The capture says the firm actively manages accounts with quantitative strategies and offers multiple investment account types.",
    "TTCV1_EDGAR_AVAIL_DEV_029": "The capture identifies Ponta as a registered investment adviser and describes its advisory services and investment-risk disclosures.",
    "TTCV1_EDGAR_AVAIL_DEV_032": "The capture says Nerad + Deppe manages investment portfolios and provides fee-only wealth management and financial advice.",
    "TTCV1_EDGAR_AVAIL_DEV_033": "The capture describes fiduciary financial planning and investment management for individuals, retirees, and business owners.",
    "TTCV1_EDGAR_AVAIL_DEV_034": "The capture describes bespoke wealth planning, investment consulting, discretionary accounts, and institutional solutions.",
    "TTCV1_EDGAR_AVAIL_DEV_035": "The capture says the advisers oversee research, trade execution, portfolio allocation, and long-term investing for client assets.",
    "TTCV1_EDGAR_AVAIL_DEV_040": "The capture identifies an SEC-registered investment adviser providing personalized investment management.",
    "TTCV1_EDGAR_AVAIL_DEV_050": "The capture identifies Steginsky Capital as an SEC-registered investment adviser and explains its concentrated public-equity strategy.",
    "TTCV1_EDGAR_AVAIL_DEV_053": "The capture describes wealth management, dynamic wealth strategies, and investment strategies under the Elyxium brand.",
    "TTCV1_EDGAR_AVAIL_DEV_054": "The capture identifies a multi-family office and provides dedicated Investment Strategy and Family Office Services sections.",
    "TTCV1_EDGAR_AVAIL_DEV_063": "The capture says Ocean Endowment provides investment management to endowments, foundations, families, and other long-term investors.",
    "TTCV1_EDGAR_AVAIL_DEV_064": "The capture describes financial planning, investment management, institutionally priced investments, and portfolio services.",
    "TTCV1_EDGAR_AVAIL_DEV_065": "The capture identifies Inspirion as an RIA and describes investment, retirement, tax, estate, and insurance planning.",
    "TTCV1_EDGAR_AVAIL_DEV_068": "The capture identifies NuVerse Advisors as an SEC-registered investment-management and wealth-advisory firm.",
    "TTCV1_EDGAR_AVAIL_DEV_070": "The capture identifies Aureum as an SEC-registered adviser and describes portfolio design, investing, and retirement-plan services.",
    "TTCV1_EDGAR_AVAIL_DEV_071": "The capture identifies Wilkins Investment Counsel and presents its investment philosophy, process, team, and market outlook.",
    "TTCV1_EDGAR_AVAIL_DEV_074": "The capture identifies Trium Capital as an alternative-asset manager and describes multiple fund and investment strategies.",
    "TTCV1_EDGAR_AVAIL_DEV_076": "The capture identifies Gratus as an SEC-registered investment adviser and describes wealth-advisory services.",
    "TTCV1_EDGAR_AVAIL_DEV_082": "The capture states that Laraway Financial Advisors offers investment-advisory services and describes investment management and planning.",
    "TTCV1_EDGAR_AVAIL_DEV_086": "The capture identifies Traub Capital Management as a registered investment adviser offering investment management and planning.",
    "TTCV1_EDGAR_AVAIL_DEV_089": "The capture identifies Farrow as a fee-only registered investment adviser offering portfolio management and financial planning.",
    "TTCV1_EDGAR_AVAIL_HOLDOUT_001": "The capture identifies Miller Wealth Advisors as an RIA and describes retirement planning and individual portfolio management.",
    "TTCV1_EDGAR_AVAIL_HOLDOUT_002": "The capture says Incision Capital manages an equity long-short strategy focused on natural resources.",
    "TTCV1_EDGAR_AVAIL_HOLDOUT_003": "The capture explicitly names Christensen King & Associates Investment Services and describes investment management and financial advising.",
    "TTCV1_EDGAR_AVAIL_HOLDOUT_007": "The capture identifies Ledgewood as an SEC-registered investment adviser and describes tailored strategies and investment concepts.",
    "TTCV1_EDGAR_AVAIL_HOLDOUT_009": "The capture identifies Intercarolina as both broker-dealer and investment adviser and details its advisory and securities services.",
    "TTCV1_EDGAR_AVAIL_HOLDOUT_013": "The capture identifies Cordatus as a registered investment adviser providing money management and objective financial advice.",
    "TTCV1_EDGAR_AVAIL_HOLDOUT_017": "The capture identifies Goodnow Investment Group and describes its long-short and long-only equity-investing approach.",
    "TTCV1_EDGAR_AVAIL_HOLDOUT_019": "The capture identifies Lykos Global Management as an event-driven fundamental investment firm spanning private and public markets.",
    "TTCV1_EDGAR_AVAIL_HOLDOUT_021": "The capture names Rainey & Randall Wealth Advisors and expressly describes strategic wealth planning.",
    "TTCV1_EDGAR_AVAIL_HOLDOUT_022": "The capture identifies CastleArk Management as a registered investment adviser and describes multiple equity and energy strategies.",
}


UNCERTAIN_OVERRIDES: dict[str, dict[str, Any]] = {
    "TTCV1_EDGAR_AVAIL_DEV_010": {
        "assessments": {
            "identity_linkage": "PASS",
            "task_relevance": "UNCERTAIN",
            "capture_chronology": "PASS",
            "repurpose_or_parking": "PASS",
            "contradiction_screen": "PASS",
        },
        "supporting_facts": [
            "The capture names Mantle Ridge and carries a Mantle Ridge LP copyright notice on mantleridge.com.",
            "The 261-character capture contains only navigation, a stewardship tagline, and contact/copyright framing.",
        ],
        "uncertainty_reasons": [
            "The sparse capture does not independently describe investment management, advisory services, a fund, or another task-relevant financial activity."
        ],
        "rationale": "Identity is supported, but source membership and a stewardship slogan are insufficient to establish investment/advisory task relevance from the capture itself.",
    },
    "TTCV1_EDGAR_AVAIL_DEV_022": {
        "assessments": {
            "identity_linkage": "UNCERTAIN",
            "task_relevance": "PASS",
            "capture_chronology": "PASS",
            "repurpose_or_parking": "UNCERTAIN",
            "contradiction_screen": "UNCERTAIN",
        },
        "supporting_facts": [
            "The captured page is branded Interaudi Bank and describes banking, lending, investments, and wealth management.",
            "The blinded reference identifies Ameraudi Asset Management, while the grouping flags state that the declared canonical host differs from the candidate host.",
        ],
        "uncertainty_reasons": [
            "The capture does not name Ameraudi Asset Management or explain its relationship to Interaudi Bank.",
            "The canonical-host mismatch and different captured brand leave rebranding, affiliation, or domain repurpose unresolved."
        ],
        "rationale": "The content is financially relevant, but the packet alone cannot link the captured Interaudi Bank identity to the referenced Ameraudi Asset Management entity without ambiguity.",
    },
    "TTCV1_EDGAR_AVAIL_DEV_036": {
        "assessments": {
            "identity_linkage": "UNCERTAIN",
            "task_relevance": "PASS",
            "capture_chronology": "PASS",
            "repurpose_or_parking": "PASS",
            "contradiction_screen": "UNCERTAIN",
        },
        "supporting_facts": [
            "The capture consistently uses the CGC Financial Services brand and describes comprehensive financial planning.",
            "The capture's disclosure names CGC Financial Services, Inc., while the blinded official evidence names CGC Financial Services, LLC.",
        ],
        "uncertainty_reasons": [
            "The conflicting legal suffixes (Inc. versus LLC) are not reconciled within the blinded packet."
        ],
        "rationale": "The brand and services align, but the legal-entity contradiction prevents an unqualified identity pass.",
    },
    "TTCV1_EDGAR_AVAIL_DEV_039": {
        "assessments": {
            "identity_linkage": "PASS",
            "task_relevance": "PASS",
            "capture_chronology": "PASS",
            "repurpose_or_parking": "UNCERTAIN",
            "contradiction_screen": "UNCERTAIN",
        },
        "supporting_facts": [
            "Most of the capture names Laidlaw Wealth Management and describes registered investment-advisory and portfolio-management services.",
            "The same capture begins with 'Saylo Construction,' lorem-ipsum text, an example email address, and placeholder telephone details.",
        ],
        "uncertainty_reasons": [
            "Mixed unrelated construction-template content prevents a clean repurpose/template and contradiction screen."
        ],
        "rationale": "The adviser content is substantive, but the captured page contains unresolved template contamination and unrelated identity indicators.",
    },
    "TTCV1_EDGAR_AVAIL_DEV_045": {
        "assessments": {
            "identity_linkage": "UNCERTAIN",
            "task_relevance": "PASS",
            "capture_chronology": "PASS",
            "repurpose_or_parking": "UNCERTAIN",
            "contradiction_screen": "UNCERTAIN",
        },
        "supporting_facts": [
            "The capture is branded Thames Financial Management and describes portfolio management, retirement planning, and investment recommendations.",
            "The blinded official evidence names CDM Financial Counseling Services, Inc.; the capture does not mention CDM or state a DBA, merger, or rebrand relationship.",
        ],
        "uncertainty_reasons": [
            "The different captured and referenced entity names are not linked by evidence inside the packet.",
            "An unverified rebrand or domain repurpose remains possible."
        ],
        "rationale": "The page is task-relevant, but the packet does not resolve the identity transition from CDM Financial Counseling Services to Thames Financial Management.",
    },
    "TTCV1_EDGAR_AVAIL_DEV_058": {
        "assessments": {
            "identity_linkage": "UNCERTAIN",
            "task_relevance": "PASS",
            "capture_chronology": "PASS",
            "repurpose_or_parking": "PASS",
            "contradiction_screen": "UNCERTAIN",
        },
        "supporting_facts": [
            "The capture uses the Illuminate brand and describes managed sustainable-investment portfolios.",
            "The capture's legal disclosure names Illuminate Advisers, LLC, while the SEC evidence names Illuminate, Inc.",
        ],
        "uncertainty_reasons": [
            "The packet does not explain the legal relationship between Illuminate Advisers, LLC and Illuminate, Inc."
        ],
        "rationale": "Brand and task relevance are clear, but the distinct legal entities prevent an unqualified identity and contradiction pass.",
    },
    "TTCV1_EDGAR_AVAIL_DEV_061": {
        "assessments": {
            "identity_linkage": "UNCERTAIN",
            "task_relevance": "PASS",
            "capture_chronology": "PASS",
            "repurpose_or_parking": "UNCERTAIN",
            "contradiction_screen": "UNCERTAIN",
        },
        "supporting_facts": [
            "The capture is branded Vantage Wealth Planning and describes financial planning, asset management, and retirement-plan management.",
            "The blinded official evidence names KRM Wealth Management L.L.C.; KRM is not named in the captured text.",
        ],
        "uncertainty_reasons": [
            "The packet does not document a DBA, rebrand, merger, or other relationship between KRM Wealth Management and Vantage Wealth Planning.",
            "A domain repurpose or unresolved brand transition cannot be excluded."
        ],
        "rationale": "The capture is task-relevant but does not independently link the Vantage brand to the referenced KRM entity.",
    },
    "TTCV1_EDGAR_AVAIL_DEV_067": {
        "assessments": {
            "identity_linkage": "UNCERTAIN",
            "task_relevance": "PASS",
            "capture_chronology": "UNCERTAIN",
            "repurpose_or_parking": "PASS",
            "contradiction_screen": "PASS",
        },
        "supporting_facts": [
            "The capture is a broad John Hancock corporate homepage covering insurance, investments, and retirement products.",
            "The referenced entity is the specific subsidiary John Hancock Variable Trust Advisers LLC, which is not named in the capture.",
        ],
        "uncertainty_reasons": [
            "The corporate-brand capture does not establish linkage to the specific referenced adviser entity.",
            "The 2019 capture predates the 2026 official-reference observation by more than seven years and provides no entity-specific continuity evidence."
        ],
        "rationale": "The broad corporate site is financially relevant, but it is not specific enough in identity or time to support the referenced adviser entity without qualification.",
    },
    "TTCV1_EDGAR_AVAIL_DEV_069": {
        "assessments": {
            "identity_linkage": "UNCERTAIN",
            "task_relevance": "PASS",
            "capture_chronology": "PASS",
            "repurpose_or_parking": "UNCERTAIN",
            "contradiction_screen": "UNCERTAIN",
        },
        "supporting_facts": [
            "The capture is branded Seamans Holdings and describes public/private and impact-investment activity.",
            "The blinded official evidence names Seamans Capital Management, LLC, which does not appear in the capture.",
        ],
        "uncertainty_reasons": [
            "The packet does not state whether Seamans Holdings is a DBA, parent, successor, or separate entity from Seamans Capital Management.",
            "An unresolved brand transition or domain repurpose remains possible."
        ],
        "rationale": "Investment relevance is clear, but the captured identity is not explicitly connected to the referenced legal entity.",
    },
    "TTCV1_EDGAR_AVAIL_DEV_090": {
        "assessments": {
            "identity_linkage": "UNCERTAIN",
            "task_relevance": "PASS",
            "capture_chronology": "PASS",
            "repurpose_or_parking": "UNCERTAIN",
            "contradiction_screen": "UNCERTAIN",
        },
        "supporting_facts": [
            "The capture identifies Leviticus Partners, L.P. as a hedge-fund website and includes investing-oriented navigation.",
            "The blinded official evidence names AMH Equity Ltd; that entity is absent from the 393-character capture.",
        ],
        "uncertainty_reasons": [
            "No evidence in the packet links Leviticus Partners, L.P. to AMH Equity Ltd.",
            "The distinct captured brand and sparse text leave a rebrand, affiliate relationship, or domain repurpose unresolved."
        ],
        "rationale": "The page is investment-related, but its captured identity materially differs from the referenced entity and the packet does not reconcile them.",
    },
    "TTCV1_EDGAR_AVAIL_HOLDOUT_012": {
        "assessments": {
            "identity_linkage": "PASS",
            "task_relevance": "UNCERTAIN",
            "capture_chronology": "PASS",
            "repurpose_or_parking": "UNCERTAIN",
            "contradiction_screen": "UNCERTAIN",
        },
        "supporting_facts": [
            "The 48-character capture exactly names Bayesian Capital Management, LP on bayesian.capital.",
            "The capture contains no service description, strategy, disclosure, contact information, or other substantive page content.",
        ],
        "uncertainty_reasons": [
            "The entity name alone does not independently establish investment/advisory task relevance.",
            "The extremely sparse capture is insufficient to screen for parking, repurpose, or material contradictions."
        ],
        "rationale": "Exact naming supports identity, but the near-empty capture cannot satisfy the remaining substantive review gates.",
    },
    "TTCV1_EDGAR_AVAIL_HOLDOUT_020": {
        "assessments": {
            "identity_linkage": "PASS",
            "task_relevance": "UNCERTAIN",
            "capture_chronology": "PASS",
            "repurpose_or_parking": "UNCERTAIN",
            "contradiction_screen": "UNCERTAIN",
        },
        "supporting_facts": [
            "The 185-character capture exactly names Hook Mill Capital Partners, LP and provides an email address at hookmillcapital.com.",
            "The capture contains no description of investment, advisory, fund, or portfolio-management activity.",
        ],
        "uncertainty_reasons": [
            "The name and contact line alone do not independently establish task relevance.",
            "The sparse content is insufficient for a complete repurpose and contradiction screen."
        ],
        "rationale": "Identity is supported, but the capture lacks substantive business content needed to pass all remaining gates.",
    },
}


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def legitimate_review(record: dict[str, Any], service_fact: str) -> dict[str, Any]:
    record_id = record["record_id"]
    host = record["candidate_identity"]["candidate_host"]
    entity = record["official_evidence"]["iapd"]["entity_name_from_reference"]
    snapshot = record["capture"]["snapshot_timestamp"]
    observed = record["official_evidence"]["iapd"]["reference_observed_at"]
    return {
        "record_id": record_id,
        "shortlist_id": record["shortlist_id"],
        "cohort": record["cohort"],
        "candidate_host": host,
        "second_recommendation": "LEGITIMATE",
        "assessments": {
            "identity_linkage": "PASS",
            "task_relevance": "PASS",
            "capture_chronology": "PASS",
            "repurpose_or_parking": "PASS",
            "contradiction_screen": "PASS",
        },
        "supporting_facts": [
            f"The captured page identifies the operating entity or brand on {host}; the blinded official evidence links that exact single host to {entity}.",
            service_fact,
            f"The archived snapshot timestamp {snapshot} predates the official-reference observation {observed}, and the packet shows no conflicting chronology.",
        ],
        "uncertainty_reasons": [],
        "rationale": "Captured identity and substantive investment/advisory content align with the blinded provenance. The packet shows no parking, repurpose, chronology, or material contradiction indicator.",
        "ground_truth_status": "UNCERTAIN",
        "label_created": False,
        "training_eligible": "NO",
    }


def uncertain_review(record: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    return {
        "record_id": record["record_id"],
        "shortlist_id": record["shortlist_id"],
        "cohort": record["cohort"],
        "candidate_host": record["candidate_identity"]["candidate_host"],
        "second_recommendation": "UNCERTAIN",
        "assessments": override["assessments"],
        "supporting_facts": override["supporting_facts"],
        "uncertainty_reasons": override["uncertainty_reasons"],
        "rationale": override["rationale"],
        "ground_truth_status": "UNCERTAIN",
        "label_created": False,
        "training_eligible": "NO",
    }


def main() -> None:
    input_bytes = INPUT_PATH.read_bytes()
    input_sha256 = sha256_bytes(input_bytes)
    if input_sha256 != EXPECTED_INPUT_SHA256:
        raise RuntimeError(
            f"Frozen packet hash mismatch: expected {EXPECTED_INPUT_SHA256}, got {input_sha256}"
        )

    packet = json.loads(input_bytes.decode("utf-8"))
    records = packet["records"]
    if packet.get("record_count") != 56 or len(records) != 56:
        raise RuntimeError("Expected exactly 56 blinded records")

    record_ids = [record["record_id"] for record in records]
    if len(record_ids) != len(set(record_ids)):
        raise RuntimeError("Duplicate record_id in blinded packet")

    configured_ids = set(LEGITIMATE_SERVICE_FACTS) | set(UNCERTAIN_OVERRIDES)
    if configured_ids != set(record_ids):
        missing = sorted(set(record_ids) - configured_ids)
        extra = sorted(configured_ids - set(record_ids))
        raise RuntimeError(f"Decision coverage mismatch: missing={missing}, extra={extra}")
    if set(LEGITIMATE_SERVICE_FACTS) & set(UNCERTAIN_OVERRIDES):
        raise RuntimeError("A record cannot be both LEGITIMATE and UNCERTAIN")

    reviews: list[dict[str, Any]] = []
    for record in records:
        record_id = record["record_id"]
        if record_id in UNCERTAIN_OVERRIDES:
            review = uncertain_review(record, UNCERTAIN_OVERRIDES[record_id])
        else:
            review = legitimate_review(record, LEGITIMATE_SERVICE_FACTS[record_id])
        reviews.append(review)

    for review in reviews:
        recommendation = review["second_recommendation"]
        if recommendation not in {"LEGITIMATE", "UNCERTAIN"}:
            raise RuntimeError(f"Disallowed recommendation for {review['record_id']}")
        if review["ground_truth_status"] != "UNCERTAIN":
            raise RuntimeError(f"Ground-truth status changed for {review['record_id']}")
        if review["label_created"] is not False or review["training_eligible"] != "NO":
            raise RuntimeError(f"Safety invariant failed for {review['record_id']}")
        if recommendation == "LEGITIMATE":
            if set(review["assessments"].values()) != {"PASS"}:
                raise RuntimeError(f"LEGITIMATE record lacks five PASS assessments: {review['record_id']}")
            if len(review["supporting_facts"]) < 2 or review["uncertainty_reasons"]:
                raise RuntimeError(f"LEGITIMATE evidence invariant failed: {review['record_id']}")
        elif not review["uncertainty_reasons"]:
            raise RuntimeError(f"UNCERTAIN record lacks concrete reasons: {review['record_id']}")

    counts = {
        "LEGITIMATE": sum(r["second_recommendation"] == "LEGITIMATE" for r in reviews),
        "UNCERTAIN": sum(r["second_recommendation"] == "UNCERTAIN" for r in reviews),
    }
    if counts != {"LEGITIMATE": 44, "UNCERTAIN": 12}:
        raise RuntimeError(f"Unexpected recommendation counts: {counts}")

    artifact = {
        "review_id": "ISI_SEC_EDGAR_IAPD_BLIND_SECOND_REVIEW_V2",
        "status": "COMPLETE_INDEPENDENT_BLIND_SECOND_REVIEW",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "input_packet_path": str(INPUT_PATH),
        "input_packet_sha256": input_sha256,
        "input_packet_id": packet.get("packet_id"),
        "reviewer_mode": "INDEPENDENT_BLIND_AI_REVIEW",
        "primary_decisions_visible": False,
        "network_access_used": False,
        "model_predictions_visible": False,
        "source_membership_treated_as_ground_truth": False,
        "review_contract": {
            "allowed_recommendations": ["LEGITIMATE", "UNCERTAIN"],
            "legitimate_requires_all_five_assessments_pass": True,
            "legitimate_minimum_supporting_facts": 2,
            "legitimate_allows_uncertainty_reasons": False,
            "recommendation_is_not_a_final_label": True,
            "ground_truth_status_for_all_records": "UNCERTAIN",
            "label_created_for_all_records": False,
            "training_eligible_for_all_records": "NO",
        },
        "record_count": len(reviews),
        "recommendation_counts": counts,
        "records": reviews,
        "immutability": {
            "write_mode": "EXCLUSIVE_CREATE_NO_OVERWRITE",
            "output_path": str(OUTPUT_PATH),
        },
    }

    output_bytes = (json.dumps(artifact, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_PATH.open("xb") as handle:
        handle.write(output_bytes)

    print(f"wrote={OUTPUT_PATH}")
    print(f"records={len(reviews)}")
    print(f"legitimate={counts['LEGITIMATE']}")
    print(f"uncertain={counts['UNCERTAIN']}")
    print(f"input_sha256={input_sha256}")
    print(f"output_sha256={sha256_bytes(output_bytes)}")


if __name__ == "__main__":
    main()
