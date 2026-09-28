"""Offline inspection of official warning HTML for preserved solicitation artifacts."""

from __future__ import annotations

import re
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlparse

from src.isi.normalization.external_text import extract_visible_text, identity_token_check, normalize_identity


DOCUMENT_EXTENSIONS = {".csv", ".doc", ".docx", ".pdf", ".ppt", ".pptx", ".txt", ".zip"}
MEDIA_EXTENSIONS = {".gif", ".jpeg", ".jpg", ".png", ".svg", ".webp"}
GENERIC_MEDIA_TOKENS = {
    "banner",
    "favicon",
    "footer",
    "header",
    "icon",
    "logo",
    "social",
    "sprite",
}


class AssetHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.links: list[str] = []
        self.media: list[dict[str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {key.casefold(): value for key, value in attrs if value is not None}
        lowered = tag.casefold()
        if lowered == "a" and values.get("href"):
            self.links.append(str(values["href"]))
        if lowered in {"img", "source", "video", "audio", "iframe", "object"}:
            source = values.get("src") or values.get("data") or values.get("srcset")
            if source:
                self.media.append(
                    {
                        "tag": lowered,
                        "source": str(source).split(",", 1)[0].strip().split(" ", 1)[0],
                        "alt": str(values.get("alt") or values.get("title") or ""),
                    }
                )


def _extension(url: str) -> str:
    path = urlparse(url).path.casefold()
    return Path(path).suffix


def _bounded_context(text: str, needles: list[str], *, radius: int = 140) -> list[str]:
    normalized = text.casefold()
    contexts = []
    for needle in needles:
        candidate = needle.casefold().strip()
        if not candidate:
            continue
        index = normalized.find(candidate)
        if index < 0:
            continue
        start = max(0, index - radius)
        end = min(len(text), index + len(candidate) + radius)
        contexts.append(re.sub(r"\s+", " ", text[start:end]).strip())
    return list(dict.fromkeys(contexts))[:5]


def analyze_warning_capture(
    *,
    candidate: dict[str, object],
    capture_path: Path,
) -> dict[str, object]:
    raw = capture_path.read_bytes()
    text, canonical_urls = extract_visible_text(raw)
    parser = AssetHTMLParser()
    parser.feed(raw.decode("utf-8", errors="replace"))
    notice_url = str(candidate["official_reference"]["url"])
    candidate_host = str(candidate["candidate_host"]).casefold().rstrip(".")
    entity_keys = [str(value) for value in candidate.get("entity_name_keys", [])]

    links = list(dict.fromkeys(urljoin(notice_url, value) for value in parser.links if value.strip()))
    media = [
        {
            **item,
            "url": urljoin(notice_url, item["source"]),
        }
        for item in parser.media
        if item["source"].strip() and not item["source"].casefold().startswith("data:")
    ]
    documents = [url for url in links if _extension(url) in DOCUMENT_EXTENSIONS]
    candidate_domain_links = [
        url
        for url in links
        if (urlparse(url).hostname or "").casefold().removeprefix("www.") == candidate_host.removeprefix("www.")
    ]

    identity_tokens = {
        token
        for entity in entity_keys
        for token in normalize_identity(entity).split()
        if len(token) >= 4
    }
    identity_tokens.update(
        token for token in re.split(r"[^a-z0-9]+", candidate_host.split(".", 1)[0]) if len(token) >= 4
    )
    relevant_documents = []
    for url in documents:
        parsed = urlparse(url)
        searchable = normalize_identity(f"{parsed.path} {parsed.query} {parsed.fragment}")
        tokens = set(searchable.split())
        if tokens.intersection(GENERIC_MEDIA_TOKENS):
            continue
        if tokens.intersection(identity_tokens):
            relevant_documents.append(url)

    relevant_media = []
    for item in media:
        parsed = urlparse(item["url"])
        searchable = normalize_identity(
            f"{parsed.path} {parsed.query} {parsed.fragment} {item['alt']}"
        )
        tokens = set(searchable.split())
        if tokens.intersection(GENERIC_MEDIA_TOKENS):
            continue
        if _extension(item["url"]) in MEDIA_EXTENSIONS and tokens.intersection(identity_tokens):
            relevant_media.append(item)

    normalized_text = normalize_identity(text)
    host_in_text = normalize_identity(candidate_host) in normalized_text
    identity = identity_token_check(entity_keys, text)
    contexts = _bounded_context(text, [candidate_host, *entity_keys])
    follow_up_assets = [
        {"type": "DOCUMENT", "url": value}
        for value in relevant_documents
    ] + [
        {"type": "MEDIA", "url": item["url"], "alt": item["alt"]}
        for item in relevant_media
    ]
    return {
        "candidate_id": candidate.get("candidate_id"),
        "candidate_host": candidate_host,
        "official_notice_url": notice_url,
        "capture_path": str(capture_path),
        "capture_bytes": len(raw),
        "visible_text_characters": len(text),
        "canonical_urls": canonical_urls,
        "candidate_host_in_visible_text": host_in_text,
        "identity_check": identity,
        "candidate_domain_link_count": len(candidate_domain_links),
        "candidate_domain_links": candidate_domain_links[:10],
        "document_attachment_count": len(documents),
        "document_attachments": documents[:20],
        "identity_relevant_document_count": len(relevant_documents),
        "identity_relevant_documents": relevant_documents[:20],
        "media_asset_count": len(media),
        "identity_relevant_media_count": len(relevant_media),
        "identity_relevant_media": relevant_media[:20],
        "bounded_identity_contexts": contexts,
        "follow_up_asset_count": len(follow_up_assets),
        "follow_up_assets": follow_up_assets[:20],
        "warning_page_as_model_input_allowed": False,
        "observed_solicitation_artifact_found": False,
        "interpretation": (
            "The official warning page is evidence only. A linked document or identity-relevant media asset "
            "is merely a follow-up candidate until inspected; no solicitation artifact is inferred from warning text."
        ),
    }
