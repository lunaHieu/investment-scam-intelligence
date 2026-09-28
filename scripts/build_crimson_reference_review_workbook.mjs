import fs from "node:fs/promises";
import path from "node:path";
import { FileBlob, SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const pilotPath = process.argv[2];
const evidencePath = process.argv[3];
const outputDir = process.argv[4];
const secFirstPassPath = process.argv[5];
const ioscoFirstPassPath = process.argv[6];
const humanReviewPlanPath = process.argv[7];
const humanDecisionPath = process.argv[8];
if (!pilotPath || !evidencePath || !outputDir) {
  throw new Error("Usage: node build_crimson_reference_review_workbook.mjs <pilot.jsonl> <evidence.jsonl> <output-dir> [sec-first-pass.jsonl] [iosco-first-pass.jsonl] [human-review-plan.jsonl] [human-decisions.jsonl]");
}

const parseJsonl = async (filePath) => (await fs.readFile(filePath, "utf8"))
  .split(/\r?\n/)
  .filter((line) => line.trim())
  .map((line) => JSON.parse(line));

const pilot = await parseJsonl(pilotPath);
const evidence = await parseJsonl(evidencePath);
const secFirstPass = secFirstPassPath ? await parseJsonl(secFirstPassPath) : [];
const ioscoFirstPass = ioscoFirstPassPath ? await parseJsonl(ioscoFirstPassPath) : [];
const humanReviewPlan = humanReviewPlanPath ? await parseJsonl(humanReviewPlanPath) : [];
const humanDecisions = humanDecisionPath ? await parseJsonl(humanDecisionPath) : [];
const firstPass = [...secFirstPass, ...ioscoFirstPass];
if (pilot.length !== 40) throw new Error(`Expected 40 pilot records, received ${pilot.length}`);
if (secFirstPass.length && secFirstPass.length !== 8) throw new Error(`Expected 8 SEC first-pass records, received ${secFirstPass.length}`);
if (ioscoFirstPass.length && ioscoFirstPass.length !== 32) throw new Error(`Expected 32 IOSCO first-pass records, received ${ioscoFirstPass.length}`);
if (firstPass.some((row) => row.review_status !== "IN_PROGRESS" || row.training_eligible !== "NO" || row.label_created !== false)) {
  throw new Error("First-pass records must remain in progress, non-label and not eligible for training");
}
if (humanReviewPlan.length && humanReviewPlan.length !== 40) throw new Error(`Expected 40 human-review plan records, received ${humanReviewPlan.length}`);
if (humanReviewPlan.some((row) => row.review_status !== "IN_PROGRESS" || row.adjudication_status !== "NOT_READY" || row.training_eligible !== "NO" || row.label_created !== false)) {
  throw new Error("Human-review plan records must remain in progress, not ready, non-label and not eligible for training");
}
if (humanDecisions.some((row) => row.decision_stage !== "HUMAN_FIRST_REVIEW" || row.review_status !== "COMPLETED" || row.training_eligible !== "NO" || row.label_created !== false)) {
  throw new Error("Human decisions must be confirmed first reviews that remain non-label and not eligible for training");
}
const firstPassByPilot = new Map(firstPass.map((row) => [row.pilot_id, row]));
if (firstPassByPilot.size !== firstPass.length) throw new Error("First-pass pilot IDs must be unique");
const humanDecisionByPilot = new Map(humanDecisions.map((row) => [row.pilot_id, row]));
if (humanDecisionByPilot.size !== humanDecisions.length) throw new Error("Human decision pilot IDs must be unique");
if ([...humanDecisionByPilot.keys()].some((pilotId) => !firstPassByPilot.has(pilotId))) throw new Error("Human decision references a pilot outside the first-pass scope");
const ioscoDetailByEvidence = new Map();
for (const record of ioscoFirstPass) {
  for (const detail of record.reference_details || []) {
    ioscoDetailByEvidence.set(`${record.pilot_id}:${detail.reference_record_id}`, detail);
  }
}

const workbook = Workbook.create();
const review = workbook.worksheets.add("Review");
const reviewPlan = workbook.worksheets.add("Review plan");
const evidenceSheet = workbook.worksheets.add("Evidence");
const guide = workbook.worksheets.add("Guide");
const font = "Arial";
const navy = "#16324F";
const blue = "#2F6690";
const lightBlue = "#D9EAF7";
const lightGray = "#F2F4F7";
const amber = "#FFF2CC";
const red = "#FDE9D9";
const green = "#E2F0D9";
const border = "#C9D2DC";

for (const sheet of [review, reviewPlan, evidenceSheet, guide]) {
  sheet.showGridLines = false;
  sheet.getRange("A1:AA100").format.font = { name: font, size: 10, color: "#1F2937" };
  sheet.getRange("A1:AA100").format.verticalAlignment = "center";
}

// Review sheet: summary above one editable table.
review.tabColor = navy;
review.getRange("A2").values = [["Crimson external-reference review pilot"]];
review.getRange("A2").format.font = { name: font, size: 15, bold: true, color: navy };
review.getRange("A3").values = [[firstPass.length
  ? `${firstPass.length} rows contain an AI-assisted first pass. ${humanDecisions.length} first human review(s) are confirmed; all others remain IN_PROGRESS. Do not open Crimson hosts directly.`
  : "40 canonical hosts selected by a frozen protocol. Check official references only; do not open Crimson hosts directly."
]];
review.getRange("A3").format.font = { name: font, size: 10, italic: true, color: "#4B5563" };
review.getRange("A4:AA4").format.borders = { bottom: { style: "thin", color: blue } };

review.getRange("A5:L5").values = [[
  "Pilot hosts", null, "SEC references", null, "IOSCO references", null,
  "Reviews completed", null, "Ready for adjudication", null, "AI first pass", null,
]];
review.getRange("B5").formulas = [["=COUNTA(A10:A49)"]];
review.getRange("D5").formulas = [["=COUNTIFS(E10:E49,\"sec_iapd\")"]];
review.getRange("F5").formulas = [["=COUNTIFS(E10:E49,\"iosco_i_scan\")"]];
review.getRange("H5").formulas = [["=COUNTIFS(I10:I49,\"COMPLETED\")"]];
review.getRange("J5").formulas = [["=COUNTIFS(S10:S49,\"READY_FOR_ADJUDICATION\")"]];
review.getRange("L5").formulas = [["=COUNTA(A10:A49)"]];
for (const labelCell of ["A5", "C5", "E5", "G5", "I5", "K5"]) {
  review.getRange(labelCell).format = { fill: lightBlue, font: { name: font, bold: true, color: navy } };
}
for (const valueCell of ["B5", "D5", "F5", "H5", "J5", "L5"]) {
  review.getRange(valueCell).format = {
    fill: "#FFFFFF", font: { name: font, size: 12, bold: true, color: navy },
    horizontalAlignment: "center", numberFormat: "#,##0",
  };
}
review.getRange("A7").values = [["Editable fields are shaded amber. READY requires a completed review, official-reference check, identity assessment, evidence assessment, reviewer, date and notes. Some cases also require second review."]];
review.getRange("A7").format.font = { name: font, size: 10, italic: true, color: "#4B5563" };

const reviewHeaders = [
  "Pilot ID", "Rank", "Selection bucket", "Crimson host", "Reference source",
  "Host relation", "Reference matches", "Shared reference host", "Review status",
  "Official reference checked", "Identity relationship", "Evidence assessment",
  "Reviewer", "Reviewed date", "Review notes", "Second review status",
  "Second reviewer", "Second review required", "Adjudication status", "Training eligible",
];
review.getRange("A9:T9").values = [reviewHeaders];
const reviewRows = pilot.map((record) => {
  const prepared = firstPassByPilot.get(record.pilot_id);
  const decision = humanDecisionByPilot.get(record.pilot_id);
  let conciseNote = record.review_notes;
  if (prepared?.reference_source === "sec_iapd") {
    conciseNote = `SEC/IAPD CRD ${prepared.reference_record_id} lists ${prepared.entity_names.join(", ")} and ${prepared.matched_reference_host}; ${prepared.registration_type} / ${prepared.registration_status}. AI first pass supports SAME_ENTITY + REGISTRATION_RELEVANT only; human confirmation required.`;
  } else if (prepared?.reference_source === "iosco_i_scan") {
    conciseNote = `${prepared.reference_match_count} IOSCO warning record(s) from ${prepared.regulators.join(", ")} reference ${prepared.crimson_host}; ${prepared.live_reference_status}. AI first pass supports ${prepared.identity_relationship} + WARNING_RELEVANT only; human confirmation required.`;
  }
  return [
    record.pilot_id,
    record.pilot_rank,
    record.selection_bucket,
    record.crimson_match_host,
    (record.reference_sources || []).join("; "),
    (record.host_relations || []).join("; "),
    record.reference_match_count,
    record.shared_reference_host_present ? "YES" : "NO",
    decision?.review_status ?? prepared?.review_status ?? record.review_status,
    decision?.official_reference_checked ?? prepared?.official_reference_checked ?? record.official_reference_checked,
    decision?.identity_relationship ?? prepared?.identity_relationship ?? record.identity_relationship,
    decision?.evidence_assessment ?? prepared?.evidence_assessment ?? record.evidence_assessment,
    decision?.reviewer ?? prepared?.reviewer ?? record.reviewer,
    (decision?.reviewed_date || prepared?.reviewed_date)
      ? new Date(`${decision?.reviewed_date || prepared?.reviewed_date}T00:00:00Z`)
      : record.reviewed_date,
    decision?.review_notes ?? conciseNote,
    decision?.second_review_status ?? prepared?.second_review_status ?? record.second_review_status,
    decision?.second_reviewer ?? prepared?.second_reviewer ?? record.second_reviewer,
    null,
    null,
    "NO",
  ];
});
review.getRange("A10:T49").values = reviewRows;
for (let row = 10; row <= 49; row += 1) {
  review.getRange(`R${row}`).formulas = [[
    `=IF(OR(K${row}="IMPERSONATION_SUSPECTED",K${row}="UNCLEAR",H${row}="YES"),"YES","NO")`,
  ]];
  review.getRange(`S${row}`).formulas = [[
    `=IF(I${row}<>"COMPLETED","NOT_READY",IF(OR(J${row}<>"YES",K${row}="",L${row}="",M${row}="",N${row}="",O${row}=""),"MISSING_INPUT",IF(AND(R${row}="YES",P${row}<>"COMPLETED"),"SECOND_REVIEW_REQUIRED","READY_FOR_ADJUDICATION")))`,
  ]];
}

review.getRange("A9:T9").format = {
  fill: navy,
  font: { name: font, size: 10, bold: true, color: "#FFFFFF" },
  horizontalAlignment: "center",
  verticalAlignment: "center",
  wrapText: true,
  borders: { preset: "inside", style: "thin", color: "#FFFFFF" },
};
review.getRange("A10:T49").format.borders = {
  insideHorizontal: { style: "thin", color: border },
  bottom: { style: "thin", color: border },
};
review.getRange("I10:Q49").format.fill = amber;
review.getRange("R10:T49").format.fill = lightGray;
review.getRange("O10:O49").format.wrapText = true;
review.getRange("N10:N49").setNumberFormat("yyyy-mm-dd");
review.getRange("B10:B49").setNumberFormat("0");
review.getRange("G10:G49").setNumberFormat("0");
review.getRange("I10:I49").dataValidation = { rule: { type: "list", values: ["NOT_STARTED", "IN_PROGRESS", "COMPLETED", "NEEDS_SECOND_REVIEW"] } };
review.getRange("J10:J49").dataValidation = { rule: { type: "list", values: ["NO", "YES"] } };
review.getRange("K10:K49").dataValidation = { rule: { type: "list", values: ["SAME_ENTITY", "IMPERSONATION_SUSPECTED", "UNRELATED", "UNCLEAR"] } };
review.getRange("L10:L49").dataValidation = { rule: { type: "list", values: ["WARNING_RELEVANT", "REGISTRATION_RELEVANT", "REFERENCE_NOT_APPLICABLE", "INSUFFICIENT_EVIDENCE"] } };
review.getRange("P10:P49").dataValidation = { rule: { type: "list", values: ["NOT_REQUESTED", "REQUESTED", "COMPLETED"] } };
review.getRange("I10:I49").conditionalFormats.add("containsText", { text: "COMPLETED", format: { fill: green, font: { color: "#375623", bold: true } } });
review.getRange("S10:S49").conditionalFormats.add("containsText", { text: "READY_FOR_ADJUDICATION", format: { fill: green, font: { color: "#375623", bold: true } } });
review.getRange("S10:S49").conditionalFormats.add("containsText", { text: "MISSING_INPUT", format: { fill: red, font: { color: "#9C0006", bold: true } } });
review.getRange("S10:S49").conditionalFormats.add("containsText", { text: "SECOND_REVIEW_REQUIRED", format: { fill: amber, font: { color: "#9C6500", bold: true } } });
const reviewTable = review.tables.add("A9:T49", true, "CrimsonReviewPilotTable");
reviewTable.style = "TableStyleMedium2";
reviewTable.showFilterButton = true;
review.freezePanes.freezeRows(9);
review.freezePanes.freezeColumns(4);

const reviewWidths = {
  "A:A": 24, "B:B": 7, "C:C": 25, "D:D": 28, "E:F": 24,
  "G:H": 14, "I:L": 24, "M:M": 28, "N:N": 14, "O:O": 62,
  "P:Q": 22, "R:R": 24, "S:S": 32, "T:T": 20,
};
for (const [range, width] of Object.entries(reviewWidths)) review.getRange(range).format.columnWidth = width;
review.getRange("9:9").format.rowHeight = 42;
review.getRange("10:49").format.rowHeight = 34;
if (firstPass.length) review.getRange(`10:${9 + firstPass.length}`).format.rowHeight = 58;

// Review plan sheet: prioritized human work queue linked to the editable Review sheet.
reviewPlan.tabColor = "#5B8C85";
reviewPlan.getRange("A2").values = [["Human review plan"]];
reviewPlan.getRange("A2").format.font = { name: font, size: 15, bold: true, color: navy };
reviewPlan.getRange("A3").values = [["Work from top to bottom. Open only official regulator references from the Evidence sheet; never open a Crimson host on the main machine."]];
reviewPlan.getRange("A3").format.font = { name: font, size: 10, italic: true, color: "#4B5563" };
reviewPlan.getRange("A4:O4").format.borders = { bottom: { style: "thin", color: blue } };
reviewPlan.getRange("A5:J5").values = [[
  "Planned hosts", null, "Identity exceptions", null, "Live URL follow-up", null,
  "Second review required", null, "Ready for adjudication", null,
]];
reviewPlan.getRange("B5").formulas = [["=COUNTA(A10:A49)"]];
reviewPlan.getRange("D5").formulas = [["=COUNTIF(F10:F49,\"IMPERSONATION_SUSPECTED\")"]];
reviewPlan.getRange("F5").formulas = [["=COUNTIFS(G10:G49,\"<>ALL_URLS_LIVE_CONFIRMED\",G10:G49,\"<>OFFICIAL_PROFILE_SNAPSHOT\")"]];
reviewPlan.getRange("H5").formulas = [["=COUNTIF(I10:I49,\"YES\")"]];
reviewPlan.getRange("J5").formulas = [["=COUNTIF(M10:M49,\"READY_FOR_ADJUDICATION\")"]];
for (const labelCell of ["A5", "C5", "E5", "G5", "I5"]) {
  reviewPlan.getRange(labelCell).format = { fill: lightBlue, font: { name: font, bold: true, color: navy } };
}
for (const valueCell of ["B5", "D5", "F5", "H5", "J5"]) {
  reviewPlan.getRange(valueCell).format = {
    fill: "#FFFFFF", font: { name: font, size: 12, bold: true, color: navy },
    horizontalAlignment: "center", numberFormat: "#,##0",
  };
}
reviewPlan.getRange("A7").values = [["Priority P0 covers suspected impersonation. P1 and P2 require two human reviews. P3 requires manual recovery of an official URL. P4 is the remaining single-review queue."]];
reviewPlan.getRange("A7").format.font = { name: font, size: 10, italic: true, color: "#4B5563" };

const reviewPlanHeaders = [
  "Review order", "Priority", "Pilot ID", "Crimson host", "Reference source",
  "Identity suggestion", "Live evidence", "Reference record IDs", "Second review required",
  "Required human action", "Review status", "Second review status", "Adjudication status",
  "Training eligible", "Safety",
];
reviewPlan.getRange("A9:O9").values = [reviewPlanHeaders];
const reviewPlanRows = humanReviewPlan.map((record) => [
  record.review_order,
  record.priority_band,
  record.pilot_id,
  record.crimson_host,
  record.reference_source,
  record.identity_suggestion,
  humanDecisionByPilot.get(record.pilot_id)?.live_reference_status ?? record.live_reference_status,
  (record.reference_record_ids || []).join("; "),
  record.second_review_required ? "YES" : "NO",
  record.required_action,
  null,
  null,
  null,
  null,
  "Use official regulator references only; do not open the Crimson host.",
]);
if (reviewPlanRows.length) reviewPlan.getRange(`A10:O${9 + reviewPlanRows.length}`).values = reviewPlanRows;
for (let index = 0; index < humanReviewPlan.length; index += 1) {
  const planRow = 10 + index;
  const sourceRow = Number(humanReviewPlan[index].review_sheet_row);
  reviewPlan.getRange(`K${planRow}:N${planRow}`).formulas = [[
    `=Review!I${sourceRow}`,
    `=Review!P${sourceRow}`,
    `=Review!S${sourceRow}`,
    `=Review!T${sourceRow}`,
  ]];
}
reviewPlan.getRange("A9:O9").format = {
  fill: navy,
  font: { name: font, size: 10, bold: true, color: "#FFFFFF" },
  horizontalAlignment: "center",
  verticalAlignment: "center",
  wrapText: true,
  borders: { preset: "inside", style: "thin", color: "#FFFFFF" },
};
if (reviewPlanRows.length) {
  const planEndRow = 9 + reviewPlanRows.length;
  reviewPlan.getRange(`A10:O${planEndRow}`).format.borders = {
    insideHorizontal: { style: "thin", color: border }, bottom: { style: "thin", color: border },
  };
  reviewPlan.getRange(`J10:J${planEndRow}`).format.wrapText = true;
  reviewPlan.getRange(`O10:O${planEndRow}`).format.wrapText = true;
  reviewPlan.getRange(`K10:N${planEndRow}`).format.fill = lightGray;
  reviewPlan.getRange(`B10:B${planEndRow}`).conditionalFormats.add("containsText", { text: "P0_", format: { fill: red, font: { color: "#9C0006", bold: true } } });
  reviewPlan.getRange(`B10:B${planEndRow}`).conditionalFormats.add("containsText", { text: "P1_", format: { fill: amber, font: { color: "#9C6500", bold: true } } });
  reviewPlan.getRange(`B10:B${planEndRow}`).conditionalFormats.add("containsText", { text: "P2_", format: { fill: lightBlue, font: { color: navy, bold: true } } });
  reviewPlan.getRange(`M10:M${planEndRow}`).conditionalFormats.add("containsText", { text: "READY_FOR_ADJUDICATION", format: { fill: green, font: { color: "#375623", bold: true } } });
  const planTable = reviewPlan.tables.add(`A9:O${planEndRow}`, true, "CrimsonHumanReviewPlanTable");
  planTable.style = "TableStyleMedium2";
  planTable.showFilterButton = true;
}
reviewPlan.freezePanes.freezeRows(9);
reviewPlan.freezePanes.freezeColumns(4);
const reviewPlanWidths = {
  "A:A": 12, "B:B": 34, "C:C": 24, "D:D": 28, "E:E": 18,
  "F:G": 28, "H:H": 26, "I:I": 18, "J:J": 72, "K:L": 24, "M:M": 32, "N:N": 18, "O:O": 48,
};
for (const [range, width] of Object.entries(reviewPlanWidths)) reviewPlan.getRange(range).format.columnWidth = width;
reviewPlan.getRange("9:9").format.rowHeight = 42;
if (reviewPlanRows.length) reviewPlan.getRange(`10:${9 + reviewPlanRows.length}`).format.rowHeight = 52;

// Evidence sheet: immutable source rows supporting the selected pilot.
evidenceSheet.tabColor = blue;
evidenceSheet.getRange("A2").values = [["Reference evidence for selected hosts"]];
evidenceSheet.getRange("A2").format.font = { name: font, size: 15, bold: true, color: navy };
evidenceSheet.getRange("A3").values = [["Sources: IOSCO I-SCAN (https://www.iosco.org/i-scan/) and SEC/IAPD (https://adviserinfo.sec.gov/compilation). Snapshot hashes are frozen in the project registry."]];
evidenceSheet.getRange("A3").format.font = { name: font, size: 10, italic: true, color: "#4B5563" };
const evidenceHeaders = [
  "Pilot ID", "Rank", "Crimson host", "Reference source", "Reference record ID",
  "Reference role", "Host relation", "Matched reference host", "Records sharing host",
  "IOSCO notice URL", "SEC number", "Official entity names", "Regulator / filing type",
  "Jurisdiction / filing status", "Reference date", "Official reference URL", "Live URL check",
  "AI first-pass rationale", "Crimson artifact IDs", "Observed Crimson domains", "Source status",
];
evidenceSheet.getRange("A5:U5").values = [evidenceHeaders];
const evidenceRows = evidence.map((record) => {
  const prepared = firstPassByPilot.get(record.pilot_id);
  const ioscoDetail = ioscoDetailByEvidence.get(`${record.pilot_id}:${record.reference_record_id}`);
  const entityNames = ioscoDetail?.entity_names || prepared?.entity_names || [];
  const sourceType = ioscoDetail?.regulator_name || prepared?.registration_type || "";
  const sourceStatus = ioscoDetail?.jurisdiction || prepared?.registration_status || "";
  const referenceDate = ioscoDetail?.validation_date || prepared?.filing_date || "";
  const officialUrl = ioscoDetail?.official_reference_url || prepared?.official_reference_url || record.notice_reference_url || "";
  const liveUrlCheck = ioscoDetail?.live_check_status || (prepared?.reference_source === "sec_iapd" ? "NOT_APPLICABLE" : "");
  return [
    record.pilot_id, record.pilot_rank, record.crimson_match_host, record.match_source_id,
    record.reference_record_id, record.reference_role, record.host_relation,
    record.matched_reference_host, record.reference_host_record_count,
    record.notice_reference_url || "", record.sec_number || "",
    entityNames.join("; "), sourceType, sourceStatus,
    referenceDate ? new Date(`${referenceDate}T00:00:00Z`) : "",
    officialUrl, liveUrlCheck, prepared?.review_notes || "",
    (record.crimson_artifact_ids || []).join("; "),
    (record.observed_crimson_domains || []).join("; "), record.review_status,
  ];
});
evidenceSheet.getRange(`A6:U${5 + evidenceRows.length}`).values = evidenceRows;
evidenceSheet.getRange("A5:U5").format = {
  fill: navy, font: { name: font, size: 10, bold: true, color: "#FFFFFF" },
  horizontalAlignment: "center", verticalAlignment: "center", wrapText: true,
  borders: { preset: "inside", style: "thin", color: "#FFFFFF" },
};
evidenceSheet.getRange(`A6:U${5 + evidenceRows.length}`).format.borders = {
  insideHorizontal: { style: "thin", color: border }, bottom: { style: "thin", color: border },
};
evidenceSheet.getRange(`J6:J${5 + evidenceRows.length}`).format.wrapText = true;
evidenceSheet.getRange(`L6:U${5 + evidenceRows.length}`).format.wrapText = true;
evidenceSheet.getRange(`O6:O${5 + evidenceRows.length}`).setNumberFormat("yyyy-mm-dd");
const evidenceTable = evidenceSheet.tables.add(`A5:U${5 + evidenceRows.length}`, true, "CrimsonReferenceEvidenceTable");
evidenceTable.style = "TableStyleMedium2";
evidenceTable.showFilterButton = true;
evidenceSheet.freezePanes.freezeRows(5);
evidenceSheet.freezePanes.freezeColumns(3);
const evidenceWidths = {
  "A:A": 24, "B:B": 7, "C:C": 28, "D:D": 16, "E:E": 18, "F:F": 34,
  "G:G": 34, "H:H": 28, "I:I": 15, "J:J": 58, "K:K": 18,
  "L:L": 34, "M:N": 30, "O:O": 18, "P:P": 52, "Q:Q": 26,
  "R:R": 76, "S:S": 30, "T:T": 32, "U:U": 16,
};
for (const [range, width] of Object.entries(evidenceWidths)) evidenceSheet.getRange(range).format.columnWidth = width;
evidenceSheet.getRange("5:5").format.rowHeight = 42;
evidenceSheet.getRange(`6:${5 + evidenceRows.length}`).format.rowHeight = 32;
if (firstPass.length) evidenceSheet.getRange(`6:${5 + evidenceRows.length}`).format.rowHeight = 58;

// Guide sheet: concise review protocol and categorical definitions.
guide.tabColor = "#7F8C8D";
guide.getRange("A2").values = [["Review protocol"]];
guide.getRange("A2").format.font = { name: font, size: 15, bold: true, color: navy };
guide.getRange("A4:B4").values = [["Step", "Action"]];
guide.getRange("A5:B11").values = [
  [1, "Start with the Evidence row for the same Pilot ID. Use only the official IOSCO notice or SEC/IAPD record."],
  [2, "Do not open or browse the Crimson host directly on the main machine."],
  [3, "Record whether the reference and Crimson host appear to be the same entity, impersonation, unrelated or unclear."],
  [4, "Record what the official evidence supports. A registration match never proves that the website is legitimate."],
  [5, "Set Review status to COMPLETED only after filling the reference check, relationship, assessment, reviewer, date and notes."],
  [6, "Complete a second review when the workbook marks it required. No pilot row is eligible for training."],
  [7, "AI-assisted rows remain IN_PROGRESS. A human changes them to COMPLETED only after confirming the official record and rationale."],
];
guide.getRange("A13:B13").values = [["Field", "Allowed values and meaning"]];
guide.getRange("A14:B22").values = [
  ["Identity relationship", "SAME_ENTITY, IMPERSONATION_SUSPECTED, UNRELATED or UNCLEAR"],
  ["Evidence assessment", "WARNING_RELEVANT, REGISTRATION_RELEVANT, REFERENCE_NOT_APPLICABLE or INSUFFICIENT_EVIDENCE"],
  ["Official reference checked", "YES only after checking the official regulator reference"],
  ["Second review required", "Calculated as YES for suspected impersonation, unclear identity or a shared reference host"],
  ["Adjudication status", "Calculated. READY requires every mandatory field and any required second review"],
  ["Training eligible", "Always NO for this pilot"],
  ["IOSCO match", "Warning evidence for review. It is not a conviction or complete scam label"],
  ["SEC match", "Registration reference for review. It is not a safety label and does not rule out impersonation"],
  ["Live URL check", "Availability check only. LIVE_NOT_CONFIRMED does not invalidate the frozen IOSCO I-SCAN record"],
];
guide.getRange("A24:B24").values = [["Priority", "Review order meaning"]];
guide.getRange("A25:B29").values = [
  ["P0_IMPERSONATION_SUSPECTED", "Verify clone or impersonation wording first and require two human reviews"],
  ["P1_SECOND_REVIEW_WITH_LIVE_GAP", "Resolve missing official URL access and require two human reviews"],
  ["P2_SECOND_REVIEW_LIVE_CONFIRMED", "Official URLs were confirmed, but shared references still require two human reviews"],
  ["P3_SINGLE_REVIEW_WITH_LIVE_GAP", "Resolve missing official URL access before completing one human review"],
  ["P4_SINGLE_REVIEW_OFFICIAL_REFERENCE", "Complete the remaining single-review official-reference checks"],
];
for (const header of ["A4:B4", "A13:B13", "A24:B24"]) {
  guide.getRange(header).format = {
    fill: navy, font: { name: font, size: 10, bold: true, color: "#FFFFFF" },
    horizontalAlignment: "center", borders: { preset: "inside", style: "thin", color: "#FFFFFF" },
  };
}
guide.getRange("A5:B11").format.borders = { insideHorizontal: { style: "thin", color: border } };
guide.getRange("A14:B22").format.borders = { insideHorizontal: { style: "thin", color: border } };
guide.getRange("A25:B29").format.borders = { insideHorizontal: { style: "thin", color: border } };
guide.getRange("B5:B11").format.wrapText = true;
guide.getRange("B14:B22").format.wrapText = true;
guide.getRange("B25:B29").format.wrapText = true;
guide.getRange("A:A").format.columnWidth = 42;
guide.getRange("B:B").format.columnWidth = 88;
guide.getRange("5:11").format.rowHeight = 34;
guide.getRange("14:22").format.rowHeight = 34;
guide.getRange("25:29").format.rowHeight = 34;

// Test the editable workflow, then restore the untouched pilot before export.
const originalStandard = review.getRange("I10:Q10").values;
review.getRange("I10:Q10").values = [[
  "COMPLETED", "YES", "SAME_ENTITY", "REGISTRATION_RELEVANT", "QA Reviewer",
  new Date("2026-09-23T00:00:00Z"), "Official registration reference checked.",
  "NOT_REQUESTED", "",
]];
workbook.recalculate();
const standardReadyCheck = review.getRange("S10").values[0][0];
const standardPlanIndex = humanReviewPlan.findIndex((row) => Number(row.review_sheet_row) === 10);
const standardPlanReadyCheck = standardPlanIndex >= 0
  ? reviewPlan.getRange(`M${10 + standardPlanIndex}`).values[0][0]
  : null;
review.getRange("I10:Q10").values = originalStandard;

const originalSecondReview = review.getRange("I18:Q18").values;
review.getRange("I18:Q18").values = [[
  "COMPLETED", "YES", "UNCLEAR", "WARNING_RELEVANT", "QA Reviewer",
  new Date("2026-09-23T00:00:00Z"), "Official warning reference checked.",
  "NOT_REQUESTED", "",
]];
workbook.recalculate();
const secondReviewRequiredCheck = review.getRange("S18").values[0][0];
const secondReviewPlanIndex = humanReviewPlan.findIndex((row) => Number(row.review_sheet_row) === 18);
const secondReviewPlanRequiredCheck = secondReviewPlanIndex >= 0
  ? reviewPlan.getRange(`M${10 + secondReviewPlanIndex}`).values[0][0]
  : null;
review.getRange("P18:Q18").values = [["COMPLETED", "Second QA Reviewer"]];
workbook.recalculate();
const secondReviewReadyCheck = review.getRange("S18").values[0][0];
const secondReviewPlanReadyCheck = secondReviewPlanIndex >= 0
  ? reviewPlan.getRange(`M${10 + secondReviewPlanIndex}`).values[0][0]
  : null;
review.getRange("I18:Q18").values = originalSecondReview;

workbook.recalculate();
const reviewInspect = await workbook.inspect({
  kind: "table", range: "Review!A1:T15", include: "values,formulas",
  tableMaxRows: 15, tableMaxCols: 20, maxChars: 12000,
});
const reviewPlanInspect = await workbook.inspect({
  kind: "table", range: "Review plan!A1:O15", include: "values,formulas",
  tableMaxRows: 15, tableMaxCols: 15, maxChars: 16000,
});
const errorInspect = await workbook.inspect({
  kind: "match", searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!",
  options: { useRegex: true, maxResults: 300 }, summary: "final formula error scan", maxChars: 5000,
});

await fs.mkdir(outputDir, { recursive: true });
for (const [sheetName, fileName, range] of [
  ["Review", "preview_review.png", "A1:T18"],
  ["Review", "preview_review_decision.png", "A23:T30"],
  ["Review plan", "preview_review_plan.png", "A1:O18"],
  ["Evidence", "preview_evidence.png", "A1:U18"],
  ["Guide", "preview_guide.png", "A1:B30"],
]) {
  const preview = await workbook.render({ sheetName, range, scale: 1, format: "png" });
  await fs.writeFile(path.join(outputDir, fileName), new Uint8Array(await preview.arrayBuffer()));
}
const outputPath = path.join(outputDir, "Crimson_External_Reference_Review_Pilot_V1.xlsx");
const output = await SpreadsheetFile.exportXlsx(workbook);
await output.save(outputPath);
const reopened = await SpreadsheetFile.importXlsx(await FileBlob.load(outputPath));
const reopenedInspect = await reopened.inspect({
  kind: "table", range: "Review!A5:T10", include: "values,formulas",
  tableMaxRows: 6, tableMaxCols: 20, maxChars: 8000,
});
const criticalIoscoInspect = await reopened.inspect({
  kind: "table", range: "Review!A27:T48", include: "values,formulas",
  tableMaxRows: 22, tableMaxCols: 20, maxChars: 30000,
});
const reopenedErrors = await reopened.inspect({
  kind: "match", searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!",
  options: { useRegex: true, maxResults: 300 }, summary: "reopened formula error scan", maxChars: 5000,
});
console.log(JSON.stringify({
  outputPath,
  pilotRecordCount: pilot.length,
  evidenceRecordCount: evidence.length,
  firstPassRecordCount: firstPass.length,
  humanReviewPlanCount: humanReviewPlan.length,
  humanDecisionCount: humanDecisions.length,
  workflowChecks: {
    standardReadyCheck,
    standardPlanReadyCheck,
    secondReviewRequiredCheck,
    secondReviewPlanRequiredCheck,
    secondReviewReadyCheck,
    secondReviewPlanReadyCheck,
  },
  reviewInspect: reviewInspect.ndjson,
  reviewPlanInspect: reviewPlanInspect.ndjson,
  formulaErrors: errorInspect.ndjson,
  reopenedInspect: reopenedInspect.ndjson,
  criticalIoscoInspect: criticalIoscoInspect.ndjson,
  reopenedFormulaErrors: reopenedErrors.ndjson,
}, null, 2));
