# Crimson Primary Evidence Assessment Draft V1

Date: 2026-11-02
Status: AI-assisted recommendations only; all human primary tasks remain pending

## Purpose and boundary

This memo organizes the 15 official-reference follow-up tasks in current review
order using only the pinned source facts and access-status records in V1/V2/V3.
It is preparation for a primary reviewer, not a human decision log. It does not
create `SCAM` or `LEGITIMATE` labels, admit data, or change any source status.
Do not show this AI draft to blind second reviewers.

`SAME_ENTITY` below means only that a directly read official artifact names the
exact candidate host alongside the warned entity. It does not prove who sent a
particular message, establish current control of the host, or imply a scam
label. `WARNING_RELEVANT` and `REGISTRATION_RELEVANT` describe the kind of
official fact, not ground truth for a message.

## Draft recommendations in review order

| Order | Pilot / candidate host | Pinned evidence and boundary | AI suggestion for primary reviewer | Second review after primary |
|---:|---|---|---|:---:|
| 1 | REF_039 — `benefittrade.org` | FMA list search-index lead only; the official endpoint previously returned HTTP 429. No directly reviewed page or retained official artifact. | `UNCLEAR` + `INSUFFICIENT_EVIDENCE`; keep `UNCERTAIN`. | Yes |
| 2 | REF_009 — `bitforex.com` | Direct SFC record names BitForex and the exact host, and reports suspected fraud/user access and withdrawal problems; this is an official alert, not a court finding. | `SAME_ENTITY` + `WARNING_RELEVANT`; note the regulator's wording and date. | Yes |
| 3 | REF_010 — `aiminingex.com` | Direct FCA warning names Ai-MiningEx and the exact host and states it is not FCA-authorised. | `SAME_ENTITY` + `WARNING_RELEVANT`; UK authorization scope only. | Yes |
| 4 | REF_011 — `chainstackinvest.com` | Direct FCA and CNMV records name the exact host and describe lack of authorization for specified services. | `SAME_ENTITY` + `WARNING_RELEVANT`; keep jurisdictional scope. | Yes |
| 5 | REF_012 — `cryptobanxatrade.com` | Direct CFTC RED List release includes CryptoBanxaTrade with the exact domain. RED List inclusion concerns registration; it is not an adjudication of fraud. | `SAME_ENTITY` + `REGISTRATION_RELEVANT`. | Yes |
| 6 | REF_013 — `forexcapitalgain.com` | Direct CFTC page names Forex Capital Gain and exact domain; it says the firm appears to require registration but is not registered and expressly limits the legal implication. | `SAME_ENTITY` + `REGISTRATION_RELEVANT`. | Yes |
| 7 | REF_016 — `magnomicyieldltd.com` | Direct English CONSOB release names Magnomic Yield Ltd and the exact website among seven sites ordered blocked for abusive financial services/products. [Review brief](../reports/crimson_external_reference_review_pilot_v1/PILOT_CRIMSON_REF_016_review_brief_v1.md). | `SAME_ENTITY` + `WARNING_RELEVANT`; the exact source limits are in the brief. | Yes |
| 8 | REF_017 — `opentrading-platform.com` | Direct FCA and CNMV records name the exact host and state it is not authorized/registered for specified services. | `SAME_ENTITY` + `WARNING_RELEVANT`; authorization warning, not conviction. | Yes |
| 9 | REF_020 — `primewealthltd.com` | Direct AMF Québec page names the exact host and says PrimeWealth is not registered or authorized to solicit in Québec. | `SAME_ENTITY` + `REGISTRATION_RELEVANT`; jurisdiction-specific. | Yes |
| 10 | REF_021 — `affiliate.primexbt.com` | AMF source names root `www.primexbt.com`; SC Malaysia source names PrimeXBT but supplies no candidate domain. Neither establishes the affiliate subdomain's operator. | `UNCLEAR` + `INSUFFICIENT_EVIDENCE`; preserve the identity gap. | Yes |
| 11 | REF_026 — `me.tradextixcoins.com` | SEC/CFTC sources name root `tradextixcoins.com`; neither reviewed fact ties the `me.` subdomain to that entity/operator. | `UNCLEAR` + `INSUFFICIENT_EVIDENCE`; root match cannot be extended to the subdomain. | Yes |
| 12 | REF_028 — `www-stage.cedarfx.com` | CFTC release names CedarFX/Cedar LLC and root `cedarfx.com`; the stage subdomain is not linked to them in the source. | `UNCLEAR` + `INSUFFICIENT_EVIDENCE`; do not infer the stage-host relationship. | Yes |
| 13 | REF_033 — `virtualcapitaltraders.com` | Direct AMF document names the exact host, categorizes it under crypto-currencies, and says the offer is unauthorized in France. | `SAME_ENTITY` + `WARNING_RELEVANT`; blacklist entry, not conviction. | No, per frozen plan |
| 14 | REF_034 — `hotfxcrypto.net` | Direct CNMV warning names the exact host and states the specified services are unauthorized in Spain. | `SAME_ENTITY` + `WARNING_RELEVANT`; jurisdiction-specific warning. | No, per frozen plan |
| 15 | REF_037 — `banktrustcoin.com` | FMA list search-index lead only; the official endpoint previously returned HTTP 429. No directly reviewed page or retained official artifact. | `UNCLEAR` + `INSUFFICIENT_EVIDENCE`; keep `UNCERTAIN`. | No, per frozen plan |

## Summary of the draft

- 10 exact-host official facts support an AI suggestion of `SAME_ENTITY` with a
  warning- or registration-relevant evidence assessment.
- 3 root-only/name-only records and 2 FMA access blockers remain
  `UNCLEAR`/`INSUFFICIENT_EVIDENCE` in this draft.
- All 15 human primary tasks remain `PENDING`; this memo has no reviewer identity
  or review date because no human decision was entered.
- All model dispositions remain `UNCERTAIN`; no row is admitted or
  training-eligible.
- The frozen review plan requires a second human review after primary review
  for 12 tasks. Three tasks are single-review under that plan.

## Next action

A truthful primary reviewer should accept, revise, or reject each suggestion
through the existing human-review workflow. The Magnomic brief is available
for review, but this memo alone does not confirm the user's decision. The blind
reviewer must be a different person and must not see this AI draft or the
primary decisions. Reconcile only after required reviews; disagreements and
insufficient evidence stay `UNCERTAIN`.
