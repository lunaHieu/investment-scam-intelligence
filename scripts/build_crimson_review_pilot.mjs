import crypto from "node:crypto";
import fs from "node:fs/promises";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const candidatePath = "D:/nckh 2026-2027/ISI_Data/interim/crimson_www_2025/b040e2def08ea26058ef9da752b72fa4a5238987/candidate_url_artifacts_v2.jsonl";
const outputDir = "outputs/crimson_review_pilot";
const outputPath = `${outputDir}/ISI_Crimson_Curated_Pilot_Review.xlsx`;
const sampleSize = 100;
const sampleSeed = "ISI_CRIMSON_REVIEW_V1";
const font = "Arial";

const hash = (value) => crypto.createHash("sha256").update(value).digest("hex");
const lines = (await fs.readFile(candidatePath, "utf8")).trim().split(/\r?\n/);
const candidates = lines.map((line) => JSON.parse(line));
const sample = candidates
  .map((item) => ({ item, selectionHash: hash(`${sampleSeed}|${item.artifact_id}`) }))
  .sort((a, b) => a.selectionHash.localeCompare(b.selectionHash))
  .slice(0, sampleSize);

const workbook = Workbook.create();
const overview = workbook.worksheets.add("Tổng quan");
const queue = workbook.worksheets.add("Review queue");
const protocol = workbook.worksheets.add("Protocol");
for (const sheet of [overview, queue, protocol]) {
  sheet.showGridLines = false;
  sheet.getRange("A1:Q120").format.font = { name: font, size: 10, color: "#1F2937" };
}

overview.getRange("A2:F2").merge();
overview.getRange("A2").values = [["ISI Crimson – Curated pilot review"]];
overview.getRange("A2").format = { font: { name: font, size: 15, bold: true, color: "#1F2937" } };
overview.getRange("A3:F3").merge();
overview.getRange("A3").values = [["Batch xác định trước gồm 100 candidate URL từ Crimson. Chưa có dòng nào là nhãn ground truth hoặc dữ liệu train."]];
overview.getRange("A3").format = { font: { name: font, size: 10, italic: true, color: "#4B5563" } };
overview.getRange("A5:B9").values = [
  ["Chỉ số", "Giá trị"],
  ["Candidate trong batch", sampleSize],
  ["Nguồn candidate", candidates.length],
  ["Trạng thái ban đầu", "UNREVIEWED"],
  ["Case Gold", 0],
];
overview.getRange("A5:B5").format = { fill: "#1F4E78", font: { name: font, bold: true, color: "#FFFFFF" }, horizontalAlignment: "center" };
overview.getRange("A5:B9").format.borders = { preset: "all", style: "thin", color: "#D9D9D9" };
overview.getRange("D5:E10").values = [
  ["Review status", "Số dòng"],
  ["UNREVIEWED", null],
  ["IN_REVIEW", null],
  ["REVIEWED", null],
  ["RECONCILED", null],
  ["Tổng", null],
];
overview.getRange("D5:E5").format = { fill: "#1F4E78", font: { name: font, bold: true, color: "#FFFFFF" }, horizontalAlignment: "center" };
overview.getRange("D5:E10").format.borders = { preset: "all", style: "thin", color: "#D9D9D9" };
overview.getRange("E6:E9").formulas = [
  ['=COUNTIF(\'Review queue\'!$G$2:$G$101,D6)'],
  ['=COUNTIF(\'Review queue\'!$G$2:$G$101,D7)'],
  ['=COUNTIF(\'Review queue\'!$G$2:$G$101,D8)'],
  ['=COUNTIF(\'Review queue\'!$G$2:$G$101,D9)'],
];
overview.getRange("E10").formulas = [["=SUM(E6:E9)"]];
overview.getRange("A12:F16").values = [
  ["Quy tắc sử dụng", null, null, null, null, null],
  ["1", "Không mở URL từ workbook trong quá trình kiểm tra tự động.", null, null, null, null],
  ["2", "Chỉ gán CONFIRMED khi evidence trực tiếp đáp ứng guideline; một research label không đủ.", null, null, null, null],
  ["3", "Giữ case_id trống trong batch này. Tạo case sau khi liên kết evidence và review rationale.", null, null, null, null],
  ["4", "Không export batch này vào train, validation, test hoặc Gold.", null, null, null, null],
];
overview.getRange("A12:F12").format = { fill: "#D9EAF7", font: { name: font, bold: true, color: "#1F2937" } };
overview.getRange("A12:F16").format.borders = { preset: "outside", style: "thin", color: "#A6A6A6" };
overview.getRange("A18:F18").merge();
overview.getRange("A18").values = [["Nguồn: Crimson data.json, commit b040e2def08ea26058ef9da752b72fa4a5238987; 43.572 candidate URL, canonicalized without fetching any URL."]];
overview.getRange("A18").format = { font: { name: font, size: 9, italic: true, color: "#4B5563" } };
overview.getRange("A:A").format.columnWidth = 18;
overview.getRange("B:B").format.columnWidth = 43;
overview.getRange("C:C").format.columnWidth = 3;
overview.getRange("D:D").format.columnWidth = 22;
overview.getRange("E:E").format.columnWidth = 14;
overview.getRange("F:F").format.columnWidth = 20;

