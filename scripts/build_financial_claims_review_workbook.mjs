import fs from "node:fs/promises";
import path from "node:path";
import crypto from "node:crypto";
import { FileBlob, SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const DEFAULT_QUEUE = "D:\\nckh 2026-2027\\ISI_Data\\derived\\mendeley_investment_deceptive_2026\\financial_claims_v1\\review_queue_120.jsonl";
const DEFAULT_PROFILE = "D:\\nckh 2026-2027\\ISI_Data\\derived\\mendeley_investment_deceptive_2026\\financial_claims_v1\\profile_v1.json";
const DEFAULT_REGISTRY = "registry/features/mendeley_financial_claims_v1.json";

const FONT = "Arial";
const COLORS = {
  navy: "#1F4E78",
  blue: "#D9EAF7",
  lightBlue: "#EAF2F8",
  yellow: "#FFF2CC",
  green: "#E2F0D9",
  greenText: "#375623",
  red: "#FCE4D6",
  redText: "#9C0006",
  gray: "#E7E6E6",
  grayText: "#595959",
  white: "#FFFFFF",
  text: "#1F1F1F",
  line: "#B4C6E7",
};

const SIGNAL_LABELS = {
  RETURN_RATE: "Tỷ suất lợi nhuận có phần trăm",
  RETURN_MULTIPLE: "Lợi nhuận dạng nhân nhiều lần",
  MONEY_AMOUNT: "Số tiền có đơn vị tiền tệ",
  GUARANTEED_RETURN: "Cam kết lợi nhuận chắc chắn",
  NO_RISK: "Không có rủi ro hoặc không thể thua lỗ",
  URGENCY_SCARCITY: "Gây khẩn cấp hoặc khan hiếm",
  PASSIVE_OR_EASY_INCOME: "Thu nhập thụ động, dễ dàng hoặc làm giàu nhanh",
  RECRUITMENT_REWARD: "Thưởng hoặc thu nhập gắn với tuyển/giới thiệu người",
  PAYMENT_OR_TRANSFER_REQUEST: "Yêu cầu gửi, chuyển hoặc nạp tài sản",
  ADVANCE_FEE_OR_WITHDRAWAL: "Phí/thuế gắn với mở khóa hoặc rút tiền",
  CRYPTO_INVESTMENT_OR_PAYMENT: "Crypto gắn với đầu tư, thanh toán, chuyển tiền hoặc lợi nhuận",
};

function parseArgs(argv) {
  const result = { queue: DEFAULT_QUEUE, profile: DEFAULT_PROFILE, registry: DEFAULT_REGISTRY, renderDir: null, output: null };
  for (let i = 0; i < argv.length; i += 2) {
    const key = argv[i];
    const value = argv[i + 1];
    if (!value || !key.startsWith("--")) throw new Error(`Đối số không hợp lệ: ${key ?? ""}`);
    const normalized = key.slice(2).replace(/-([a-z])/g, (_, c) => c.toUpperCase());
    if (!(normalized in result)) throw new Error(`Đối số không được hỗ trợ: ${key}`);
    result[normalized] = value;
  }
  if (!result.renderDir) throw new Error("Thiếu --render-dir");
  return result;
}

function sha256(buffer) {
  return crypto.createHash("sha256").update(buffer).digest("hex");
}

function parseJsonl(text) {
  return text.split(/\r?\n/).filter(Boolean).map((line, index) => {
    try {
      return JSON.parse(line);
    } catch (error) {
      throw new Error(`JSONL lỗi ở dòng ${index + 1}: ${error.message}`);
    }
  });
}

function colLetter(index) {
  let value = index + 1;
  let letters = "";
  while (value > 0) {
    const remainder = (value - 1) % 26;
    letters = String.fromCharCode(65 + remainder) + letters;
    value = Math.floor((value - 1) / 26);
  }
  return letters;
}

function styleTitle(sheet, address) {
  const range = sheet.getRange(address);
  range.format.font = { name: FONT, size: 15, bold: true, color: COLORS.navy };
  range.format.borders = { bottom: { style: "medium", color: COLORS.navy } };
}

function styleSectionHeader(range) {
  range.format = {
    fill: COLORS.navy,
    font: { name: FONT, size: 10, bold: true, color: COLORS.white },
    horizontalAlignment: "center",
    verticalAlignment: "center",
    wrapText: true,
    borders: { preset: "inside", style: "thin", color: COLORS.white },
  };
}

function styleBody(range) {
  range.format.font = { name: FONT, size: 10, color: COLORS.text };
  range.format.verticalAlignment = "top";
}

function buildReviewUnits(records) {
  const units = [];
  records.forEach((record, index) => {
    const sourceRank = index + 1;
    const signals = Array.isArray(record.signal_types) ? record.signal_types : [];
    const targets = signals.length > 0 ? signals : ["NO_SIGNAL_AUDIT"];
    targets.forEach((target, targetIndex) => {
      units.push({
        review_unit_id: `FCV1-${String(sourceRank).padStart(3, "0")}-${String(targetIndex + 1).padStart(2, "0")}`,
        source_rank: sourceRank,
        pilot_scope: sourceRank <= 20 ? "PILOT_20" : "LATER_100",
        record_id: record.record_id,
        partition: record.partition,
        queue_reason: record.queue_reason,
        target_signal: target,
        detected_signals: signals.join(", "),
        text_excerpt: record.text_excerpt,
        evidence_context: (record.evidence_contexts ?? []).join(" || "),
      });
    });
  });
  return units;
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const [queueBuffer, profileText, registryText] = await Promise.all([
    fs.readFile(args.queue),
    fs.readFile(args.profile, "utf8"),
    fs.readFile(args.registry, "utf8"),
  ]);
  const queueHash = sha256(queueBuffer);
  const records = parseJsonl(queueBuffer.toString("utf8"));
  const profile = JSON.parse(profileText);
  const registry = JSON.parse(registryText);
  const expectedHash = registry.artifacts.find((item) => item.role === "review_queue")?.sha256;

  if (queueHash !== expectedHash) throw new Error(`SHA-256 review queue không khớp registry: ${queueHash} != ${expectedHash}`);
  if (records.length !== 120) throw new Error(`Review queue phải có 120 record, thực tế ${records.length}`);
  if (new Set(records.map((row) => row.record_id)).size !== 120) throw new Error("record_id trong review queue không duy nhất");
  if (new Set(records.map((row) => row.split_group_id)).size !== 120) throw new Error("split_group_id trong review queue không duy nhất");
  if (records.some((row) => row.review_status !== "UNREVIEWED")) throw new Error("Review queue nguồn không còn ở trạng thái UNREVIEWED hoàn toàn");

  const reviewUnits = buildReviewUnits(records);
  const pilotUnits = reviewUnits.filter((unit) => unit.pilot_scope === "PILOT_20").length;
  const candidateRecords = records.filter((row) => row.queue_reason === "SIGNAL_CANDIDATE").length;
  const noSignalRecords = records.filter((row) => row.queue_reason === "NO_SIGNAL_AUDIT").length;
  if (candidateRecords !== 80 || noSignalRecords !== 40) throw new Error("Cơ cấu queue không còn là 80 candidate + 40 no-signal audit");

  const workbook = Workbook.create();
  const overview = workbook.worksheets.add("Tong quan");
  const review = workbook.worksheets.add("Danh gia");
  const source = workbook.worksheets.add("Nguon 120");
  overview.showGridLines = false;
  review.showGridLines = false;
  source.showGridLines = false;
  overview.tabColor = COLORS.navy;
  review.tabColor = "#5B9BD5";

  overview.getRange("A2:H2").values = [["Financial Claims V1 - kiểm tra thủ công", null, null, null, null, null, null, null]];
  styleTitle(overview, "A2:H2");
  overview.getRange("A4:H4").values = [["Mục tiêu: xác nhận độ đúng của rule trên train/validation. Đây không phải nhãn scam và không dùng dữ liệu test.", null, null, null, null, null, null, null]];
  overview.getRange("A4:H4").format = { fill: COLORS.yellow, font: { name: FONT, size: 10, bold: true, color: COLORS.text }, wrapText: true };
  overview.getRange("A4:H4").format.rowHeight = 32;

  overview.getRange("A6:B6").values = [["Phạm vi", "Giá trị"]];
  styleSectionHeader(overview.getRange("A6:B6"));
  overview.getRange("A7:B14").values = [
    ["Record nguồn", records.length],
    ["Review unit", reviewUnits.length],
    ["Record pilot", 20],
    ["Review unit pilot", pilotUnits],
    ["Signal candidate", candidateRecords],
    ["No-signal audit", noSignalRecords],
    ["Partition", "train + validation"],
    ["Nội dung test đã xử lý", profile.test_partition_text_processed],
  ];
  styleBody(overview.getRange("A7:B14"));
  overview.getRange("A7:A14").format.font = { name: FONT, size: 10, bold: true, color: COLORS.text };
  overview.getRange("B7:B14").format.horizontalAlignment = "right";

  const reviewStartRow = 11;
  const reviewEndRow = reviewStartRow + reviewUnits.length - 1;
  overview.getRange("D6:E6").values = [["Tiến độ", "Giá trị"]];
  styleSectionHeader(overview.getRange("D6:E6"));
  overview.getRange("D7:D11").values = [["Hoàn tất"], ["Chưa hoàn tất"], ["Hoàn tất pilot"], ["Tổng pilot"], ["Tỷ lệ hoàn tất"]];
  overview.getRange("E7:E11").formulas = [
    [`=COUNTIFS('Danh gia'!$P$${reviewStartRow}:$P$${reviewEndRow},"HOÀN TẤT")`],
    [`=${reviewUnits.length}-E7`],
    [`=COUNTIFS('Danh gia'!$C$${reviewStartRow}:$C$${reviewEndRow},"PILOT_20",'Danh gia'!$P$${reviewStartRow}:$P$${reviewEndRow},"HOÀN TẤT")`],
    [`=${pilotUnits}`],
    [`=E7/${reviewUnits.length}`],
  ];
  styleBody(overview.getRange("D7:E11"));
  overview.getRange("D7:D11").format.font = { name: FONT, size: 10, bold: true, color: COLORS.text };
  overview.getRange("E7:E10").format.numberFormat = "#,##0";
  overview.getRange("E11").format.numberFormat = "0.0%";
  overview.getRange("E7:E11").format.fill = COLORS.green;
  overview.getRange("E7:E11").format.font = { name: FONT, size: 10, bold: true, color: COLORS.greenText };

  overview.getRange("A17:H17").values = [["Cách review", null, null, null, null, null, null, null]];
  overview.getRange("A17:H17").format = { fill: COLORS.blue, font: { name: FONT, size: 11, bold: true, color: COLORS.navy } };
  overview.getRange("A18:H23").values = [
    ["1", "Mở sheet Danh gia và lọc cột pilot_scope = PILOT_20.", null, null, null, null, null, null],
    ["2", "Đọc text_excerpt và evidence_context. Đánh giá target_signal, không đánh giá record có phải scam hay không.", null, null, null, null, null, null],
    ["3", "Với signal candidate: chọn CORRECT, INCORRECT hoặc UNCERTAIN.", null, null, null, null, null, null],
    ["4", "Với NO_SIGNAL_AUDIT: chọn NO_MISSED_SIGNAL, MISSED_SIGNAL hoặc UNCERTAIN.", null, null, null, null, null, null],
    ["5", "Nếu MISSED_SIGNAL, chọn missed_signal_type. Nếu INCORRECT, MISSED_SIGNAL hoặc UNCERTAIN, ghi rationale ngắn.", null, null, null, null, null, null],
    ["6", "Điền reviewer và reviewed_date. Chỉ coi là xong khi completion_status = HOÀN TẤT.", null, null, null, null, null, null],
  ];
  overview.getRange("A18:A23").format = { font: { name: FONT, size: 10, bold: true, color: COLORS.navy }, horizontalAlignment: "center" };
  overview.getRange("B18:H23").format = { font: { name: FONT, size: 10, color: COLORS.text }, wrapText: true, verticalAlignment: "top" };
  overview.getRange("A18:H23").format.borders = { bottom: { style: "thin", color: COLORS.line } };

  const signalRows = Object.entries(SIGNAL_LABELS).map(([id, label]) => [id, label]);
  overview.getRange("A26:B26").values = [["Signal ID", "Ý nghĩa cần kiểm tra"]];
  styleSectionHeader(overview.getRange("A26:B26"));
  overview.getRangeByIndexes(26, 0, signalRows.length, 2).values = signalRows;
  styleBody(overview.getRange(`A27:B${26 + signalRows.length}`));
  overview.getRange(`A27:A${26 + signalRows.length}`).format.font = { name: FONT, size: 9, bold: true, color: COLORS.navy };
  overview.getRange(`A27:B${26 + signalRows.length}`).format.borders = { bottom: { style: "thin", color: "#D9E2F3" } };

  overview.getRange("D26:E26").values = [["Nguồn kiểm tra", "Giá trị"]];
  styleSectionHeader(overview.getRange("D26:E26"));
  overview.getRange("D27:E31").values = [
    ["Feature version", profile.feature_version],
    ["Queue file", path.basename(args.queue)],
    ["Queue SHA-256", queueHash],
    ["Rule set SHA-256", profile.rule_set_sha256],
    ["Queue trạng thái gốc", "UNREVIEWED"],
  ];
  styleBody(overview.getRange("D27:E31"));
  overview.getRange("D27:D31").format.font = { name: FONT, size: 10, bold: true, color: COLORS.text };
  overview.getRange("E29:E30").format.font = { name: "Consolas", size: 8, color: COLORS.grayText };

  overview.getRange("A1:H40").format.verticalAlignment = "center";
  overview.getRange("A:A").format.columnWidth = 33;
  overview.getRange("B:B").format.columnWidth = 68;
  overview.getRange("C:C").format.columnWidth = 3;
  overview.getRange("D:D").format.columnWidth = 25;
  overview.getRange("E:E").format.columnWidth = 70;
  overview.getRange("F:H").format.columnWidth = 4;
  overview.getRange("A18:H23").format.rowHeight = 30;

  review.getRange("A2:P2").values = [["Đánh giá rule - 203 review unit từ 120 record", null, null, null, null, null, null, null, null, null, null, null, null, null, null, null]];
  styleTitle(review, "A2:P2");
  review.getRange("A4:P4").values = [[`Bắt đầu bằng ${pilotUnits} review unit thuộc 20 record PILOT_20. Chỉ nhập vào các cột màu vàng.`, null, null, null, null, null, null, null, null, null, null, null, null, null, null, null]];
  review.mergeCells("A4:P4");
  review.getRange("A4:P4").format = { fill: COLORS.yellow, font: { name: FONT, size: 10, bold: true, color: COLORS.text }, wrapText: true };
  review.getRange("A5:P5").values = [["Không sửa cột nguồn. CORRECT/INCORRECT áp dụng cho target_signal. NO_MISSED_SIGNAL/MISSED_SIGNAL chỉ áp dụng cho NO_SIGNAL_AUDIT.", null, null, null, null, null, null, null, null, null, null, null, null, null, null, null]];
  review.mergeCells("A5:P5");
  review.getRange("A5:P5").format = { fill: COLORS.lightBlue, font: { name: FONT, size: 10, color: COLORS.text }, wrapText: true };
  review.getRange("A7:P7").values = [["Trường nhập", null, null, null, null, null, null, null, null, null, "review_outcome", "missed_signal_type", "rationale", "reviewer", "reviewed_date", "completion_status tự tính"]];
  review.getRange("A7:P7").format = { font: { name: FONT, size: 9, italic: true, color: COLORS.grayText } };
  review.getRange("K7:O7").format.fill = COLORS.yellow;
  review.getRange("P7").format.fill = COLORS.green;

  const reviewHeaders = [
    "review_unit_id", "source_rank", "pilot_scope", "record_id", "partition", "queue_reason", "target_signal", "detected_signals", "text_excerpt", "evidence_context", "review_outcome", "missed_signal_type", "rationale", "reviewer", "reviewed_date", "completion_status",
  ];
  review.getRange("A10:P10").values = [reviewHeaders];
  const reviewRows = reviewUnits.map((unit) => [
    unit.review_unit_id,
    unit.source_rank,
    unit.pilot_scope,
    unit.record_id,
    unit.partition,
    unit.queue_reason,
    unit.target_signal,
    unit.detected_signals,
    unit.text_excerpt,
    unit.evidence_context,
    null,
    null,
    null,
    null,
    null,
    null,
  ]);
  review.getRangeByIndexes(reviewStartRow - 1, 0, reviewRows.length, reviewHeaders.length).values = reviewRows;
  const statusFormula = '=IF(K11="","CHƯA ĐÁNH GIÁ",IF(AND(G11<>"NO_SIGNAL_AUDIT",NOT(OR(K11="CORRECT",K11="INCORRECT",K11="UNCERTAIN"))),"OUTCOME KHÔNG HỢP LỆ",IF(AND(G11="NO_SIGNAL_AUDIT",NOT(OR(K11="NO_MISSED_SIGNAL",K11="MISSED_SIGNAL",K11="UNCERTAIN"))),"OUTCOME KHÔNG HỢP LỆ",IF(AND(K11="MISSED_SIGNAL",L11=""),"THIẾU LOẠI TÍN HIỆU",IF(AND(OR(K11="INCORRECT",K11="UNCERTAIN",K11="MISSED_SIGNAL"),M11=""),"THIẾU GIẢI THÍCH",IF(OR(N11="",O11=""),"THIẾU NGƯỜI/NGÀY","HOÀN TẤT"))))))';
  review.getRange("P11").formulas = [[statusFormula]];
  review.getRange(`P11:P${reviewEndRow}`).fillDown();
  const reviewTable = review.tables.add(`A10:P${reviewEndRow}`, true, "FinancialClaimsReviewUnits");
  reviewTable.style = "TableStyleMedium2";
  reviewTable.showBandedColumns = false;
  reviewTable.showFilterButton = true;
  styleSectionHeader(review.getRange("A10:P10"));
  styleBody(review.getRange(`A11:P${reviewEndRow}`));
  review.getRange(`A11:J${reviewEndRow}`).format.fill = COLORS.white;
  review.getRange(`K11:O${reviewEndRow}`).format.fill = COLORS.yellow;
  review.getRange(`P11:P${reviewEndRow}`).format.fill = COLORS.lightBlue;
  review.getRange(`I11:J${reviewEndRow}`).format.wrapText = true;
  review.getRange(`M11:M${reviewEndRow}`).format.wrapText = true;
  review.getRange(`A11:H${reviewEndRow}`).format.verticalAlignment = "top";
  review.getRange(`K11:P${reviewEndRow}`).format.verticalAlignment = "top";
  review.getRange(`B11:B${reviewEndRow}`).format.numberFormat = "#,##0";
  review.getRange(`O11:O${reviewEndRow}`).format.numberFormat = "yyyy-mm-dd";
  review.getRange(`K11:K${reviewEndRow}`).dataValidation = { rule: { type: "list", values: ["CORRECT", "INCORRECT", "UNCERTAIN", "NO_MISSED_SIGNAL", "MISSED_SIGNAL"] } };
  review.getRange(`L11:L${reviewEndRow}`).dataValidation = { rule: { type: "list", values: Object.keys(SIGNAL_LABELS) } };
  review.getRange(`C11:C${reviewEndRow}`).conditionalFormats.add("containsText", { text: "PILOT_20", format: { fill: COLORS.blue, font: { bold: true, color: COLORS.navy } } });
  review.getRange(`K11:K${reviewEndRow}`).conditionalFormats.add("containsText", { text: "INCORRECT", format: { fill: COLORS.red, font: { bold: true, color: COLORS.redText } } });
  review.getRange(`K11:K${reviewEndRow}`).conditionalFormats.add("containsText", { text: "MISSED_SIGNAL", format: { fill: COLORS.red, font: { bold: true, color: COLORS.redText } } });
  review.getRange(`K11:K${reviewEndRow}`).conditionalFormats.add("containsText", { text: "UNCERTAIN", format: { fill: "#FCE4D6", font: { bold: true, color: "#9C6500" } } });
  review.getRange(`K11:K${reviewEndRow}`).conditionalFormats.add("containsText", { text: "CORRECT", format: { fill: COLORS.green, font: { bold: true, color: COLORS.greenText } } });
  review.getRange(`P11:P${reviewEndRow}`).conditionalFormats.add("containsText", { text: "HOÀN TẤT", format: { fill: COLORS.green, font: { bold: true, color: COLORS.greenText } } });
  review.getRange(`P11:P${reviewEndRow}`).conditionalFormats.add("containsText", { text: "THIẾU", format: { fill: COLORS.red, font: { bold: true, color: COLORS.redText } } });
  review.getRange(`P11:P${reviewEndRow}`).conditionalFormats.add("containsText", { text: "KHÔNG HỢP LỆ", format: { fill: COLORS.red, font: { bold: true, color: COLORS.redText } } });
  review.freezePanes.freezeRows(10);
  review.freezePanes.freezeColumns(4);
  const reviewWidths = [22, 10, 12, 38, 12, 22, 34, 42, 65, 65, 22, 34, 45, 18, 14, 24];
  reviewWidths.forEach((width, index) => { review.getRange(`${colLetter(index)}:${colLetter(index)}`).format.columnWidth = width; });
  review.getRange(`A11:P${reviewEndRow}`).format.rowHeight = 58;
  review.getRange("A2:P7").format.rowHeight = 26;

  source.getRange("A2:I2").values = [["Nguồn review queue 120 record", null, null, null, null, null, null, null, null]];
  styleTitle(source, "A2:I2");
  source.getRange("A4:I4").values = [[`File: ${path.basename(args.queue)} | SHA-256: ${queueHash}`, null, null, null, null, null, null, null, null]];
  source.mergeCells("A4:I4");
  source.getRange("A4:I4").format = { fill: COLORS.lightBlue, font: { name: FONT, size: 9, color: COLORS.grayText }, wrapText: true };
  source.getRange("A5:I5").values = [["Sheet này giữ nguyên các trường nguồn để đối chiếu. Không nhập kết quả review tại đây.", null, null, null, null, null, null, null, null]];
  source.mergeCells("A5:I5");
  source.getRange("A5:I5").format = { fill: COLORS.gray, font: { name: FONT, size: 10, bold: true, color: COLORS.grayText } };
  const sourceHeaders = ["source_rank", "record_id", "partition", "split_group_id", "signal_types", "text_excerpt", "evidence_contexts", "queue_reason", "review_status"];
  source.getRange("A7:I7").values = [sourceHeaders];
  const sourceRows = records.map((row, index) => [
    index + 1,
    row.record_id,
    row.partition,
    row.split_group_id,
    (row.signal_types ?? []).join(", "),
    row.text_excerpt,
    (row.evidence_contexts ?? []).join(" || "),
    row.queue_reason,
    row.review_status,
  ]);
  const sourceStartRow = 8;
  const sourceEndRow = sourceStartRow + sourceRows.length - 1;
  source.getRangeByIndexes(sourceStartRow - 1, 0, sourceRows.length, sourceHeaders.length).values = sourceRows;
  const sourceTable = source.tables.add(`A7:I${sourceEndRow}`, true, "FinancialClaimsSourceQueue");
  sourceTable.style = "TableStyleMedium2";
  sourceTable.showFilterButton = true;
  styleSectionHeader(source.getRange("A7:I7"));
  styleBody(source.getRange(`A8:I${sourceEndRow}`));
  source.getRange(`E8:G${sourceEndRow}`).format.wrapText = true;
  source.getRange(`A8:I${sourceEndRow}`).format.rowHeight = 58;
  source.freezePanes.freezeRows(7);
  source.freezePanes.freezeColumns(2);
  const sourceWidths = [12, 42, 12, 25, 42, 70, 70, 22, 16];
  sourceWidths.forEach((width, index) => { source.getRange(`${colLetter(index)}:${colLetter(index)}`).format.columnWidth = width; });

  workbook.recalculate();

  // Prove that the completion gate reacts to valid, invalid, and incomplete inputs.
  review.getRange("K11").values = [["CORRECT"]];
  review.getRange("N11").values = [["QA"]];
  review.getRange("O11").values = [[new Date("2026-09-16T00:00:00Z")]];
  workbook.recalculate();
  if (review.getRange("P11").values[0][0] !== "HOÀN TẤT") throw new Error("Completion gate không hoàn tất candidate hợp lệ");
  review.getRange("K11").values = [["NO_MISSED_SIGNAL"]];
  workbook.recalculate();
  if (review.getRange("P11").values[0][0] !== "OUTCOME KHÔNG HỢP LỆ") throw new Error("Completion gate không chặn outcome sai loại");
  review.getRange("K11:O11").values = [[null, null, null, null, null]];

  const auditUnitIndex = reviewUnits.findIndex((unit) => unit.target_signal === "NO_SIGNAL_AUDIT");
  const auditRow = reviewStartRow + auditUnitIndex;
  review.getRange(`K${auditRow}`).values = [["MISSED_SIGNAL"]];
  review.getRange(`N${auditRow}`).values = [["QA"]];
  review.getRange(`O${auditRow}`).values = [[new Date("2026-09-16T00:00:00Z")]];
  workbook.recalculate();
  if (review.getRange(`P${auditRow}`).values[0][0] !== "THIẾU LOẠI TÍN HIỆU") throw new Error("Completion gate không yêu cầu missed_signal_type");
  review.getRange(`L${auditRow}`).values = [["RETURN_RATE"]];
  workbook.recalculate();
  if (review.getRange(`P${auditRow}`).values[0][0] !== "THIẾU GIẢI THÍCH") throw new Error("Completion gate không yêu cầu rationale");
  review.getRange(`M${auditRow}`).values = [["Kiểm thử workflow"]];
  workbook.recalculate();
  if (review.getRange(`P${auditRow}`).values[0][0] !== "HOÀN TẤT") throw new Error("Completion gate không hoàn tất no-signal audit hợp lệ");
  review.getRange(`K${auditRow}:O${auditRow}`).values = [[null, null, null, null, null]];
  workbook.recalculate();

  const overviewInspect = await workbook.inspect({ kind: "table", range: "Tong quan!A1:E37", include: "values,formulas", tableMaxRows: 40, tableMaxCols: 8, maxChars: 14000 });
  const reviewInspect = await workbook.inspect({ kind: "table", range: `Danh gia!A1:P${Math.min(reviewEndRow, 18)}`, include: "values,formulas", tableMaxRows: 20, tableMaxCols: 16, maxChars: 14000 });
  const errors = await workbook.inspect({ kind: "match", searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!", options: { useRegex: true, maxResults: 300 }, summary: "final formula error scan" });
  console.log(JSON.stringify({ queueHash, records: records.length, reviewUnits: reviewUnits.length, pilotUnits, candidateRecords, noSignalRecords }));
  console.log(overviewInspect.ndjson);
  console.log(reviewInspect.ndjson);
  console.log(errors.ndjson);

  await fs.mkdir(args.renderDir, { recursive: true });
  const renderSpecs = [
    ["Tong quan", "A1:E37", "tong_quan.png"],
    ["Danh gia", "A1:P35", "danh_gia_top.png"],
    ["Danh gia", `A${Math.max(1, reviewEndRow - 23)}:P${reviewEndRow}`, "danh_gia_tail.png"],
    ["Nguon 120", "A1:I25", "nguon_top.png"],
    ["Nguon 120", `A${Math.max(1, sourceEndRow - 15)}:I${sourceEndRow}`, "nguon_tail.png"],
  ];
  for (const [sheetName, range, filename] of renderSpecs) {
    const preview = await workbook.render({ sheetName, range, scale: 1, format: "png" });
    await fs.writeFile(path.join(args.renderDir, filename), new Uint8Array(await preview.arrayBuffer()));
  }

  if (args.output) {
    await fs.mkdir(path.dirname(args.output), { recursive: true });
    const output = await SpreadsheetFile.exportXlsx(workbook);
    await output.save(args.output);
    const savedWorkbook = await SpreadsheetFile.importXlsx(await FileBlob.load(args.output));
    const savedSummary = await savedWorkbook.inspect({ kind: "sheet,table", maxChars: 8000, tableMaxRows: 4, tableMaxCols: 6 });
    const savedErrors = await savedWorkbook.inspect({ kind: "match", searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!", options: { useRegex: true, maxResults: 300 }, summary: "saved workbook formula error scan" });
    console.log(savedSummary.ndjson);
    console.log(savedErrors.ndjson);
    console.log(JSON.stringify({ output: path.resolve(args.output) }));
  }
}

main().catch((error) => {
  console.error(error.stack ?? String(error));
  process.exitCode = 1;
});
