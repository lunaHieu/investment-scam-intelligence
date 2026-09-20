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
  const result = {
    queue: DEFAULT_QUEUE,
    profile: DEFAULT_PROFILE,
    registry: DEFAULT_REGISTRY,
    features: null,
    aiSuggestions: null,
    humanReview: null,
    pilotRanks: "1-20",
    renderDir: null,
    output: null,
  };
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

function excelValue(value) {
  return typeof value === "string"
    ? value.replace(/[\u0000-\u0008\u000B\u000C\u000E-\u001F]/g, "�")
    : value;
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

function parsePilotRanks(value, recordCount) {
  const ranks = new Set();
  for (const token of String(value).split(",").map((item) => item.trim()).filter(Boolean)) {
    const rangeMatch = token.match(/^(\d+)-(\d+)$/);
    if (rangeMatch) {
      const start = Number(rangeMatch[1]);
      const end = Number(rangeMatch[2]);
      if (start > end) throw new Error(`Khoảng pilot không hợp lệ: ${token}`);
      for (let rank = start; rank <= end; rank += 1) ranks.add(rank);
    } else if (/^\d+$/.test(token)) {
      ranks.add(Number(token));
    } else {
      throw new Error(`pilot-ranks không hợp lệ: ${token}`);
    }
  }
  if (ranks.size === 0 || [...ranks].some((rank) => rank < 1 || rank > recordCount)) {
    throw new Error(`pilot-ranks phải nằm trong 1..${recordCount}`);
  }
  return ranks;
}

function buildReviewUnits(records, featureByRecordId, pilotRankSet, idPrefix, pilotScope, laterScope) {
  const units = [];
  records.forEach((record, index) => {
    const sourceRank = index + 1;
    const signals = Array.isArray(record.signal_types) ? record.signal_types : [];
    const targets = signals.length > 0 ? signals : ["NO_SIGNAL_AUDIT"];
    const featureRecord = featureByRecordId.get(record.record_id);
    targets.forEach((target, targetIndex) => {
      const targetContexts = target === "NO_SIGNAL_AUDIT"
        ? []
        : (featureRecord?.signals ?? []).filter((signal) => signal.signal_type === target).slice(0, 3).map((signal) => signal.context);
      units.push({
        review_unit_id: `${idPrefix}-${String(sourceRank).padStart(3, "0")}-${String(targetIndex + 1).padStart(2, "0")}`,
        source_rank: sourceRank,
        pilot_scope: pilotRankSet.has(sourceRank) ? pilotScope : laterScope,
        record_id: record.record_id,
        partition: record.partition,
        queue_reason: record.queue_reason,
        target_signal: target,
        detected_signals: signals.join(", "),
        text_excerpt: record.text_excerpt,
        evidence_context: targetContexts.join(" || "),
      });
    });
  });
  return units.sort((left, right) => {
    const leftPilot = left.pilot_scope === pilotScope ? 0 : 1;
    const rightPilot = right.pilot_scope === pilotScope ? 0 : 1;
    return leftPilot - rightPilot || left.source_rank - right.source_rank || left.review_unit_id.localeCompare(right.review_unit_id);
  });
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const [queueBuffer, profileText, registryText] = await Promise.all([
    fs.readFile(args.queue),
    fs.readFile(args.profile, "utf8"),
    fs.readFile(args.registry, "utf8"),
  ]);
  const aiSuggestionsBuffer = args.aiSuggestions ? await fs.readFile(args.aiSuggestions) : null;
  const humanReviewBuffer = args.humanReview ? await fs.readFile(args.humanReview) : null;
  const queueHash = sha256(queueBuffer);
  const aiSuggestionsHash = aiSuggestionsBuffer ? sha256(aiSuggestionsBuffer) : null;
  const humanReviewHash = humanReviewBuffer ? sha256(humanReviewBuffer) : null;
  const records = parseJsonl(queueBuffer.toString("utf8"));
  const profile = JSON.parse(profileText);
  const registry = JSON.parse(registryText);
  const featureArtifact = registry.artifacts.find((item) => item.role === "feature_records");
  const featuresPath = args.features ?? featureArtifact?.path;
  if (!featuresPath) throw new Error("Thiếu feature_records để lấy evidence theo target signal");
  const featuresBuffer = await fs.readFile(featuresPath);
  const featuresHash = sha256(featuresBuffer);
  if (featuresHash !== featureArtifact?.sha256) throw new Error("SHA-256 feature_records không khớp registry");
  const featureRecords = parseJsonl(featuresBuffer.toString("utf8"));
  const featureByRecordId = new Map(featureRecords.map((record) => [record.record_id, record]));
  const aiPackage = aiSuggestionsBuffer ? JSON.parse(aiSuggestionsBuffer.toString("utf8")) : null;
  const humanReviewPackage = humanReviewBuffer ? JSON.parse(humanReviewBuffer.toString("utf8")) : null;
  const expectedHash = registry.artifacts.find((item) => item.role === "review_queue")?.sha256;

  if (queueHash !== expectedHash) throw new Error(`SHA-256 review queue không khớp registry: ${queueHash} != ${expectedHash}`);
  if (records.length !== 120) throw new Error(`Review queue phải có 120 record, thực tế ${records.length}`);
  if (new Set(records.map((row) => row.record_id)).size !== 120) throw new Error("record_id trong review queue không duy nhất");
  if (new Set(records.map((row) => row.split_group_id)).size !== 120) throw new Error("split_group_id trong review queue không duy nhất");
  if (records.some((row) => row.review_status !== "UNREVIEWED")) throw new Error("Review queue nguồn không còn ở trạng thái UNREVIEWED hoàn toàn");
  if (records.some((row) => !featureByRecordId.has(row.record_id))) throw new Error("Feature records thiếu record trong review queue");

  const pilotRankSet = parsePilotRanks(args.pilotRanks, records.length);
  const pilotRecordCount = pilotRankSet.size;
  const pilotScope = `PILOT_${pilotRecordCount}`;
  const laterScope = `LATER_${records.length - pilotRecordCount}`;
  const versionMatch = String(profile.feature_version ?? "").match(/_V(\d+)$/);
  if (!versionMatch || registry.feature_set_id !== profile.feature_version) throw new Error("Feature version không khớp profile/registry");
  const versionNumber = versionMatch[1];
  const idPrefix = `FCV${versionNumber}`;
  const reviewUnits = buildReviewUnits(records, featureByRecordId, pilotRankSet, idPrefix, pilotScope, laterScope);
  const pilotUnits = reviewUnits.filter((unit) => unit.pilot_scope === pilotScope).length;
  const candidateRecords = records.filter((row) => row.queue_reason === "SIGNAL_CANDIDATE").length;
  const noSignalRecords = records.filter((row) => row.queue_reason === "NO_SIGNAL_AUDIT").length;
  if (candidateRecords !== 80 || noSignalRecords !== 40) throw new Error("Cơ cấu queue không còn là 80 candidate + 40 no-signal audit");

  const aiSuggestions = aiPackage?.suggestions ?? [];
  const aiCoverageFindings = aiPackage?.coverage_findings ?? [];
  const aiSuggestionById = new Map(aiSuggestions.map((item) => [item.review_unit_id, item]));
  if (aiSuggestions.length > 0) {
    const pilotIds = new Set(reviewUnits.filter((unit) => unit.pilot_scope === pilotScope).map((unit) => unit.review_unit_id));
    if (aiPackage.status !== "PROVISIONAL_AI_ASSISTANCE_ONLY" || aiPackage.not_human_labels !== true) {
      throw new Error("Gói AI phải được đánh dấu là gợi ý tạm thời, không phải nhãn người review");
    }
    if (aiSuggestions.length !== pilotUnits || aiSuggestionById.size !== pilotUnits) {
      throw new Error(`Gợi ý AI phải bao phủ đúng ${pilotUnits} review unit pilot và không trùng ID`);
    }
    for (const item of aiSuggestions) {
      if (!pilotIds.has(item.review_unit_id)) throw new Error(`Gợi ý AI ngoài pilot: ${item.review_unit_id}`);
      const unit = reviewUnits.find((candidate) => candidate.review_unit_id === item.review_unit_id);
      const allowedOutcomes = unit.target_signal === "NO_SIGNAL_AUDIT"
        ? ["NO_MISSED_SIGNAL", "MISSED_SIGNAL", "UNCERTAIN"]
        : ["CORRECT", "INCORRECT", "UNCERTAIN"];
      if (!allowedOutcomes.includes(item.ai_suggested_outcome)) {
        throw new Error(`Outcome AI không hợp lệ: ${item.review_unit_id}`);
      }
      if (!["HIGH", "MEDIUM", "LOW"].includes(item.ai_confidence)) {
        throw new Error(`Confidence AI không hợp lệ: ${item.review_unit_id}`);
      }
      if (typeof item.ai_rationale !== "string" || item.ai_rationale.trim().length < 12) {
        throw new Error(`Thiếu rationale AI đủ rõ: ${item.review_unit_id}`);
      }
    }
    for (const finding of aiCoverageFindings) {
      const recordRank = records.findIndex((record) => record.record_id === finding.record_id) + 1;
      if (!pilotRankSet.has(recordRank)) throw new Error(`Coverage finding ngoài pilot: ${finding.record_id}`);
      if (!Array.isArray(finding.potential_missed_signal_types) || finding.potential_missed_signal_types.some((signal) => !(signal in SIGNAL_LABELS))) {
        throw new Error(`Coverage finding có signal không hợp lệ: ${finding.record_id}`);
      }
      if (typeof finding.rationale !== "string" || finding.rationale.trim().length < 12) throw new Error(`Coverage finding thiếu rationale: ${finding.record_id}`);
    }
  }
  const aiCorrect = aiSuggestions.filter((item) => item.ai_suggested_outcome === "CORRECT").length;
  const aiIncorrect = aiSuggestions.filter((item) => item.ai_suggested_outcome === "INCORRECT").length;
  const aiNoMissed = aiSuggestions.filter((item) => item.ai_suggested_outcome === "NO_MISSED_SIGNAL").length;
  const aiMissed = aiSuggestions.filter((item) => item.ai_suggested_outcome === "MISSED_SIGNAL").length;
  const aiUncertain = aiSuggestions.filter((item) => item.ai_suggested_outcome === "UNCERTAIN").length;

  const humanDecisionById = new Map();
  if (humanReviewPackage) {
    if (aiSuggestions.length !== pilotUnits) throw new Error("Human confirmation cần đúng bộ gợi ý AI pilot");
    if (humanReviewPackage.review_mode !== "AI_ASSISTED_HUMAN_CONFIRMATION" || humanReviewPackage.independent_blind_review !== false) {
      throw new Error("Human confirmation phải ghi rõ đây là review có AI hỗ trợ, không phải blind review độc lập");
    }
    if (humanReviewPackage.action !== "ACCEPT_ALL_AI_SUGGESTIONS") {
      throw new Error("Builder hiện chỉ hỗ trợ gói xác nhận toàn bộ gợi ý AI với overrides tường minh");
    }
    const confirmedIds = humanReviewPackage.confirmed_review_unit_ids ?? [];
    const confirmedIdSet = new Set(confirmedIds);
    const pilotIds = reviewUnits.filter((unit) => unit.pilot_scope === pilotScope).map((unit) => unit.review_unit_id);
    if (confirmedIds.length !== pilotUnits || confirmedIdSet.size !== pilotUnits || pilotIds.some((id) => !confirmedIdSet.has(id))) {
      throw new Error(`Human confirmation phải bao phủ đúng toàn bộ review unit ${pilotScope}, không trùng hoặc thiếu ID`);
    }
    if (typeof humanReviewPackage.reviewer !== "string" || !humanReviewPackage.reviewer.trim()) throw new Error("Thiếu reviewer");
    if (!/^\d{4}-\d{2}-\d{2}$/.test(humanReviewPackage.reviewed_date ?? "")) throw new Error("reviewed_date phải theo YYYY-MM-DD");
    for (const reviewUnitId of confirmedIds) {
      const suggestion = aiSuggestionById.get(reviewUnitId);
      humanDecisionById.set(reviewUnitId, {
        review_outcome: suggestion.ai_suggested_outcome,
        missed_signal_type: suggestion.ai_missed_signal_type ?? null,
        rationale: ["CORRECT", "NO_MISSED_SIGNAL"].includes(suggestion.ai_suggested_outcome) ? null : `Xác nhận gợi ý AI: ${suggestion.ai_rationale}`,
        reviewer: humanReviewPackage.reviewer.trim(),
        reviewed_date: new Date(`${humanReviewPackage.reviewed_date}T00:00:00Z`),
      });
    }
    for (const override of humanReviewPackage.overrides ?? []) {
      if (!humanDecisionById.has(override.review_unit_id)) throw new Error(`Override ngoài pilot: ${override.review_unit_id}`);
      humanDecisionById.set(override.review_unit_id, {
        review_outcome: override.review_outcome,
        missed_signal_type: override.missed_signal_type ?? null,
        rationale: override.rationale ?? null,
        reviewer: humanReviewPackage.reviewer.trim(),
        reviewed_date: new Date(`${humanReviewPackage.reviewed_date}T00:00:00Z`),
      });
    }
  }
  const humanDecisionCount = humanDecisionById.size;

  const workbook = Workbook.create();
  const overview = workbook.worksheets.add("Tong quan");
  const review = workbook.worksheets.add("Danh gia");
  const source = workbook.worksheets.add("Nguon 120");
  overview.showGridLines = false;
  review.showGridLines = false;
  source.showGridLines = false;
  overview.tabColor = COLORS.navy;
  review.tabColor = "#5B9BD5";

  overview.getRange("A2:H2").values = [[`Financial Claims V${versionNumber} - kiểm tra thủ công`, null, null, null, null, null, null, null]];
  styleTitle(overview, "A2:H2");
  overview.getRange("A4:H4").values = [["Mục tiêu: xác nhận độ đúng của rule trên train/validation. Đây không phải nhãn scam và không dùng dữ liệu test.", null, null, null, null, null, null, null]];
  overview.getRange("A4:H4").format = { fill: COLORS.yellow, font: { name: FONT, size: 10, bold: true, color: COLORS.text }, wrapText: true };
  overview.getRange("A4:H4").format.rowHeight = 32;

  overview.getRange("A6:B6").values = [["Phạm vi", "Giá trị"]];
  styleSectionHeader(overview.getRange("A6:B6"));
  overview.getRange("A7:B14").values = [
    ["Record nguồn", records.length],
    ["Review unit", reviewUnits.length],
    ["Record pilot", pilotRecordCount],
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
    [`=COUNTIFS('Danh gia'!$S$${reviewStartRow}:$S$${reviewEndRow},"HOÀN TẤT")`],
    [`=${reviewUnits.length}-E7`],
    [`=COUNTIFS('Danh gia'!$C$${reviewStartRow}:$C$${reviewEndRow},"${pilotScope}",'Danh gia'!$S$${reviewStartRow}:$S$${reviewEndRow},"HOÀN TẤT")`],
    [`=${pilotUnits}`],
    [`=E7/${reviewUnits.length}`],
  ];
  styleBody(overview.getRange("D7:E11"));
  overview.getRange("D7:D11").format.font = { name: FONT, size: 10, bold: true, color: COLORS.text };
  overview.getRange("E7:E10").format.numberFormat = "#,##0";
  overview.getRange("E11").format.numberFormat = "0.0%";
  overview.getRange("E7:E11").format.fill = COLORS.green;
  overview.getRange("E7:E11").format.font = { name: FONT, size: 10, bold: true, color: COLORS.greenText };

  overview.getRange("G6:H6").values = [["Gợi ý AI pilot", "Giá trị"]];
  styleSectionHeader(overview.getRange("G6:H6"));
  overview.getRange("G7:G13").values = [
    ["Review unit có gợi ý"],
    ["AI đề xuất CORRECT"],
    ["AI đề xuất INCORRECT"],
    ["AI đề xuất NO_MISSED_SIGNAL"],
    ["AI đề xuất MISSED_SIGNAL"],
    ["AI đề xuất UNCERTAIN"],
    ["Quyết định người review"],
  ];
  overview.getRange("H7:H13").formulas = [
    [`=COUNTIFS('Danh gia'!$C$${reviewStartRow}:$C$${reviewEndRow},"${pilotScope}",'Danh gia'!$K$${reviewStartRow}:$K$${reviewEndRow},"<>")`],
    [`=COUNTIFS('Danh gia'!$C$${reviewStartRow}:$C$${reviewEndRow},"${pilotScope}",'Danh gia'!$K$${reviewStartRow}:$K$${reviewEndRow},"CORRECT")`],
    [`=COUNTIFS('Danh gia'!$C$${reviewStartRow}:$C$${reviewEndRow},"${pilotScope}",'Danh gia'!$K$${reviewStartRow}:$K$${reviewEndRow},"INCORRECT")`],
    [`=COUNTIFS('Danh gia'!$C$${reviewStartRow}:$C$${reviewEndRow},"${pilotScope}",'Danh gia'!$K$${reviewStartRow}:$K$${reviewEndRow},"NO_MISSED_SIGNAL")`],
    [`=COUNTIFS('Danh gia'!$C$${reviewStartRow}:$C$${reviewEndRow},"${pilotScope}",'Danh gia'!$K$${reviewStartRow}:$K$${reviewEndRow},"MISSED_SIGNAL")`],
    [`=COUNTIFS('Danh gia'!$C$${reviewStartRow}:$C$${reviewEndRow},"${pilotScope}",'Danh gia'!$K$${reviewStartRow}:$K$${reviewEndRow},"UNCERTAIN")`],
    [`=COUNTIFS('Danh gia'!$C$${reviewStartRow}:$C$${reviewEndRow},"${pilotScope}",'Danh gia'!$N$${reviewStartRow}:$N$${reviewEndRow},"<>")`],
  ];
  styleBody(overview.getRange("G7:H13"));
  overview.getRange("G7:G13").format.font = { name: FONT, size: 10, bold: true, color: COLORS.text };
  overview.getRange("H7:H13").format = {
    fill: COLORS.lightBlue,
    font: { name: FONT, size: 10, bold: true, color: COLORS.navy },
    horizontalAlignment: "right",
    numberFormat: "#,##0",
  };

  overview.getRange("A17:H17").values = [["Cách review", null, null, null, null, null, null, null]];
  overview.getRange("A17:H17").format = { fill: COLORS.blue, font: { name: FONT, size: 11, bold: true, color: COLORS.navy } };
  overview.getRange("A18:H23").values = [
    ["1", `Mở sheet Danh gia và lọc cột pilot_scope = ${pilotScope}.`, null, null, null, null, null, null],
    ["2", "Đọc text_excerpt và evidence_context. So sánh gợi ý AI với bằng chứng; gợi ý AI không phải nhãn và có thể sai.", null, null, null, null, null, null],
    ["3", "Tự chọn review_outcome: CORRECT, INCORRECT hoặc UNCERTAIN. Không đánh giá record có phải scam hay không.", null, null, null, null, null, null],
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
  overview.getRange("D27:E39").values = [
    ["Feature version", profile.feature_version],
    ["Queue file", path.basename(args.queue)],
    ["Queue SHA-256", queueHash],
    ["Rule set SHA-256", profile.rule_set_sha256],
    ["Queue trạng thái gốc", "UNREVIEWED"],
    ["AI suggestions file", args.aiSuggestions ? path.basename(args.aiSuggestions) : "Không cung cấp"],
    ["AI suggestions SHA-256", aiSuggestionsHash ?? "n.a."],
    ["AI suggestions status", aiSuggestions.length > 0 ? (humanReviewPackage ? "Đã được người dùng xác nhận trong pilot" : "PROVISIONAL - cần người review xác nhận") : "Không có"],
    ["Human review file", args.humanReview ? path.basename(args.humanReview) : "Không cung cấp"],
    ["Human review SHA-256", humanReviewHash ?? "n.a."],
    ["Review mode", humanReviewPackage ? "AI-assisted confirmation - không phải blind review" : "Chưa review"],
    ["Features file", path.basename(featuresPath)],
    ["Features SHA-256", featuresHash],
  ];
  styleBody(overview.getRange("D27:E39"));
  overview.getRange("D27:D39").format.font = { name: FONT, size: 10, bold: true, color: COLORS.text };
  overview.getRange("E29:E30").format.font = { name: "Consolas", size: 8, color: COLORS.grayText };
  overview.getRange("E33").format.font = { name: "Consolas", size: 8, color: COLORS.grayText };
  overview.getRange("E36").format.font = { name: "Consolas", size: 8, color: COLORS.grayText };
  overview.getRange("E39").format.font = { name: "Consolas", size: 8, color: COLORS.grayText };

  const overviewEndRow = aiCoverageFindings.length > 0 ? 58 + aiCoverageFindings.length : 54;
  overview.getRange(`A1:H${overviewEndRow}`).format.verticalAlignment = "center";
  overview.getRange("A:A").format.columnWidth = 33;
  overview.getRange("B:B").format.columnWidth = 68;
  overview.getRange("C:C").format.columnWidth = 8;
  overview.getRange("D:D").format.columnWidth = 25;
  overview.getRange("E:E").format.columnWidth = 52;
  overview.getRange("F:F").format.columnWidth = 3;
  overview.getRange("G:G").format.columnWidth = 30;
  overview.getRange("H:H").format.columnWidth = 16;
  overview.getRange("A18:H23").format.rowHeight = 30;

  overview.getRange("A40:D40").values = [[humanReviewPackage ? "Kết quả đã được người review xác nhận" : "Kết quả chờ người review xác nhận", null, null, null]];
  overview.getRange("A40:D40").format = { fill: COLORS.blue, font: { name: FONT, size: 11, bold: true, color: COLORS.navy } };
  overview.getRange("A41:D41").values = [["Signal ID", "Đã review", "Đúng", "Tỷ lệ đúng"]];
  styleSectionHeader(overview.getRange("A41:D41"));
  const pilotMetricStartRow = 42;
  const pilotMetricEndRow = pilotMetricStartRow + Object.keys(SIGNAL_LABELS).length - 1;
  overview.getRangeByIndexes(pilotMetricStartRow - 1, 0, Object.keys(SIGNAL_LABELS).length, 1).values = Object.keys(SIGNAL_LABELS).map((signal) => [signal]);
  overview.getRange(`B${pilotMetricStartRow}`).formulas = [[`=COUNTIFS('Danh gia'!$C$${reviewStartRow}:$C$${reviewEndRow},"${pilotScope}",'Danh gia'!$G$${reviewStartRow}:$G$${reviewEndRow},A${pilotMetricStartRow},'Danh gia'!$S$${reviewStartRow}:$S$${reviewEndRow},"HOÀN TẤT")`]];
  overview.getRange(`B${pilotMetricStartRow}:B${pilotMetricEndRow}`).fillDown();
  overview.getRange(`C${pilotMetricStartRow}`).formulas = [[`=COUNTIFS('Danh gia'!$C$${reviewStartRow}:$C$${reviewEndRow},"${pilotScope}",'Danh gia'!$G$${reviewStartRow}:$G$${reviewEndRow},A${pilotMetricStartRow},'Danh gia'!$N$${reviewStartRow}:$N$${reviewEndRow},"CORRECT")`]];
  overview.getRange(`C${pilotMetricStartRow}:C${pilotMetricEndRow}`).fillDown();
  overview.getRange(`D${pilotMetricStartRow}`).formulas = [[`=IF(B${pilotMetricStartRow}=0,"n.a.",C${pilotMetricStartRow}/B${pilotMetricStartRow})`]];
  overview.getRange(`D${pilotMetricStartRow}:D${pilotMetricEndRow}`).fillDown();
  styleBody(overview.getRange(`A${pilotMetricStartRow}:D${pilotMetricEndRow}`));
  overview.getRange(`A${pilotMetricStartRow}:A${pilotMetricEndRow}`).format.font = { name: FONT, size: 9, bold: true, color: COLORS.navy };
  overview.getRange(`B${pilotMetricStartRow}:C${pilotMetricEndRow}`).format.numberFormat = "#,##0";
  overview.getRange(`D${pilotMetricStartRow}:D${pilotMetricEndRow}`).format.numberFormat = "0.0%";
  overview.getRange(`A${pilotMetricStartRow}:D${pilotMetricEndRow}`).format.borders = { bottom: { style: "thin", color: "#D9E2F3" } };
  const pilotInterpretation = humanReviewPackage
    ? `Kết quả này mô tả ${pilotUnits} review unit trong ${pilotRecordCount} record pilot được người dùng xác nhận theo quy trình có AI hỗ trợ. Đây không phải blind review; không dùng làm recall hoặc độ chính xác model.`
    : `Kết quả này chỉ mô tả ${pilotUnits} review unit trong ${pilotRecordCount} record pilot được chọn có chủ đích. Gợi ý AI chưa phải xác nhận của người review. Không dùng làm recall hoặc độ chính xác model.`;
  overview.getRange("A54:H54").values = [[pilotInterpretation, null, null, null, null, null, null, null]];
  overview.getRange("A54:H54").format = { fill: COLORS.yellow, font: { name: FONT, size: 10, color: COLORS.text }, wrapText: true };
  overview.getRange("A54:H54").format.rowHeight = 32;

  if (aiCoverageFindings.length > 0) {
    overview.getRange("A57:E57").values = [["Dấu hiệu có thể bị bỏ sót trong pilot", null, null, null, null]];
    overview.getRange("A57:E57").format = { fill: COLORS.blue, font: { name: FONT, size: 11, bold: true, color: COLORS.navy } };
    overview.getRange("A58:E58").values = [["record_id", "Tín hiệu có thể thiếu", null, "Confidence", "Giải thích AI"]];
    styleSectionHeader(overview.getRange("A58:B58"));
    styleSectionHeader(overview.getRange("D58:E58"));
    const coverageRows = aiCoverageFindings.map((finding) => [
      finding.record_id,
      finding.potential_missed_signal_types.join(", "),
      null,
      finding.ai_confidence,
      finding.rationale,
    ].map(excelValue));
    overview.getRangeByIndexes(58, 0, coverageRows.length, 5).values = coverageRows;
    styleBody(overview.getRange(`A59:B${58 + coverageRows.length}`));
    styleBody(overview.getRange(`D59:E${58 + coverageRows.length}`));
    overview.getRange(`A59:B${58 + coverageRows.length}`).format.wrapText = true;
    overview.getRange(`D59:E${58 + coverageRows.length}`).format.wrapText = true;
    overview.getRange(`A59:E${58 + coverageRows.length}`).format.rowHeight = 42;
  }

  review.getRange("A2:S2").values = [[`Đánh giá rule - ${reviewUnits.length} review unit từ ${records.length} record`, null, null, null, null, null, null, null, null, null, null, null, null, null, null, null, null, null, null]];
  styleTitle(review, "A2:S2");
  review.getRange("A4:S4").values = [[`Bắt đầu bằng ${pilotUnits} review unit thuộc ${pilotRecordCount} record ${pilotScope}. Cột xanh nhạt là gợi ý AI; chỉ nhập quyết định người review vào các cột màu vàng.`, null, null, null, null, null, null, null, null, null, null, null, null, null, null, null, null, null, null]];
  review.mergeCells("A4:S4");
  review.getRange("A4:S4").format = { fill: COLORS.yellow, font: { name: FONT, size: 10, bold: true, color: COLORS.text }, wrapText: true };
  review.getRange("A5:S5").values = [[humanReviewPackage
    ? "Pilot đã được người dùng xác nhận theo quy trình có AI hỗ trợ. Đây không phải blind review độc lập; test và training gate vẫn đóng."
    : "Gợi ý AI không phải nhãn và không làm thay đổi completion_status. Hãy kiểm tra bằng chứng rồi tự chọn review_outcome.", null, null, null, null, null, null, null, null, null, null, null, null, null, null, null, null, null, null]];
  review.mergeCells("A5:S5");
  review.getRange("A5:S5").format = { fill: COLORS.lightBlue, font: { name: FONT, size: 10, color: COLORS.text }, wrapText: true };
  review.getRange("A7:S7").values = [["Loại trường", null, null, null, null, null, null, null, null, null, "Gợi ý AI", "Gợi ý AI", "Gợi ý AI", "Người review nhập", "Người review nhập", "Người review nhập", "Người review nhập", "Người review nhập", "Tự tính"]];
  review.getRange("A7:S7").format = { font: { name: FONT, size: 9, italic: true, color: COLORS.grayText } };
  review.getRange("K7:M7").format.fill = COLORS.lightBlue;
  review.getRange("N7:R7").format.fill = COLORS.yellow;
  review.getRange("S7").format.fill = COLORS.green;

  const reviewHeaders = [
    "review_unit_id", "source_rank", "pilot_scope", "record_id", "partition", "queue_reason", "target_signal", "detected_signals", "text_excerpt", "evidence_context", "ai_suggested_outcome", "ai_confidence", "ai_rationale", "review_outcome", "missed_signal_type", "rationale", "reviewer", "reviewed_date", "completion_status",
  ];
  review.getRange("A10:S10").values = [reviewHeaders];
  const reviewRows = reviewUnits.map((unit) => {
    const suggestion = aiSuggestionById.get(unit.review_unit_id);
    const humanDecision = humanDecisionById.get(unit.review_unit_id);
    return [
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
      suggestion?.ai_suggested_outcome ?? null,
      suggestion?.ai_confidence ?? null,
      suggestion?.ai_rationale ?? null,
      humanDecision?.review_outcome ?? null,
      humanDecision?.missed_signal_type ?? null,
      humanDecision?.rationale ?? null,
      humanDecision?.reviewer ?? null,
      humanDecision?.reviewed_date ?? null,
      null,
    ].map(excelValue);
  });
  review.getRangeByIndexes(reviewStartRow - 1, 0, reviewRows.length, reviewHeaders.length).values = reviewRows;
  const statusFormula = '=IF(N11="","CHƯA ĐÁNH GIÁ",IF(AND(G11<>"NO_SIGNAL_AUDIT",NOT(OR(N11="CORRECT",N11="INCORRECT",N11="UNCERTAIN"))),"OUTCOME KHÔNG HỢP LỆ",IF(AND(G11="NO_SIGNAL_AUDIT",NOT(OR(N11="NO_MISSED_SIGNAL",N11="MISSED_SIGNAL",N11="UNCERTAIN"))),"OUTCOME KHÔNG HỢP LỆ",IF(AND(N11="MISSED_SIGNAL",O11=""),"THIẾU LOẠI TÍN HIỆU",IF(AND(OR(N11="INCORRECT",N11="UNCERTAIN",N11="MISSED_SIGNAL"),P11=""),"THIẾU GIẢI THÍCH",IF(OR(Q11="",R11=""),"THIẾU NGƯỜI/NGÀY","HOÀN TẤT"))))))';
  review.getRange("S11").formulas = [[statusFormula]];
  review.getRange(`S11:S${reviewEndRow}`).fillDown();
  const reviewTable = review.tables.add(`A10:S${reviewEndRow}`, true, "FinancialClaimsReviewUnits");
  reviewTable.style = "TableStyleMedium2";
  reviewTable.showBandedColumns = false;
  reviewTable.showFilterButton = true;
  styleSectionHeader(review.getRange("A10:S10"));
  styleBody(review.getRange(`A11:S${reviewEndRow}`));
  review.getRange(`A11:J${reviewEndRow}`).format.fill = COLORS.white;
  review.getRange(`K11:M${reviewEndRow}`).format.fill = COLORS.lightBlue;
  review.getRange(`N11:R${reviewEndRow}`).format.fill = COLORS.yellow;
  review.getRange(`S11:S${reviewEndRow}`).format.fill = COLORS.lightBlue;
  review.getRange(`I11:J${reviewEndRow}`).format.wrapText = true;
  review.getRange(`M11:M${reviewEndRow}`).format.wrapText = true;
  review.getRange(`P11:P${reviewEndRow}`).format.wrapText = true;
  review.getRange(`A11:H${reviewEndRow}`).format.verticalAlignment = "top";
  review.getRange(`K11:S${reviewEndRow}`).format.verticalAlignment = "top";
  review.getRange(`B11:B${reviewEndRow}`).format.numberFormat = "#,##0";
  review.getRange(`R11:R${reviewEndRow}`).format.numberFormat = "yyyy-mm-dd";
  review.getRange(`N11:N${reviewEndRow}`).dataValidation = { rule: { type: "list", values: ["CORRECT", "INCORRECT", "UNCERTAIN", "NO_MISSED_SIGNAL", "MISSED_SIGNAL"] } };
  review.getRange(`O11:O${reviewEndRow}`).dataValidation = { rule: { type: "list", values: Object.keys(SIGNAL_LABELS) } };
  review.getRange(`C11:C${reviewEndRow}`).conditionalFormats.add("containsText", { text: pilotScope, format: { fill: COLORS.blue, font: { bold: true, color: COLORS.navy } } });
  review.getRange(`K11:K${reviewEndRow}`).conditionalFormats.add("containsText", { text: "INCORRECT", format: { fill: "#FCE4D6", font: { bold: true, color: COLORS.redText } } });
  review.getRange(`K11:K${reviewEndRow}`).conditionalFormats.add("containsText", { text: "UNCERTAIN", format: { fill: COLORS.gray, font: { bold: true, color: COLORS.grayText } } });
  review.getRange(`K11:K${reviewEndRow}`).conditionalFormats.add("containsText", { text: "CORRECT", format: { fill: COLORS.blue, font: { bold: true, color: COLORS.navy } } });
  review.getRange(`K11:K${reviewEndRow}`).conditionalFormats.add("containsText", { text: "NO_MISSED_SIGNAL", format: { fill: COLORS.blue, font: { bold: true, color: COLORS.navy } } });
  review.getRange(`K11:K${reviewEndRow}`).conditionalFormats.add("containsText", { text: "MISSED_SIGNAL", format: { fill: COLORS.red, font: { bold: true, color: COLORS.redText } } });
  review.getRange(`L11:L${reviewEndRow}`).conditionalFormats.add("containsText", { text: "MEDIUM", format: { fill: "#FFF2CC", font: { bold: true, color: "#9C6500" } } });
  review.getRange(`L11:L${reviewEndRow}`).conditionalFormats.add("containsText", { text: "LOW", format: { fill: COLORS.red, font: { bold: true, color: COLORS.redText } } });
  review.getRange(`N11:N${reviewEndRow}`).conditionalFormats.add("containsText", { text: "INCORRECT", format: { fill: COLORS.red, font: { bold: true, color: COLORS.redText } } });
  review.getRange(`N11:N${reviewEndRow}`).conditionalFormats.add("containsText", { text: "MISSED_SIGNAL", format: { fill: COLORS.red, font: { bold: true, color: COLORS.redText } } });
  review.getRange(`N11:N${reviewEndRow}`).conditionalFormats.add("containsText", { text: "UNCERTAIN", format: { fill: "#FCE4D6", font: { bold: true, color: "#9C6500" } } });
  review.getRange(`N11:N${reviewEndRow}`).conditionalFormats.add("containsText", { text: "CORRECT", format: { fill: COLORS.green, font: { bold: true, color: COLORS.greenText } } });
  review.getRange(`S11:S${reviewEndRow}`).conditionalFormats.add("containsText", { text: "HOÀN TẤT", format: { fill: COLORS.green, font: { bold: true, color: COLORS.greenText } } });
  review.getRange(`S11:S${reviewEndRow}`).conditionalFormats.add("containsText", { text: "THIẾU", format: { fill: COLORS.red, font: { bold: true, color: COLORS.redText } } });
  review.getRange(`S11:S${reviewEndRow}`).conditionalFormats.add("containsText", { text: "KHÔNG HỢP LỆ", format: { fill: COLORS.red, font: { bold: true, color: COLORS.redText } } });
  review.freezePanes.freezeRows(10);
  review.freezePanes.freezeColumns(4);
  const reviewWidths = [22, 10, 12, 38, 12, 22, 34, 42, 60, 60, 22, 14, 48, 22, 34, 42, 18, 14, 24];
  reviewWidths.forEach((width, index) => { review.getRange(`${colLetter(index)}:${colLetter(index)}`).format.columnWidth = width; });
  review.getRange(`A11:S${reviewEndRow}`).format.rowHeight = 64;
  review.getRange("A2:S7").format.rowHeight = 26;

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
  ].map(excelValue));
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
  const candidateTestIndex = reviewUnits.findIndex((unit) => unit.pilot_scope === laterScope && unit.target_signal !== "NO_SIGNAL_AUDIT");
  const candidateTestRow = reviewStartRow + candidateTestIndex;
  review.getRange(`N${candidateTestRow}`).values = [["CORRECT"]];
  review.getRange(`Q${candidateTestRow}`).values = [["QA"]];
  review.getRange(`R${candidateTestRow}`).values = [[new Date("2026-09-16T00:00:00Z")]];
  workbook.recalculate();
  if (review.getRange(`S${candidateTestRow}`).values[0][0] !== "HOÀN TẤT") throw new Error("Completion gate không hoàn tất candidate hợp lệ");
  review.getRange(`N${candidateTestRow}`).values = [["NO_MISSED_SIGNAL"]];
  workbook.recalculate();
  if (review.getRange(`S${candidateTestRow}`).values[0][0] !== "OUTCOME KHÔNG HỢP LỆ") throw new Error("Completion gate không chặn outcome sai loại");
  review.getRange(`N${candidateTestRow}:R${candidateTestRow}`).values = [[null, null, null, null, null]];

  const auditUnitIndex = reviewUnits.findIndex((unit) => unit.pilot_scope === laterScope && unit.target_signal === "NO_SIGNAL_AUDIT");
  const auditRow = reviewStartRow + auditUnitIndex;
  review.getRange(`N${auditRow}`).values = [["MISSED_SIGNAL"]];
  review.getRange(`Q${auditRow}`).values = [["QA"]];
  review.getRange(`R${auditRow}`).values = [[new Date("2026-09-16T00:00:00Z")]];
  workbook.recalculate();
  if (review.getRange(`S${auditRow}`).values[0][0] !== "THIẾU LOẠI TÍN HIỆU") throw new Error("Completion gate không yêu cầu missed_signal_type");
  review.getRange(`O${auditRow}`).values = [["RETURN_RATE"]];
  workbook.recalculate();
  if (review.getRange(`S${auditRow}`).values[0][0] !== "THIẾU GIẢI THÍCH") throw new Error("Completion gate không yêu cầu rationale");
  review.getRange(`P${auditRow}`).values = [["Kiểm thử workflow"]];
  workbook.recalculate();
  if (review.getRange(`S${auditRow}`).values[0][0] !== "HOÀN TẤT") throw new Error("Completion gate không hoàn tất no-signal audit hợp lệ");
  review.getRange(`N${auditRow}:R${auditRow}`).values = [[null, null, null, null, null]];
  const pilotAuditUnitIndex = reviewUnits.findIndex((unit) => unit.pilot_scope === pilotScope && unit.target_signal === "NO_SIGNAL_AUDIT");
  const pilotAuditRow = pilotAuditUnitIndex >= 0 ? reviewStartRow + pilotAuditUnitIndex : auditRow;
  workbook.recalculate();

  const aiPilotRows = review.getRange(`K${reviewStartRow}:M${reviewStartRow + pilotUnits - 1}`).values;
  const aiLaterRows = review.getRange(`K${reviewStartRow + pilotUnits}:M${reviewEndRow}`).values;
  const humanPilotRows = review.getRange(`N${reviewStartRow}:R${reviewStartRow + pilotUnits - 1}`).values;
  const humanLaterRows = review.getRange(`N${reviewStartRow + pilotUnits}:R${reviewEndRow}`).values;
  const pilotStatusRows = review.getRange(`S${reviewStartRow}:S${reviewStartRow + pilotUnits - 1}`).values;
  const laterStatusRows = review.getRange(`S${reviewStartRow + pilotUnits}:S${reviewEndRow}`).values;
  if (aiSuggestions.length > 0 && aiPilotRows.some((row) => row.some((value) => value === null || value === ""))) {
    throw new Error("Gợi ý AI pilot chưa được điền đủ outcome, confidence và rationale");
  }
  if (aiLaterRows.some((row) => row.some((value) => value !== null && value !== ""))) {
    throw new Error(`Gợi ý AI đã vượt khỏi phạm vi ${pilotScope}`);
  }
  if (humanLaterRows.some((row) => row.some((value) => value !== null && value !== ""))) {
    throw new Error("Cột quyết định người review ngoài pilot không còn trống sau kiểm thử");
  }
  if (humanReviewPackage) {
    if (humanPilotRows.some((row) => !row[0] || !row[3] || !row[4])) throw new Error("Human confirmation chưa điền đủ outcome, reviewer hoặc ngày");
    if (pilotStatusRows.some((row) => row[0] !== "HOÀN TẤT")) throw new Error("Pilot đã xác nhận nhưng chưa hoàn tất toàn bộ");
  } else {
    if (humanPilotRows.some((row) => row.some((value) => value !== null && value !== ""))) throw new Error("Cột human pilot phải trống khi chưa có confirmation");
    if (pilotStatusRows.some((row) => row[0] !== "CHƯA ĐÁNH GIÁ")) throw new Error("Gợi ý AI không được tự làm hoàn tất pilot");
  }
  if (laterStatusRows.some((row) => row[0] !== "CHƯA ĐÁNH GIÁ")) throw new Error("Review ngoài pilot phải giữ CHƯA ĐÁNH GIÁ");
  if (overview.getRange("H7:H13").values.map((row) => row[0]).join(",") !== `${aiSuggestions.length},${aiCorrect},${aiIncorrect},${aiNoMissed},${aiMissed},${aiUncertain},${humanDecisionCount}`) {
    throw new Error("Tổng hợp gợi ý AI hoặc quyết định người review không khớp");
  }
  const pilotMetricValues = overview.getRange(`B${pilotMetricStartRow}:C${pilotMetricEndRow}`).values;
  const pilotMetricReviewed = pilotMetricValues.reduce((sum, row) => sum + Number(row[0] ?? 0), 0);
  const pilotMetricCorrect = pilotMetricValues.reduce((sum, row) => sum + Number(row[1] ?? 0), 0);
  const humanSignalDecisionCount = reviewUnits.filter((unit) => unit.target_signal !== "NO_SIGNAL_AUDIT" && humanDecisionById.has(unit.review_unit_id)).length;
  if (pilotMetricReviewed !== humanSignalDecisionCount || pilotMetricCorrect !== (humanReviewPackage ? aiCorrect : 0)) {
    throw new Error("Bảng kết quả pilot không khớp quyết định đã ghi nhận");
  }

  const overviewInspect = await workbook.inspect({ kind: "table", range: `Tong quan!A1:H${overviewEndRow}`, include: "values,formulas", tableMaxRows: 80, tableMaxCols: 8, maxChars: 24000 });
  const aiOverviewInspect = await workbook.inspect({ kind: "table", range: "Tong quan!G6:H13", include: "values,formulas", tableMaxRows: 12, tableMaxCols: 4, maxChars: 5000 });
  const reviewInspect = await workbook.inspect({ kind: "table", range: `Danh gia!A1:S${Math.min(reviewEndRow, 18)}`, include: "values,formulas", tableMaxRows: 20, tableMaxCols: 19, maxChars: 18000 });
  const errors = await workbook.inspect({ kind: "match", searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!", options: { useRegex: true, maxResults: 300 }, summary: "final formula error scan" });
  console.log(JSON.stringify({ queueHash, records: records.length, reviewUnits: reviewUnits.length, pilotRecordCount, pilotUnits, pilotScope, candidateRecords, noSignalRecords, aiSuggestions: aiSuggestions.length, aiCorrect, aiIncorrect, aiNoMissed, aiMissed, aiUncertain, aiCoverageFindings: aiCoverageFindings.length, humanDecisionCount, reviewMode: humanReviewPackage?.review_mode ?? null }));
  console.log(overviewInspect.ndjson);
  console.log(aiOverviewInspect.ndjson);
  console.log(reviewInspect.ndjson);
  console.log(errors.ndjson);

  await fs.mkdir(args.renderDir, { recursive: true });
  const renderSpecs = [
    ["Tong quan", `A1:H${overviewEndRow}`, "tong_quan.png"],
    ["Danh gia", "A1:S35", "danh_gia_top.png"],
    ["Danh gia", "I1:S25", "danh_gia_ai_review.png"],
    ["Danh gia", `I${Math.max(1, pilotAuditRow - 3)}:S${Math.min(reviewEndRow, pilotAuditRow + 11)}`, "danh_gia_no_signal_pilot.png"],
    ["Danh gia", `A${Math.max(1, reviewEndRow - 23)}:S${reviewEndRow}`, "danh_gia_tail.png"],
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
