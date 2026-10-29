"""Bounded production HTTP transport, hard-disabled by execution preflight."""

from __future__ import annotations

import argparse
import json
import urllib.error
import urllib.parse
import urllib.request
from email.message import Message
from typing import BinaryIO, Mapping

from scripts.execute_target_text_corpus_v1_parser_bound_content_v1 import (
    TransportResponse,
    execution_preflight,
)
from scripts.verify_target_text_corpus_v1_parser_bound_content_release_v1 import (
    RELEASE,
)


REDIRECT_STATUSES = {301, 302, 303, 307, 308}
_LIVE_CAPABILITY = object()


class NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, file_pointer, code, message, headers, new_url):
        return None


def _contract() -> dict:
    return json.loads(RELEASE.read_text(encoding="utf-8"))["http_transport_contract"]


def authorize_live_transport() -> object:
    """Return an unforgeable in-process token only after every gate is open."""

    preflight = execution_preflight()
    if preflight["execution_allowed"] is not True:
        raise PermissionError("Live HTTP transport is closed by execution preflight")
    return _LIVE_CAPABILITY


def _headers_dict(headers: Mapping[str, str] | Message) -> dict[str, str]:
    return {str(key):str(value) for key, value in headers.items()}


def _read_bounded(stream: BinaryIO, maximum_bytes: int, chunk_bytes: int) -> bytes:
    chunks: list[bytes] = []
    remaining = maximum_bytes + 1
    while remaining > 0:
        chunk = stream.read(min(chunk_bytes, remaining))
        if not chunk:
            break
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


def _validate_redirect(resource: dict, current_url: str, location: str, redirects: int) -> str:
    maximum = int(resource.get("maximum_redirects", 0))
    if redirects >= maximum:
        raise ValueError("Redirect is not permitted for this resource")
    target = urllib.parse.urljoin(current_url, location)
    parsed = urllib.parse.urlparse(target)
    if parsed.scheme != "https" or parsed.hostname != "huggingface.co" or parsed.username or parsed.password or parsed.fragment:
        raise ValueError("Redirect target is outside the exact HTTPS authority")
    required = resource.get("required_final_url_contains")
    if not required or required not in target:
        raise ValueError("Redirect target lacks the immutable revision identity")
    return target


def fetch_with_injected_opener(
    resource: dict,
    opener,
    *,
    timeout_seconds: int | None = None,
) -> TransportResponse:
    """Fetch through an explicitly injected opener; used for deterministic tests."""

    contract = _contract()
    timeout = int(timeout_seconds or contract["timeout_seconds"])
    chunk_bytes = int(contract["read_chunk_bytes"])
    current = resource["url"]
    redirects = 0
    while True:
        request = urllib.request.Request(
            current,
            method="GET",
            headers={
                "User-Agent":contract["descriptive_user_agent"],
                "Accept":", ".join(resource["content_types"]),
            },
        )
        try:
            response = opener.open(request, timeout=timeout)
        except urllib.error.HTTPError as error:
            if error.code in REDIRECT_STATUSES:
                location = error.headers.get("Location")
                if not location:
                    raise ValueError("Redirect response lacks Location") from error
                current = _validate_redirect(resource, current, location, redirects)
                redirects += 1
                continue
            return TransportResponse(
                status_code=int(error.code),
                final_url=current,
                headers=_headers_dict(error.headers),
                body=b"",
                redirect_count=redirects,
            )
        with response:
            body = _read_bounded(response, int(resource["maximum_bytes"]), chunk_bytes)
            status = int(getattr(response, "status", response.getcode()))
            headers = _headers_dict(response.headers)
        return TransportResponse(
            status_code=status,
            final_url=current,
            headers=headers,
            body=body,
            redirect_count=redirects,
        )


def live_transport(resource: dict, capability: object) -> TransportResponse:
    """The only real-opener path; capability is unavailable while this release is local."""

    if capability is not _LIVE_CAPABILITY:
        raise PermissionError("Missing live HTTP transport capability")
    opener = urllib.request.build_opener(NoRedirectHandler())
    return fetch_with_injected_opener(resource, opener)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    if not args.verify_only:
        raise PermissionError("This module has no standalone live-execution command")
    preflight = execution_preflight()
    print(json.dumps({
        "status":"PASS_HTTP_TRANSPORT_IMPLEMENTED_LIVE_CAPABILITY_CLOSED",
        "descriptive_user_agent":_contract()["descriptive_user_agent"],
        "release_tracked":preflight["release_tracked"],
        "qa_tracked":preflight["qa_tracked"],
        "execution_allowed":preflight["execution_allowed"],
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
