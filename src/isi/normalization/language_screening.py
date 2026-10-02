"""Transparent language screening for offline HTML captures.

The result is routing metadata for manual confirmation.  It is deliberately
not a ground-truth label and is not suitable as a model feature.
"""

from __future__ import annotations

import re
from collections import Counter
from html.parser import HTMLParser

from src.isi.normalization.external_text import extract_visible_text
from src.isi.normalization.wayback_external_text import decode_archived_payload


STOPWORDS = {
    "en": {"and", "are", "for", "from", "has", "have", "investment", "is", "of", "our", "the", "this", "to", "we", "with", "you", "your"},
    "es": {"con", "de", "del", "el", "en", "es", "inversion", "la", "las", "los", "para", "por", "que", "su", "una", "y"},
    "fr": {"avec", "ce", "de", "des", "du", "en", "est", "et", "investissement", "la", "le", "les", "notre", "pour", "que", "un", "une", "vous"},
    "de": {"das", "der", "die", "ein", "eine", "für", "ist", "mit", "sie", "und", "unser", "von", "wir", "zu"},
    "it": {"che", "con", "dei", "del", "della", "di", "e", "gli", "il", "investimento", "la", "le", "per", "un", "una"},
    "nl": {"beleggen", "de", "een", "en", "het", "investering", "is", "met", "naar", "onze", "voor", "van", "wij", "zijn"},
    "pt": {"com", "da", "de", "do", "e", "em", "investimento", "o", "os", "para", "por", "que", "sua", "um", "uma"},
}


class DeclaredLanguageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.values: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {key.casefold(): value for key, value in attrs if value is not None}
        if tag.casefold() == "html" and values.get("lang"):
            self.values.append(str(values["lang"]))
        if tag.casefold() != "meta":
            return
        key = str(values.get("http-equiv") or values.get("name") or "").casefold()
        if key in {"content-language", "language"} and values.get("content"):
            self.values.append(str(values["content"]))


def normalize_language_code(value: str) -> str | None:
    match = re.match(r"\s*([a-zA-Z]{2,3})(?:[-_][a-zA-Z0-9]+)?", value)
    return match.group(1).casefold() if match else None


def screen_html_language(raw: bytes) -> tuple[dict[str, object], str]:
    decoded, transport_decoding = decode_archived_payload(raw)
    html = decoded.decode("utf-8", errors="replace")
    parser = DeclaredLanguageParser()
    parser.feed(html)
    declared = list(
        dict.fromkeys(
            code for value in parser.values if (code := normalize_language_code(value)) is not None
        )
    )
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

    declared_primary = declared[0] if declared else None
    if declared_primary:
        hint = declared_primary
        bucket = "ENGLISH" if declared_primary == "en" else "NON_ENGLISH"
        confidence = "HIGH_FOR_ROUTING_ONLY"
        reason = "declared_html_or_meta_language"
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
        "automatic_language_bucket": bucket,
        "automatic_language_hint": hint,
        "routing_confidence": confidence,
        "routing_reason": reason,
        "declared_language_codes": declared,
        "stopword_scores": scores,
        "token_count": len(tokens),
        "visible_text_characters": len(text),
        "non_latin_letter_ratio": round(non_latin_ratio, 6),
        "transport_decoding": transport_decoding,
        "manual_confirmation_required": True,
        "ground_truth_label_created": False,
        "model_feature_allowed": False,
    }
    return screening, text
