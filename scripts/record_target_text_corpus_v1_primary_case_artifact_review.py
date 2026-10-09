"""Record the authorized primary review from the frozen local-evidence packet."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected object: {path}")
    return value


def judgment(
    recommendation: str,
    identity: str,
    relevance: str,
    chronology: str,
    repurpose: str,
    contradiction: str,
    facts: list[str],
    rationale: str,
    uncertainty: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "primary_recommendation": recommendation,
        "assessments": {
            "identity_linkage": identity,
            "task_relevance": relevance,
            "capture_chronology": chronology,
            "repurpose_or_parking": repurpose,
            "contradiction_screen": contradiction,
        },
        "supporting_facts": facts,
        "uncertainty_reasons": uncertainty or [],
        "rationale": rationale,
        "ground_truth_status": "UNCERTAIN",
        "label_created": False,
        "training_eligible": "NO",
    }


JUDGMENTS: dict[str, dict[str, Any]] = {
    "TTCV1_CAND_CONF_CFTC_001": judgment(
        "CONFIRMED", "PASS", "PASS", "PASS", "PASS", "PASS",
        [
            "The capture names Allgo Trade and repeatedly solicits binary-options accounts and trading.",
            "The frozen CFTC RED record names Allgo Trading and prints allgotrade.com as the exact web address.",
        ],
        "The archived artifact, advertised financial activity, exact host, and named CFTC RED entity align without a parking, repurpose, or identity contradiction signal. This supports a primary CONFIRMED recommendation only.",
    ),
    "TTCV1_CAND_CONF_CFTC_004": judgment(
        "CONFIRMED", "PASS", "PASS", "PASS", "PASS", "PASS",
        [
            "The capture identifies 2options and presents a binary-options trading platform with account and deposit actions.",
            "The frozen CFTC RED record names 2 Options and prints 2options.com as the exact web address.",
        ],
        "The captured trading solicitation has exact name-and-host alignment with the frozen CFTC warning evidence, and no captured parking, repurpose, or conflicting operator signal remains. This is a primary recommendation, not a final label.",
    ),
    "TTCV1_CAND_CONF_CFTC_006": judgment(
        "UNCERTAIN", "UNCERTAIN", "FAIL", "UNCERTAIN", "FAIL", "UNCERTAIN",
        [
            "The only visible captured content is a NameBright notice stating that 24optionforex.com expired.",
            "The frozen CFTC RED record links 24OptionForex Investment Group to the exact host, but the capture contains no target operator or investment offer.",
        ],
        "The official record supports historical host linkage, but the captured artifact is only an expired-domain parking notice. It cannot establish that the reviewed text belongs to the warned investment operation, so the case must remain UNCERTAIN.",
        ["Expired-domain capture has no substantive target artifact or resolvable operator identity."],
    ),
    "TTCV1_CAND_CONF_CFTC_009": judgment(
        "UNCERTAIN", "FAIL", "FAIL", "UNCERTAIN", "FAIL", "FAIL",
        [
            "The capture presents a Chinese petroleum-equipment company and unrelated product information.",
            "The frozen CFTC RED record links 1Billion Forex to 1billionforex.com, but that identity and activity are absent from the capture.",
        ],
        "The observed artifact conflicts with the warned forex identity and is unrelated to investment solicitation. The host appears repurposed or otherwise serving unrelated content, so source-list membership cannot be transferred to this text and the recommendation remains UNCERTAIN.",
        ["Captured operator and subject matter conflict with the warned entity, indicating repurpose or unresolved host control."],
    ),
    "TTCV1_CAND_CONF_REG_003": judgment(
        "CONFIRMED", "PASS", "PASS", "PASS", "PASS", "PASS",
        [
            "The capture names Hamstech LLC and solicits cryptocurrency, forex, stock, and real-estate investments.",
            "The frozen IOSCO/FMA warning row names Hamstech LLC, records hamstechllc.com, and includes unregistered and fraud-related categories.",
        ],
        "The artifact has exact entity-and-host alignment with the official warning row and contains direct investment solicitation. No parking, repurpose, or contradictory identity is visible, supporting a conservative primary CONFIRMED recommendation.",
    ),
    "TTCV1_CAND_CONF_REG_007": judgment(
        "CONFIRMED", "PASS", "PASS", "PASS", "PASS", "PASS",
        [
            "The capture identifies Yuan Mao International in Chinese and offers asset management, securities, futures, and investment services.",
            "The frozen SFC warning row names yuan mao internationality and records yuanmaofinancial.com; its validation date is consistent with the March 2023 snapshot.",
        ],
        "The exact warned host, corresponding Yuan Mao identity, investment-service content, and contemporaneous chronology align. With no captured parking, repurpose, or competing operator signal, the artifact supports a primary CONFIRMED recommendation.",
    ),
    "TTCV1_CAND_CONF_REG_008": judgment(
        "UNCERTAIN", "PASS", "FAIL", "FAIL", "UNCERTAIN", "UNCERTAIN",
        [
            "The capture names Sunseeker Energy but describes solar technology and renewable-energy equipment rather than an investment offer.",
            "The frozen SFC warning row names Sunseeker Energy Limited at the same host, but its 2016 validation predates the 2024 capture by more than eight years.",
        ],
        "Name and host align, but the captured content is outside the investment-solicitation task and is far later than the warning evidence. The available material cannot resolve whether this is a changed business, a repurposed domain, or the same warned operation, so it remains UNCERTAIN.",
        ["Non-investment capture and long warning-to-snapshot gap leave repurpose and task relevance unresolved."],
    ),
    "TTCV1_CAND_CONF_REG_009": judgment(
        "UNCERTAIN", "PASS", "FAIL", "PASS", "PASS", "PASS",
        [
            "The capture identifies ChargeMe Ltd at chargebackme.com and markets recovery of funds lost to brokers or financial platforms.",
            "The frozen CySEC warning row records chargebackme.com under fraud and other misconduct, but the captured service is recovery assistance rather than an investment offer.",
        ],
        "The identity and official warning align, yet the reviewed artifact is a fund-recovery service adjacent to investment fraud rather than an investment solicitation itself. Because this corpus gate targets investment-related deceptive content, the relevance failure requires an UNCERTAIN recommendation.",
        ["Artifact is a recovery-service solicitation, not clearly an investment product or investment opportunity."],
    ),
    "TTCV1_CAND_LEGIT_EDGAR_001": judgment(
        "LEGITIMATE", "PASS", "PASS", "PASS", "PASS", "PASS",
        [
            "The capture names HealthEquity Advisors, LLC, calls it an SEC-registered investment adviser, and describes fiduciary fund-selection services.",
            "The frozen IAPD row lists HealthEquity Advisors LLC as APPROVED and records healthequityadvisors.com as its host.",
        ],
        "The captured entity, advisory activity, exact registered host, and active IAPD identity agree. The EDGAR relationship is treated only as supporting provenance, while the artifact-to-IAPD alignment independently supports a primary LEGITIMATE recommendation.",
    ),
    "TTCV1_CAND_LEGIT_EDGAR_002": judgment(
        "LEGITIMATE", "PASS", "PASS", "PASS", "PASS", "PASS",
        [
            "The capture names Provident Investment Management and describes personalized wealth management and investment advice.",
            "The frozen IAPD row lists Provident Investment Management Inc as APPROVED and records investprovident.com as its host.",
        ],
        "The EDGAR company name is not used as the deciding identity. The captured Provident adviser name and investment services align directly with the active IAPD record and exact host, with no captured contradiction, supporting a primary LEGITIMATE recommendation.",
    ),
    "TTCV1_CAND_LEGIT_EDGAR_003": judgment(
        "LEGITIMATE", "PASS", "PASS", "PASS", "PASS", "PASS",
        [
            "The capture identifies SEI and markets technology and investment solutions for asset managers, advisers, and institutional investors.",
            "The frozen IAPD row lists SEI Investments Management Corp as APPROVED and records seic.com as its host.",
        ],
        "The exact IAPD-recorded host, shared SEI investment identity, and captured investment-services content align without a conflicting operator or repurpose signal. This supports a primary LEGITIMATE recommendation independent of the EDGAR crosswalk.",
    ),
    "TTCV1_CAND_LEGIT_EDGAR_006": judgment(
        "LEGITIMATE", "PASS", "PASS", "PASS", "PASS", "PASS",
        [
            "The capture names Commonwealth Investment Management and describes SEC-registered equity and fixed-income investment management.",
            "The frozen IAPD row includes Commonwealth Investment Management as an entity-name key, is APPROVED, and records ciminvests.com.",
        ],
        "The captured name is explicitly present in the IAPD identity keys and the exact host and investment-management activity align. The unrelated-looking EDGAR parent name is not relied upon, leaving no unresolved contradiction for the primary LEGITIMATE recommendation.",
    ),
    "TTCV1_CAND_LEGIT_EDGAR_007": judgment(
        "UNCERTAIN", "UNCERTAIN", "FAIL", "PASS", "PASS", "UNCERTAIN",
        [
            "The capture presents Inter's banking super-app, credit card, digital account, shopping, and payment features.",
            "The frozen IAPD row lists Inter Advisors LLC at inter.co, but neither that adviser identity nor an investment-advisory service appears in the extracted artifact.",
        ],
        "The official host link alone is insufficient to transfer the registered-adviser identity to a captured retail-banking page. Because the artifact lacks explicit investment or advisory content and the affiliate relationship is unresolved in the text, the recommendation remains UNCERTAIN.",
        ["Captured artifact does not independently link Inter Advisors LLC or investment-advisory activity to the page."],
    ),
    "TTCV1_CAND_LEGIT_EDGAR_008": judgment(
        "LEGITIMATE", "PASS", "PASS", "PASS", "PASS", "PASS",
        [
            "The capture names A.G. Morgan Financial Advisors, LLC and describes a full-service wealth-planning firm.",
            "The frozen IAPD row lists A G Morgan Financial Advisors LLC as APPROVED and records agmorgan.net as its host.",
        ],
        "The exact adviser name, wealth-management activity, and IAPD-recorded host align without a competing operator or content contradiction. The EDGAR entity is not used to decide identity, so the artifact independently supports a primary LEGITIMATE recommendation.",
    ),
    "TTCV1_CAND_LEGIT_EDGAR_009": judgment(
        "LEGITIMATE", "PASS", "PASS", "PASS", "PASS", "PASS",
        [
            "The capture names SPARX Asset Management in Japanese and contains investment trusts, fund reports, and investment philosophy content.",
            "The frozen IAPD row lists SPARX Asset Management Co Ltd as APPROVED and records sparx.co.jp as its host.",
        ],
        "The captured asset-manager identity, investment content, and exact IAPD-recorded host agree, with no repurpose or competing operator signal. This independently supports a primary LEGITIMATE recommendation without depending on the EDGAR name match.",
    ),
    "TTCV1_CAND_LEGIT_EDGAR_010": judgment(
        "LEGITIMATE", "PASS", "PASS", "PASS", "PASS", "PASS",
        [
            "The capture names Alamo Advisors LP, identifies wealth management, and provides the alamoadvisors.com contact identity.",
            "The frozen IAPD row lists Alamo Advisors LP as APPROVED and records alamoadvisors.com as its host.",
        ],
        "The exact adviser name, wealth-management role, and IAPD-recorded host align without contradiction. The EDGAR Alamo Group name is not treated as decisive evidence, while the direct artifact-to-IAPD match supports a primary LEGITIMATE recommendation.",
    ),
    "TTCV1_CAND_LEGIT_IAPD_001": judgment(
        "LEGITIMATE", "PASS", "PASS", "PASS", "PASS", "PASS",
        [
            "The AmeriServ capture includes AmeriServ Wealth Advisors, managing investments, investment management, and wealth-management services.",
            "The frozen IAPD row lists AmeriServ Wealth Advisors Inc as APPROVED and records ameriserv.com as its host.",
        ],
        "Although the landing page also covers banking, it explicitly identifies AmeriServ Wealth Advisors and investment-management services. That captured identity aligns with the active IAPD record and exact host, supporting a primary LEGITIMATE recommendation.",
    ),
    "TTCV1_CAND_LEGIT_IAPD_004": judgment(
        "LEGITIMATE", "PASS", "PASS", "PASS", "PASS", "PASS",
        [
            "The capture repeatedly names Bridger Investment Partners LLC and describes residential-credit investment management.",
            "The frozen IAPD row lists Bridger Investment Partners LLC as APPROVED and records bridger-partners.com as its host.",
        ],
        "The exact legal name, investment-management activity, and IAPD-recorded host align without a conflicting identity, parking, or repurpose signal. This supports a primary LEGITIMATE recommendation while retaining the later review gates.",
    ),
    "TTCV1_CAND_LEGIT_IAPD_005": judgment(
        "LEGITIMATE", "PASS", "PASS", "PASS", "PASS", "PASS",
        [
            "The capture names Accumulus Capital Management, LLC and presents its investment approach and risk-return positioning.",
            "The frozen IAPD row lists Accumulus Capital Management LLC as APPROVED and records accumuluscapital.com as its host.",
        ],
        "The exact registered entity name, investment context, and official host align without a competing operator or repurpose indicator. This evidence supports a primary LEGITIMATE recommendation, not a final ground-truth label.",
    ),
    "TTCV1_CAND_LEGIT_IAPD_006": judgment(
        "LEGITIMATE", "PASS", "PASS", "PASS", "PASS", "PASS",
        [
            "The capture names Summit Financial Advisors, Inc. and describes investment, financial-planning, and portfolio services.",
            "The frozen IAPD row lists Summit Financial Advisors Inc as APPROVED and records sfadvisorsinc.com as its host.",
        ],
        "The exact adviser identity, investment-service content, and IAPD-recorded host agree, and no captured parking, repurpose, or identity contradiction is present. This supports a primary LEGITIMATE recommendation.",
    ),
    "TTCV1_CAND_LEGIT_IAPD_007": judgment(
        "UNCERTAIN", "FAIL", "UNCERTAIN", "PASS", "UNCERTAIN", "FAIL",
        [
            "The capture names Ironwood Funding, describes lending and finance, and uses an irfcapital.com contact address.",
            "The frozen IAPD row instead names Cumberland Hill Capital Management LLC while recording ironwoodfunding.com as its host.",
        ],
        "The official host is present, but the captured operator name and contact domain do not establish Cumberland Hill Capital Management or an investment-advisory artifact. The unresolved identity and content mismatch prevents a LEGITIMATE recommendation and requires UNCERTAIN.",
        ["Captured Ironwood Funding identity and irfcapital.com contact do not resolve to the IAPD entity."],
    ),
    "TTCV1_CAND_LEGIT_IAPD_008": judgment(
        "UNCERTAIN", "UNCERTAIN", "PASS", "PASS", "PASS", "UNCERTAIN",
        [
            "The capture names Astō Consumer Partners and describes investment opportunities and an investment philosophy associated with Clayton Christopher.",
            "The frozen IAPD row names Christopher & Co LLC and records astoconsumer.com, but that legal entity name is absent from the captured text.",
        ],
        "The artifact is clearly investment-related and shares a person-name cue with the registered entity, but the captured Astō identity is not explicitly connected to Christopher & Co LLC. Registration and host alone cannot resolve the DBA or affiliate relationship, so it remains UNCERTAIN.",
        ["The captured brand-to-registered-entity relationship is plausible but not explicitly established by the frozen artifact."],
    ),
}


def build_review(config_path: Path) -> dict[str, Any]:
    config = load(config_path)
    packet_path = Path(config["outputs"]["review_packet"])
    packet = load(packet_path)
    packet_ids = {row["candidate_id"] for row in packet["records"]}
    if packet.get("status") != "FROZEN_UNREVIEWED_PACKET":
        raise ValueError("Unexpected packet status")
    if packet_ids != set(JUDGMENTS) or len(packet_ids) != config["expected_review_population"]:
        raise ValueError("Judgment population does not exactly match frozen packet")
    rows = [{"candidate_id": candidate_id, **JUDGMENTS[candidate_id]} for candidate_id in sorted(packet_ids)]
    counts = Counter(row["primary_recommendation"] for row in rows)
    return {
        "review_id": "ISI_TARGET_TEXT_CORPUS_V1_PRIMARY_CASE_ARTIFACT_REVIEW_V1",
        "status": "PRIMARY_REVIEW_COMPLETE_SECOND_REVIEW_REQUIRED",
        "input_packet": {"path": str(packet_path), "sha256": sha(packet_path)},
        "reviewer": {
            "mode": "AI_ASSISTED_PRIMARY_MANUAL_REVIEW_AUTHORIZED_BY_OWNER",
            "reviewed_at": "2026-10-09",
            "network_access_used": False,
            "model_predictions_visible": False,
            "source_stratum_treated_as_ground_truth": False,
        },
        "records": rows,
        "summary": {
            "reviewed_records": len(rows),
            "primary_recommendation_counts": dict(sorted(counts.items())),
            "labels_created": 0,
            "training_eligible_records": 0,
        },
        "decision": {
            "primary_case_and_artifact_review_completed": True,
            "blind_independent_second_review_required": True,
            "reconciliation_required": True,
            "owner_acceptance_required": True,
            "ground_truth_labeling_completed": False,
            "training_allowed": False,
        },
        "safety_contract": config["safety_contract"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    args = parser.parse_args()
    config = load(args.config)
    output = Path(config["outputs"]["primary_review"])
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite frozen output: {output}")
    review = build_review(args.config)
    with output.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(review, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    print(json.dumps({"review_id": review["review_id"], "summary": review["summary"], "output": str(output), "sha256": sha(output)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
