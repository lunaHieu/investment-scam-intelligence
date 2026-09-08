import fs from "node:fs/promises";
import path from "node:path";
import { spawnSync } from "node:child_process";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const root = path.resolve(".");
const rawCsv = "D:/nckh 2026-2027/ISI_Data/raw/mendeley_investment_deceptive_2026/v2/Multimodal_Dataset_for_Investment-Related_Deceptive_Content_Detection_on_Social_Platforms.csv";
const outputDir = path.join(root, "outputs", "mendeley_v2_explorer");
const bundledPython = "C:/Users/hieu/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe";

const analysisCode = String.raw`
import json, re, sys
import pandas as pd

df = pd.read_csv(sys.argv[1])
keywords = r"\b(invest(?:ment|ing)?|stock|forex|crypto|return|profit|trading|broker|shares?|portfolio|dividend|market)\b"
mask = df["text_content"].fillna("").str.contains(keywords, case=False, regex=True)
candidates = df.loc[df["source_dataset"].eq("cresci_stock_2018") & mask, ["record_id", "source_dataset", "source_modality", "label", "text_content"]].head(50).copy()
candidates["candidate_reason"] = "Stock-source record plus investment keyword; manual review required"
candidates["text_content"] = candidates["text_content"].str.replace(r"\s+", " ", regex=True).str.slice(0, 260)
missing_columns = ["followers", "friends_following", "statuses_posts", "account_age_days", "repost_count", "verified_bool", "has_bio", "has_location", "has_url", "is_private"]
out = {
  "shape": [int(df.shape[0]), int(df.shape[1])],
  "label_counts": [[int(k), int(v)] for k,v in df["label"].value_counts().sort_index().items()],
  "partition_counts": [[str(k), int(v)] for k,v in df["partition"].value_counts().items()],
  "modality_counts": [[str(k), int(v)] for k,v in df["source_modality"].value_counts().items()],
  "source_counts": [[str(k), int(v)] for k,v in df["source_dataset"].value_counts().items()],
  "source_label": [[str(index), int(row.get(0, 0)), int(row.get(1, 0))] for index,row in pd.crosstab(df["source_dataset"], df["label"]).iterrows()],
  "missing": [[c, int(df[c].isna().sum()), round(float(df[c].isna().mean()), 4)] for c in missing_columns],
  "candidates": candidates.where(pd.notna(candidates), None).values.tolist()
}
print(json.dumps(out, ensure_ascii=False))
`;

const analysis = spawnSync(bundledPython, ["-X", "utf8", "-c", analysisCode, rawCsv], { encoding: "utf8" });
if (analysis.status !== 0) throw new Error(analysis.stderr || "Could not analyse Mendeley CSV");
const data = JSON.parse(analysis.stdout);

const navy = "#1F4E78";
const blue = "#D9EAF7";
const pale = "#F4F8FB";
const amber = "#FFF2CC";
const red = "#FDE9E7";
const border = { preset: "all", style: "thin", color: "#D9D9D9" };
const font = { name: "Arial", size: 10, color: "#1F2937" };

function styleTitle(sheet, range, title) {
  sheet.mergeCells(range);
  sheet.getRange(range).values = [[title]];
  sheet.getRange(range).format.font = { name: "Arial", size: 15, bold: true, color: "#000000" };
}

function styleHeader(range) {
  range.format.fill = navy;
  range.format.font = { name: "Arial", size: 10, bold: true, color: "#FFFFFF" };
  range.format.horizontalAlignment = "center";
  range.format.verticalAlignment = "center";
  range.format.borders = border;
}

function styleTable(range) {
  range.format.font = font;
  range.format.verticalAlignment = "center";
  range.format.borders = border;
}

const wb = Workbook.create();
const overview = wb.worksheets.add("Tổng quan");
const fields = wb.worksheets.add("Data dictionary");
const summary = wb.worksheets.add("Thống kê");
const preview = wb.worksheets.add("Mẫu candidate");

for (const sheet of [overview, fields, summary, preview]) {
  sheet.showGridLines = false;
  sheet.tabColor = navy;
}