const headers = [
  "queue_id", "artifact_id", "source_record_id", "domain", "url_canonical", "source_label",
  "review_status", "ground_truth_status", "primary_subtype", "evidence_url_1", "evidence_url_2",
  "evidence_summary", "reviewer", "reviewed_date", "review_rationale", "review_gate", "secondary_tactics",
];
queue.getRange("A1:Q1").values = [headers];
const queueRows = sample.map(({ item }, index) => [
  `REV_CRIMSON_${String(index + 1).padStart(3, "0")}`,
  item.artifact_id,
  item.source_record_id,
  item.domain,
  item.url,
  item.source_label,
  "UNREVIEWED",
  "",
  "",
  "",
  "",
  "",
  "",
  "",
  "",
  "",
  "",
]);
queue.getRange(`A2:Q${sampleSize + 1}`).values = queueRows;
queue.getRange("P2").formulas = [[`=IF(G2="UNREVIEWED","PENDING",IF(AND(H2<>"",I2<>"",J2<>"",L2<>""),"READY_FOR_RECONCILIATION","MISSING_EVIDENCE_OR_RATIONALE"))`]];
queue.getRange(`P2:P${sampleSize + 1}`).fillDown();
queue.getRange("A1:Q1").format = { fill: "#1F4E78", font: { name: font, bold: true, color: "#FFFFFF" }, horizontalAlignment: "center", verticalAlignment: "center", wrapText: true };
queue.getRange(`A1:Q${sampleSize + 1}`).format.borders = { preset: "outside", style: "thin", color: "#D9D9D9" };
queue.getRange(`G2:O${sampleSize + 1}`).format.fill = "#FFF2CC";
queue.getRange(`P2:P${sampleSize + 1}`).format.fill = "#E2F0D9";
queue.getRange(`N2:N${sampleSize + 1}`).format.numberFormat = "yyyy-mm-dd";
queue.getRange(`A2:Q${sampleSize + 1}`).format.verticalAlignment = "center";
queue.getRange(`E2:E${sampleSize + 1}`).format.columnWidth = 38;
queue.getRange(`J2:K${sampleSize + 1}`).format.columnWidth = 34;
queue.getRange(`L2:L${sampleSize + 1}`).format.columnWidth = 38;
queue.getRange(`O2:O${sampleSize + 1}`).format.columnWidth = 42;
for (const column of ["A", "B", "C", "D", "F", "G", "H", "I", "M", "N", "P", "Q"]) queue.getRange(`${column}:${column}`).format.columnWidth = 18;
queue.getRange(`G2:G${sampleSize + 1}`).dataValidation = { rule: { type: "list", values: ["UNREVIEWED", "IN_REVIEW", "REVIEWED", "RECONCILED"] } };
queue.getRange(`H2:H${sampleSize + 1}`).dataValidation = { rule: { type: "list", values: ["", "CONFIRMED", "LEGITIMATE", "UNCERTAIN"] } };
queue.getRange(`I2:I${sampleSize + 1}`).dataValidation = { rule: { type: "list", values: ["", "FAKE_PLATFORM_BROKER", "HIGH_RETURN_GUARANTEE", "FAKE_ADVISOR_GROUP", "PONZI_HYIP", "MARKET_OPPORTUNITY_SCAM", "TRAINING_COACHING_SCAM", "OTHER_EMERGING"] } };
queue.getRange(`P2:P${sampleSize + 1}`).conditionalFormats.add("containsText", { text: "MISSING", format: { fill: "#FCE4D6", font: { color: "#9C0006" } } });
queue.tables.add(`A1:Q${sampleSize + 1}`, true, "CrimsonReviewQueue");
queue.freezePanes.freezeRows(1);
queue.freezePanes.freezeColumns(4);

