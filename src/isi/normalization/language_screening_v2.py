"""Corrected language and text-quality screening for offline HTML captures."""

from __future__ import annotations

import re
from collections import Counter

from src.isi.normalization.external_text import extract_visible_text
from src.isi.normalization.language_screening import (
    DeclaredLanguageParser,
    STOPWORDS,
    normalize_language_code,
)
from src.isi.normalization.wayback_external_text import decode_archived_payload


NON_DECISIVE_DECLARATIONS = {"mul", "und", "zxx"}


def screen_html_language_v2(raw: bytes) -> tuple[dict[str, object], str]:
    decoded, transport_decoding = decode_archived_payload(raw)
    html = decoded.decode("utf-8", errors="replace")
    parser = DeclaredLanguageParser()
    parser.feed(html)
    declared = list(
        dict.fromkeys(
            code for value in parser.values if (code := normalize_language_code(value)) is not None
        )
    )
    decisive_declared = [code for code in declared if code not in NON_DECISIVE_DECLARATIONS]
    text, _ = extract_visible_text(decoded)
    tokens = [token.casefold() for token in re.findall(r"[^\W\d_]{2,}", text, flags=re.UNICODE)]
    counts = Counter(tokens)
    scores = {
        language: sum(counts[word] for word in words)
        for language, words in STOPWORDS.items()
    }
    ranked = sorted(scores.items(), key=lambda item: (-item[1], item[0]))
    best_language, best_score = ranked[0]
    second_score = ranked[1][1]
    letters = [character for character in text if character.isalpha()]
    non_latin_ratio = (
        sum(ord(character) > 0x024F for character in letters) / len(letters)
        if letters
        else 0.0
    )
    replacement_ratio = text.count("\ufffd") / max(1, len(text))
    non_whitespace_characters = len(re.sub(r"\s+", "", text))

    if replacement_ratio >= 0.005:
        quality_state = "UNREADABLE_DECODING_OR_BINARY_PAYLOAD"
        quality_reasons = ["replacement_character_ratio_at_or_above_0_005"]
    elif len(tokens) < 50 or non_whitespace_characters < 200:
        quality_state = "INSUFFICIENT_VISIBLE_TEXT"
        quality_reasons = ["fewer_than_50_tokens_or_200_non_whitespace_characters"]
    else:
        quality_state = "REVIEWABLE_VISIBLE_TEXT"
        quality_reasons = []

    declared_primary = decisive_declared[0] if decisive_declared else None
    if quality_state != "REVIEWABLE_VISIBLE_TEXT":
        hint = declared_primary or (best_language if best_score else "undetermined")
        bucket = "MIXED_OR_UNDETERMINED"
        confidence = "NOT_APPLICABLE_TEXT_QUALITY_BLOCKED"
        reason = "text_quality_gate_failed_before_language_routing"
    elif declared_primary:
        hint = declared_primary
        bucket = "ENGLISH" if declared_primary == "en" else "NON_ENGLISH"
        confidence = "HIGH_FOR_ROUTING_ONLY"
        reason = "decisive_declared_html_or_meta_language"
    elif non_latin_ratio >= 0.08 and len(tokens) >= 20:
        hint = "non_latin_script"
        bucket = "NON_ENGLISH"
        confidence = "MEDIUM_FOR_ROUTING_ONLY"
        reason = "non_latin_letter_ratio"
    elif best_score >= 5 and best_score >= max(2 * second_score, second_score + 3):
        hint = best_language
        bucket = "ENGLISH" if best_language == "en" else "NON_ENGLISH"
        confidence = "MEDIUM_FOR_ROUTING_ONLY"
        reason = "transparent_stopword_margin"
    else:
        hint = best_language if best_score else "undetermined"
        bucket = "MIXED_OR_UNDETERMINED"
        confidence = "LOW"
        reason = "insufficient_or_ambiguous_language_signal"

    screening = {
        "screening_version": "language_screening_v2_corrected",
        "text_quality_state": quality_state,
        "text_quality_reasons": quality_reasons,
        "automatic_language_bucket": bucket,
        "automatic_language_hint": hint,
        "routing_confidence": confidence,
        "routing_reason": reason,
        "declared_language_codes": declared,
        "decisive_declared_language_codes": decisive_declared,
        "non_decisive_declared_language_codes": [
            code for code in declared if code in NON_DECISIVE_DECLARATIONS
        ],
        "stopword_scores": scores,
        "token_count": len(tokens),
        "visible_text_characters": len(text),
        "non_whitespace_text_characters": non_whitespace_characters,
        "replacement_character_ratio": round(replacement_ratio, 6),
        "non_latin_letter_ratio": round(non_latin_ratio, 6),
        "transport_decoding": transport_decoding,
        "manual_confirmation_required": quality_state == "REVIEWABLE_VISIBLE_TEXT",
        "ground_truth_label_created": False,
        "model_feature_allowed": False,
    }
    return screening, text