styleTitle(overview, "A2:G2", "Mendeley V2 - Hướng dẫn đọc dataset");
overview.getRange("A3:G3").merge();
overview.getRange("A3").values = [["Bản đọc dữ liệu để khám phá. CSV raw giữ nguyên ở kho dữ liệu chung; workbook này không tạo ground truth."]];
overview.getRange("A3").format.font = { name: "Arial", size: 10, italic: true, color: "#4B5563" };
overview.getRange("A5:B9").values = [
  ["Chỉ số", "Giá trị"],
  ["Số record", data.shape[0]],
  ["Số cột", data.shape[1]],
  ["Text + metadata", data.modality_counts.find((x) => x[0] === "text_plus_metadata")?.[1] ?? 0],
  ["Text only", data.modality_counts.find((x) => x[0] === "text_only")?.[1] ?? 0],
];
styleHeader(overview.getRange("A5:B5")); styleTable(overview.getRange("A6:B9"));
overview.getRange("B6:B9").format.numberFormat = "#,##0";
overview.getRange("D5:G5").merge(); overview.getRange("D5").values = [["Cách hiểu đúng"]]; styleHeader(overview.getRange("D5:G5"));
overview.getRange("D6:G10").merge();
overview.getRange("D6").values = [["Mỗi dòng là một nội dung text đã được nguồn gốc gán nhãn benchmark 0/1. Dataset dùng cho baseline text và nghiên cứu metadata. Nó không chứng minh từng dòng là lừa đảo đầu tư đã xác minh, nên không được dùng làm Gold ground truth."]];
overview.getRange("D6").format = { font, fill: pale, wrapText: true, verticalAlignment: "top", borders: border };
overview.getRange("D12:G12").merge(); overview.getRange("D12").values = [["Không dùng làm feature model"]]; styleHeader(overview.getRange("D12:G12"));
overview.getRange("D13:G16").merge();
overview.getRange("D13").values = [["record_id, source_dataset, partition, gate_path, investment_score, lexicon_score và semantic_score là metadata/provenance hoặc dấu vết lọc của nguồn. Dùng chúng để audit, không dùng để dự báo scam."]];
overview.getRange("D13").format = { font, fill: red, wrapText: true, verticalAlignment: "top", borders: border };
overview.getRange("A12:B12").values = [["Điểm bắt đầu an toàn", "Việc cần làm"]]; styleHeader(overview.getRange("A12:B12"));
overview.getRange("A13:B16").values = [
  ["1", "Đọc Data dictionary để biết từng nhóm cột."],
  ["2", "Xem Thống kê để nhận diện lệch nguồn và missing data."],
  ["3", "Đọc Mẫu candidate như danh sách cần review, không phải nhãn thật."],
  ["4", "Khi làm model text, bắt đầu bằng text_content + label sau split của ISI."],
];
styleTable(overview.getRange("A13:B16"));
overview.getRange("A18:G18").merge();
overview.getRange("A18").values = [["Nguồn: Mendeley Data V2, DOI 10.17632/6wnd7jrt6z.2, CC BY 4.0. Raw labels are deceptive/suspicious, not verified investment-scam status."]];
overview.getRange("A18").format.font = { name: "Arial", size: 9, italic: true, color: "#4B5563" };
overview.getRange("A:A").format.columnWidth = 22; overview.getRange("B:B").format.columnWidth = 42;
overview.getRange("C:C").format.columnWidth = 4; overview.getRange("D:G").format.columnWidth = 20;
overview.getRange("A1:G20").format.font = font;

styleTitle(fields, "A2:D2", "Data dictionary - Các cột cần hiểu");
fields.getRange("A4:D4").values = [["Nhóm", "Cột", "Ý nghĩa", "Dùng trong ISI"]]; styleHeader(fields.getRange("A4:D4"));
const fieldRows = [
  ["Định danh", "record_id", "ID duy nhất của record gốc.", "Traceability; không làm feature."],
  ["Provenance", "source_dataset", "Nhóm dữ liệu gốc: phishing, spam, fake profile, bot hoặc stock.", "Audit bias; không làm feature."],
  ["Provenance", "source_modality, has_metadata", "Có text-only hay text kèm metadata.", "Chọn subset/ablation; không suy ra nhãn."],
  ["Nội dung", "text_content", "Nội dung text đã anonymize.", "Input text baseline."],
  ["Nhãn gốc", "label", "Nhãn 0/1 của benchmark nguồn.", "Training label only; không phải Gold."],
  ["Split nguồn", "partition", "Train/validation/test do tác giả nguồn tạo.", "Chỉ tham khảo; ISI split lại theo case/campaign."],
  ["Dấu vết lọc", "gate_path, lexicon_hits, lexicon_score, semantic_score, investment_score", "Cách nguồn chọn nội dung liên quan đầu tư.", "Audit data construction; cấm làm feature."],
  ["Behavior", "followers đến default_profile_image_flag", "Metadata tài khoản/nội dung, có missingness theo nguồn.", "Behavior extension sau khi Core ổn."],
  ["Text length", "content_length, word_count", "Độ dài text đã tính sẵn.", "EDA/quality control; không cần cho text baseline đầu."],
];
fields.getRange(`A5:D${4 + fieldRows.length}`).values = fieldRows; styleTable(fields.getRange(`A5:D${4 + fieldRows.length}`));
fields.getRange(`A11:D11`).format.fill = amber;
fields.getRange("A:A").format.columnWidth = 16; fields.getRange("B:B").format.columnWidth = 38; fields.getRange("C:C").format.columnWidth = 48; fields.getRange("D:D").format.columnWidth = 42;
fields.getRange(`A4:D${4 + fieldRows.length}`).format.wrapText = true; fields.freezePanes.freezeRows(4);

