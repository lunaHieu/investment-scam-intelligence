# Crimson official-source follow-up V2

Date: 2026-11-01

## Purpose and scope

This supplement records additional facts transcribed from 11 directly read
official regulator pages for 11 Crimson pilot IDs. The frozen evidence output
contains 12 records because PILOT_CRIMSON_REF_021 has both an AMF root-domain
record and a separate Securities Commission Malaysia name-only record. A
separate status output preserves all 15 official-reference follow-up tasks.
The work did not open a candidate host, retry a previously blocked URL, retain
raw official page files, create a human primary decision, or admit data.

The result is evidence for the next primary-review step. It is not itself a
review decision. All affected tasks remain `PENDING`, with model disposition
`UNCERTAIN`, `label_created=false`, `data_admission_allowed=false`, and
`training_eligible=NO`.

## New official facts

| Pilot | Official page | Recorded fact | Match boundary |
|---|---|---|---|
| REF_012 | [CFTC RED List additions, June 2023](https://www.cftc.gov/PressRoom/PressReleases/8716-23) | Lists CryptoBanxaTrade and cryptobanxatrade.com among RED List additions. | Exact domain; registration concern, not an adjudicated fraud finding. |
| REF_013 | [CFTC RED List: Forex Capital Gain](https://www.cftc.gov/REDlist/node/245766) | Names Forex Capital Gain and forexcapitalgain.com; states it appears to require registration but is not registered. | Exact domain; page explicitly says RED List inclusion is not a CFTC or court conclusion that a violation occurred. |
| REF_026 | [CFTC RED List: Trade Xtix Coins Ltd.](https://www.cftc.gov/REDlist/node/255441) | Lists tradextixcoins.com and Trade Xtix Coins Ltd. | Root domain only for `me.tradextixcoins.com`; subdomain operator remains unclear. |
| REF_028 | [CFTC RED List additions, June 2023](https://www.cftc.gov/PressRoom/PressReleases/8716-23) | Lists CedarFX and Cedar LLC with cedarfx.com. | Root domain only for `www-stage.cedarfx.com`; stage host/operator link is unverified. |
| REF_011 | [CNMV Chainstackinvest warning, 9 March 2026](https://www.cnmv.es/webservices/verdocumento/ver?e=ueCcI0UTnvI7Q%2B3IGcJs%2FJqsmhmHlGKVzGKYDPXP7jQPj57IXgF7VdIcuAns0KKL) | Names chainstackinvest.com / CHAINSTACKINVEST and says specified investment and crypto-asset services are unauthorized in Spain. | Exact domain; jurisdiction-specific authorization status, not a conviction. |
| REF_017 | [CNMV warning list, 23 February 2026](https://www.cnmv.es/webservices/verdocumento/ver?t=%7B0054cb9e-2cbd-4c5b-b5bb-94c9460f6922%7D) | Includes opentrading-platform.com / OPENTRADING PLATFORM; CNMV says listed entities are not registered or authorized for supervised services. | Exact domain; not a judgment or an automatic message label. |
| REF_019 | [CNMV warning list, 28 April 2025](https://www.cnmv.es/webservices/verdocumento/ver?t=%7B57327cbb-7205-4fe9-ba84-6b2d3028eaf0%7D) | Includes prime-xchange.org / PRIME XCHANGE; says listed entities are not registered or authorized in Spain. | Exact domain; the task remains for blind second review. |
| REF_034 | [CNMV HOTFXCRYPTO warning, 24 March 2025](https://www.cnmv.es/webservices/verdocumento/ver?e=%2FkI2f%2BwC%2BjzuxIXvuBTpt4bgIfO3RtNU2TGg1f2UJVUILCnUAEn6Pt63MwWh%2BqV8) | Names hotfxcrypto.net / HOTFXCRYPTO and states specified services are unauthorized in Spain. | Exact domain; not a conviction. |
| REF_014 | [CMF Chile warning, 22 April 2024](https://www.cmfchile.cl/portal/principal/623/w4-article-80858.html) | Says IFEXCAPITAL, operating via ifexcapital.com/es, is neither enrolled with nor supervised by the Chilean CMF. | Exact root host; still requires independent review. |
| REF_033 | [AMF record for virtualcapitaltraders.com](https://www.amf-france.org/sites/institutionnel/files/pdf/72471/en/virtualcapitaltraders_com.pdf?1755672340=) | Names the exact host, category crypto-currencies, and says the offer is unauthorized in France; page date 3 April 2024. | Exact domain; blacklist entry, not a court finding. |
| REF_021 | [AMF record for www.primexbt.com](https://protectepargne.amf-france.org/acteurs-listes-noires/forex/wwwprimexbtcom) | Names the root www.primexbt.com, Forex category, publication date 7 June 2021, and states certain services/products are unauthorized in France. | Root only; does not identify the operator of `affiliate.primexbt.com`. |
| REF_021 | [SC Malaysia investor-alert update, 19 August 2025](https://www.sc.com.my/bm/sumber/siaran-akhbar-dan-pengumuman/pengumuman-amaran-pelabur/senarai-peringatan-pelabur-setakat-19082025) | Names PrimeXBT as an addition to the Investor Alert List but gives no candidate domain on this announcement page. | Name-only; no link to the candidate affiliate subdomain is established. |

## Access still unresolved

- Benefittrade and Banktrustcoin appear in indexed snippets for the FMA's
  official list, but the prior direct FMA request returned HTTP 429. The same
  page was not retried; the index snippet is not counted as a directly reviewed
  source page.
- Magnomic Yield Ltd appears in an official CONSOB press-release search result.
  Direct page access returned a Radware challenge. No challenge was bypassed,
  and the source is not counted as directly reviewed.
- The alternate CNMV search result for Ai-MiningEx could not be opened from the
  search index in this update. The existing FCA evidence remains recorded.
- Prior blocked OSC, AMF France, CNMV, CFTC, and FMA URLs were not repeated.
  Alternate direct pages are recorded only where the official page or document
  was successfully read.

## Review sequence and gates

1. **Primary evidence review** — a human reviewer must assess the evidence,
   record identity relation and warning relevance, and explain limitations.
   All 15 follow-up primary decisions remain pending. Root-only and name-only
   entries cannot establish an entity relationship by themselves.
2. **Blind second review** — the independent reviewer must receive a packet
   without owner/primary decisions or AI suggestions. The nine existing ready
   packets remain unstarted; this supplement does not complete any of them.
3. **Reconciliation** — occurs only after both required reviews exist. Missing
   evidence, unresolved identity, or disagreement stays `UNCERTAIN`.
4. **Admission** — no row enters a usable dataset until source identity,
   evidence, required reviews, reconciliation, and owner acceptance are all
   recorded. No labels or training eligibility were created here.

## Reproducibility and safety

The frozen config is `configs/crimson_official_source_followup_v2.json`. The
materializer writes new, exclusive JSONL outputs; it does not modify earlier
review snapshots. The independent verifier compares both outputs with the
frozen config and pins their hashes in
`registry/analyses/crimson_official_source_followup_v2.json` and
`registry/analyses/crimson_official_source_followup_v2_qa.json`.

- Fact rows: 12 across 11 pilot IDs.
- Distinct direct official pages read: 11.
- Follow-up statuses: 15.
- Root-domain-only or name-only relations kept unresolved: 3 root-only pilot
  relations plus the name-only SC record.
- Primary reviews completed in this update: 0.
- Independent second reviews completed in this update: 0.
- Candidate hosts accessed: 0.
- Raw official pages retained: 0.
- Dataset rows admitted, labels created, or records training-eligible: 0.