protocol.getRange("A2:E2").merge();
protocol.getRange("A2").values = [["Protocol review – Crimson curated pilot"]];
protocol.getRange("A2").format = { font: { name: font, size: 14, bold: true, color: "#1F2937" } };
protocol.getRange("A4:E9").values = [
  ["Bước", "Hành động", "Kết quả cần ghi", "Không được làm", "Điều kiện chuyển bước"],
  ["1", "Review domain và nguồn evidence ngoài candidate", "evidence_url_1, evidence_summary", "Không coi research label là kết luận", "Có evidence truy vết được"],
  ["2", "Gán trạng thái ground truth", "CONFIRMED / LEGITIMATE / UNCERTAIN", "Không ép binary khi evidence thiếu", "Có rationale"],
  ["3", "Gán subtype chính và tactics phụ", "primary_subtype, secondary_tactics", "Không suy luận từ source_id", "Phù hợp evidence"],
  ["4", "Ghi reviewer và ngày review", "reviewer, reviewed_date", "Không bỏ trống rationale", "Review gate xanh"],
  ["5", "Reconcile subset bởi reviewer khác", "review_status = RECONCILED", "Không tạo Gold trước reconciliation", "Case có thể được tạo riêng"],
];
protocol.getRange("A4:E4").format = { fill: "#1F4E78", font: { name: font, bold: true, color: "#FFFFFF" }, horizontalAlignment: "center", wrapText: true };
protocol.getRange("A4:E9").format.borders = { preset: "all", style: "thin", color: "#D9D9D9" };
protocol.getRange("A:A").format.columnWidth = 10;
protocol.getRange("B:B").format.columnWidth = 35;
protocol.getRange("C:C").format.columnWidth = 34;
protocol.getRange("D:D").format.columnWidth = 40;
protocol.getRange("E:E").format.columnWidth = 30;

workbook.recalculate();
const inspection = await workbook.inspect({ kind: "table", range: "Review queue!A1:Q8", include: "values,formulas", tableMaxRows: 8, tableMaxCols: 17 });
await fs.mkdir(outputDir, { recursive: true });
await fs.writeFile(`${outputDir}/inspect.ndjson`, inspection.ndjson);
for (const [sheetName, range, fileName] of [["Tổng quan", "A1:F18", "overview.png"], ["Review queue", "A1:Q14", "queue.png"], ["Protocol", "A1:E10", "protocol.png"]]) {
  const preview = await workbook.render({ sheetName, range, scale: 1.4, format: "png" });
  await fs.writeFile(`${outputDir}/${fileName}`, new Uint8Array(await preview.arrayBuffer()));
}
const output = await SpreadsheetFile.exportXlsx(workbook);
await output.save(outputPath);
console.log(JSON.stringify({ outputPath, sampleSize, sampleSeed, inputCount: candidates.length }));