styleTitle(summary, "A2:H2", "Thống kê chất lượng Mendeley V2");
summary.getRange("A4:B4").values = [["Nhãn gốc", "Số record"]]; styleHeader(summary.getRange("A4:B4"));
summary.getRange("A5:B6").values = data.label_counts.map(([label, count]) => [`label = ${label}`, count]); styleTable(summary.getRange("A5:B6"));
summary.getRange("D4:E4").values = [["Partition nguồn", "Số record"]]; styleHeader(summary.getRange("D4:E4"));
summary.getRange("D5:E7").values = data.partition_counts; styleTable(summary.getRange("D5:E7"));
summary.getRange("G4:H4").values = [["Modality", "Số record"]]; styleHeader(summary.getRange("G4:H4"));
summary.getRange("G5:H6").values = data.modality_counts; styleTable(summary.getRange("G5:H6"));
summary.getRange("A10:C10").values = [["Nguồn gốc", "label = 0", "label = 1"]]; styleHeader(summary.getRange("A10:C10"));
summary.getRange(`A11:C${10 + data.source_label.length}`).values = data.source_label; styleTable(summary.getRange(`A11:C${10 + data.source_label.length}`));
summary.getRange("E10:F10").values = [["Nguồn gốc", "Số record"]]; styleHeader(summary.getRange("E10:F10"));
summary.getRange(`E11:F${10 + data.source_counts.length}`).values = data.source_counts; styleTable(summary.getRange(`E11:F${10 + data.source_counts.length}`));
summary.getRange("A19:C19").values = [["Behavior field", "Thiếu", "Tỷ lệ thiếu"]]; styleHeader(summary.getRange("A19:C19"));
summary.getRange(`A20:C${19 + data.missing.length}`).values = data.missing; styleTable(summary.getRange(`A20:C${19 + data.missing.length}`));
summary.getRange(`C20:C${19 + data.missing.length}`).format.numberFormat = "0.0%";
summary.getRange("A:A").format.columnWidth = 28; summary.getRange("B:C").format.columnWidth = 14; summary.getRange("D:D").format.columnWidth = 22; summary.getRange("E:F").format.columnWidth = 22; summary.getRange("G:G").format.columnWidth = 26; summary.getRange("H:H").format.columnWidth = 14;
summary.freezePanes.freezeRows(4);

styleTitle(preview, "A2:F2", "Mẫu candidate liên quan đầu tư để review");
preview.getRange("A3:F3").merge();
preview.getRange("A3").values = [["Mẫu từ nhóm Cresci stock và khớp keyword đầu tư tiếng Anh. Đây là candidate để review thủ công, không phải confirmed investment scam."]];
preview.getRange("A3").format = { font: { name: "Arial", size: 10, italic: true, color: "#4B5563" }, fill: amber, wrapText: true, borders: border };
preview.getRange("A5:F5").values = [["record_id", "source_dataset", "source_modality", "label gốc", "text_content (rút gọn)", "candidate_reason"]]; styleHeader(preview.getRange("A5:F5"));
preview.getRange(`A6:F${5 + data.candidates.length}`).values = data.candidates; styleTable(preview.getRange(`A6:F${5 + data.candidates.length}`));
preview.getRange(`A6:F${5 + data.candidates.length}`).format.wrapText = true;
preview.getRange("A:A").format.columnWidth = 18; preview.getRange("B:B").format.columnWidth = 22; preview.getRange("C:C").format.columnWidth = 20; preview.getRange("D:D").format.columnWidth = 11; preview.getRange("E:E").format.columnWidth = 75; preview.getRange("F:F").format.columnWidth = 42;
preview.freezePanes.freezeRows(5); preview.freezePanes.freezeColumns(1);

for (const sheet of [overview, fields, summary, preview]) {
  const used = sheet.getUsedRange();
  used.format.verticalAlignment = "center";
  used.format.autofitRows();
}
overview.getRange("D6:G10").format.rowHeight = 32;
overview.getRange("D13:G16").format.rowHeight = 28;
preview.getRange(`A6:F${5 + data.candidates.length}`).format.rowHeight = 36;

wb.recalculate();
await fs.mkdir(outputDir, { recursive: true });
for (const sheetName of ["Tổng quan", "Data dictionary", "Thống kê", "Mẫu candidate"]) {
  const image = await wb.render({ sheetName, autoCrop: "all", scale: 1.25, format: "png" });
  await fs.writeFile(path.join(outputDir, `${sheetName}.png`), new Uint8Array(await image.arrayBuffer()));
}
const output = await SpreadsheetFile.exportXlsx(wb);
await output.save(path.join(outputDir, "Mendeley_V2_Explorer.xlsx"));
console.log(JSON.stringify({ output: path.join(outputDir, "Mendeley_V2_Explorer.xlsx"), candidates: data.candidates.length }));
