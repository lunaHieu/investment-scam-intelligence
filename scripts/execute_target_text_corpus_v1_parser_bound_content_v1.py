"""Parser-bound content executor. Network execution is blocked while local-only."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping

from scripts.verify_target_text_corpus_v1_parser_bound_content_release_v1 import RELEASE, ROOT, verify


LOCAL_QA = ROOT / "registry" / "analyses" / "target_text_corpus_v1_parser_bound_content_release_local_qa_v1.json"
HEX40 = re.compile(r"^[0-9a-f]{40}$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")


class ParserRejection(ValueError):
    """A parser guard with a safe, allowlisted diagnostic code."""

    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class TransportResponse:
    """A response supplied by an injected transport; it never opens a socket."""

    status_code: int
    final_url: str
    headers: Mapping[str, str]
    body: bytes
    redirect_count: int = 0


def _nested_keys(value: Any) -> set[str]:
    keys: set[str] = set()
    if isinstance(value, dict):
        for key, child in value.items():
            keys.add(str(key).lower())
            keys.update(_nested_keys(child))
    elif isinstance(value, list):
        for child in value:
            keys.update(_nested_keys(child))
    return keys


def _require_sha(value: Any, length: int) -> str:
    pattern = HEX40 if length == 40 else HEX64
    if not isinstance(value, str) or not pattern.fullmatch(value.lower()):
        raise ValueError(f"Expected {length}-character hexadecimal hash")
    return value.lower()


def parse_github_commit(value: Any) -> dict:
    if not isinstance(value, dict) or not isinstance(value.get("commit"), dict):
        raise ValueError("Invalid GitHub commit schema")
    commit = value["commit"]
    tree = commit.get("tree", {})
    return {
        "sha":_require_sha(value.get("sha"), 40),
        "html_url":value.get("html_url"),
        "author_date":(commit.get("author") or {}).get("date"),
        "committer_date":(commit.get("committer") or {}).get("date"),
        "tree_sha":_require_sha(tree.get("sha"), 40),
        "parent_shas":[_require_sha(item.get("sha"), 40) for item in value.get("parents", [])],
    }


def parse_github_tree(value: Any, prefixes: list[str], exact_paths: list[str]) -> dict:
    if not isinstance(value, dict) or not isinstance(value.get("tree"), list):
        raise ValueError("Invalid GitHub tree schema")
    if value.get("truncated") is not False:
        raise ValueError("Truncated GitHub tree cannot be accepted")
    retained = []
    for item in value["tree"]:
        path = item.get("path")
        if isinstance(path, str) and (path in exact_paths or any(path.startswith(prefix) for prefix in prefixes)):
            retained.append({key:item.get(key) for key in ("path","mode","type","sha","size")})
    return {"sha":_require_sha(value.get("sha"), 40),"truncated":bool(value.get("truncated")),"entries":retained}


def parse_manifest(value: Any) -> dict:
    if not isinstance(value, dict):
        raise ValueError("Manifest must be an object")
    files = value.get("files")
    if not isinstance(files, list):
        raise ValueError("Manifest files list missing")
    retained = []
    for item in files:
        if not isinstance(item, dict) or not isinstance(item.get("path"), str):
            raise ValueError("Invalid manifest entry")
        digest = item.get("sha256")
        retained.append({"path":item["path"],"sha256":_require_sha(digest, 64),"size":item.get("size", item.get("size_bytes"))})
    return {"release_version":value.get("release_version"),"generated_at":value.get("generated_at"),"files":retained}


def parse_checksums(value: Any) -> dict:
    entries = []
    if isinstance(value, dict):
        source = value.get("files", value)
        if isinstance(source, dict):
            entries = [{"path":path,"sha256":_require_sha(digest,64)} for path,digest in source.items()]
        elif isinstance(source, list):
            entries = [{"path":item["path"],"sha256":_require_sha(item["sha256"],64)} for item in source]
    if not entries:
        raise ValueError("Unsupported checksum schema")
    return {"entries":entries}


def reject_forbidden_json(value: Any, forbidden: list[str]) -> None:
    overlap = _nested_keys(value).intersection(key.lower() for key in forbidden)
    if overlap:
        raise ParserRejection("FORBIDDEN_DATASET_KEY_PRESENT")


def parse_hf_repository(value: Any, forbidden: list[str]) -> dict:
    reject_forbidden_json(value, forbidden)
    if not isinstance(value, dict):
        raise ValueError("HF repository metadata must be an object")
    siblings = value.get("siblings") or []
    return {
        "id":value.get("id"),"sha":_require_sha(value.get("sha"),40),
        "lastModified":value.get("lastModified"),"private":value.get("private"),
        "gated":value.get("gated"),"disabled":value.get("disabled"),
        "tags":value.get("tags") or [],"license":(value.get("cardData") or {}).get("license"),
        "sibling_paths":[item.get("rfilename") for item in siblings if isinstance(item,dict) and isinstance(item.get("rfilename"),str)],
    }


def parse_hf_commits(value: Any, forbidden: list[str]) -> dict:
    reject_forbidden_json(value, forbidden)
    rows = value if isinstance(value, list) else value.get("commits") if isinstance(value, dict) else None
    if not isinstance(rows, list):
        raise ParserRejection("COMMIT_LIST_MISSING_OR_INVALID")
    commits = []
    for item in rows:
        if not isinstance(item, dict):
            raise ParserRejection("COMMIT_ENTRY_NOT_OBJECT")
        commit_id = item.get("id")
        if not isinstance(commit_id, str) or not HEX40.fullmatch(commit_id.lower()):
            raise ParserRejection("COMMIT_ID_INVALID")
        commits.append({"id":commit_id.lower(),"title":item.get("title"),"createdAt":item.get("createdAt"),"authors":[author.get("username") for author in item.get("authors",[]) if isinstance(author,dict)]})
    return {"commits":commits}


def parse_markdown_document(data: bytes, allowed_sections: list[str]) -> dict:
    text = data.decode("utf-8", errors="strict")
    if "\x00" in text:
        raise ValueError("NUL byte in markdown")
    lines = text.splitlines()
    comma_dense = sum(line.count(",") >= 3 for line in lines)
    if comma_dense > max(3, len(lines)//5):
        raise ValueError("Document resembles delimited records")
    sections: dict[str, list[str]] = {}
    current = None
    for line in lines:
        if line.lstrip().startswith("#"):
            heading = line.lstrip("# ").strip().lower()
            current = next((name for name in allowed_sections if name.lower() in heading), None)
            if current:
                sections.setdefault(current, [])
        elif current:
            sections[current].append(line)
    return {"sections":{name:"\n".join(content).strip()[:12000] for name,content in sections.items()}}


def parse_resource(resource: dict, data: bytes) -> dict:
    if len(data) > resource["maximum_bytes"]:
        raise ValueError("Resource exceeds byte ceiling")
    parser = resource["parser"]
    if parser == "PDF_SCAMBENCH_METHODS_V1":
        if not data.startswith(b"%PDF-"):
            raise ValueError("PDF magic mismatch")
        return {"status":"PDF_VALIDATED_PENDING_BUNDLED_BACKEND_AND_VISUAL_REVIEW","sha256":hashlib.sha256(data).hexdigest(),"bytes":len(data)}
    if parser == "MARKDOWN_DOCUMENTATION_V1":
        return parse_markdown_document(data, resource["retained_sections"])
    value = json.loads(data.decode("utf-8", errors="strict"))
    if parser == "GITHUB_COMMIT_METADATA_V1": return parse_github_commit(value)
    if parser == "GITHUB_TREE_METADATA_V1": return parse_github_tree(value, resource["retained_path_prefixes"], resource["retained_exact_paths"])
    if parser == "NEXVISION_RELEASE_MANIFEST_V1": return parse_manifest(value)
    if parser == "NEXVISION_CHECKSUMS_V1": return parse_checksums(value)
    if parser == "HF_DATASET_REPOSITORY_METADATA_V1": return parse_hf_repository(value, resource["forbidden_keys"])
    if parser == "HF_COMMIT_METADATA_V1": return parse_hf_commits(value, resource["forbidden_keys"])
    raise ValueError(f"Unknown parser: {parser}")


def _header(headers: Mapping[str, str], name: str) -> str | None:
    wanted = name.lower()
    return next((str(value) for key, value in headers.items() if key.lower() == wanted), None)


def _base_result(resource: dict) -> dict:
    return {
        "resource_id":resource["resource_id"],
        "source_endpoint_id":resource["source_endpoint_id"],
        "url":resource["url"],
        "final_url":None,
        "parser":resource["parser"],
        "outcome":None,
        "http_status":None,
        "content_type":None,
        "response_bytes":0,
        "response_sha256":None,
        "structured_output":None,
        "raw_response_retained":False,
        "diagnostic_code":None,
    }


def _reject(row: dict, code: str) -> dict:
    row["outcome"] = "PARSER_REJECTED"
    row["diagnostic_code"] = code
    row["structured_output"] = None
    return row


def process_transport_response(resource: dict, response: TransportResponse) -> dict:
    """Validate and parse an injected response without retaining its body."""

    row = _base_result(resource)
    row.update({
        "final_url":response.final_url,
        "http_status":response.status_code,
        "content_type":_header(response.headers, "Content-Type"),
        "response_bytes":len(response.body),
        "response_sha256":hashlib.sha256(response.body).hexdigest(),
    })
    if response.status_code != 200:
        row["outcome"] = "HTTP_ERROR"
        row["diagnostic_code"] = f"HTTP_{response.status_code}"
        return row
    if len(response.body) > resource["maximum_bytes"]:
        return _reject(row, "BYTE_CEILING_EXCEEDED")
    media_type = str(row["content_type"] or "").split(";", 1)[0].strip().lower()
    if media_type not in resource["content_types"]:
        return _reject(row, "CONTENT_TYPE_MISMATCH")
    maximum_redirects = int(resource.get("maximum_redirects", 0))
    if response.redirect_count < 0 or response.redirect_count > maximum_redirects:
        return _reject(row, "REDIRECT_COUNT_MISMATCH")
    if resource["resource_id"] == "PBC07":
        if resource["required_final_url_contains"] not in response.final_url:
            return _reject(row, "IMMUTABLE_REDIRECT_IDENTITY_MISMATCH")
    elif response.final_url != resource["url"]:
        return _reject(row, "UNEXPECTED_FINAL_URL")
    try:
        row["structured_output"] = parse_resource(resource, response.body)
    except ParserRejection as error:
        return _reject(row, f"PARSER_REJECTED_{error.code}")
    except (UnicodeError, ValueError, TypeError, KeyError, json.JSONDecodeError) as error:
        return _reject(row, f"PARSER_REJECTED_{type(error).__name__.upper()}")
    row["outcome"] = "SUCCESS"
    return row


def _append_journal(path: Path, event: dict) -> None:
    with path.open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")


def run_injected_transport_harness(
    resources: list[dict],
    transport: Callable[[dict], TransportResponse],
    journal_path: Path,
) -> list[dict]:
    """Exercise execution semantics with an injected, normally synthetic transport."""

    journal_path.parent.mkdir(parents=True, exist_ok=True)
    with journal_path.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps({"event":"RESERVED", "resources":len(resources)}, sort_keys=True) + "\n")
    rows: list[dict] = []
    stopped = False
    for resource in resources:
        if stopped:
            row = _base_result(resource)
            row["outcome"] = "SKIPPED_AFTER_FAILURE"
            row["diagnostic_code"] = "EARLIER_RESOURCE_FAILED"
        else:
            try:
                row = process_transport_response(resource, transport(resource))
            except Exception as error:  # transport is an injected boundary
                row = _base_result(resource)
                row["outcome"] = "TRANSPORT_ERROR"
                row["diagnostic_code"] = f"TRANSPORT_{type(error).__name__.upper()}"
            stopped = row["outcome"] != "SUCCESS"
        rows.append(row)
        _append_journal(journal_path, {"event":"RESOURCE_RESULT", "result":row})
    _append_journal(journal_path, {"event":"HARNESS_COMPLETE", "rows":len(rows)})
    return rows


def execution_preflight() -> dict:
    release_check = verify(require_absent=True)
    tracked = subprocess.run(["git","ls-files","--error-unmatch",str(RELEASE.relative_to(ROOT)).replace("\\","/")],cwd=ROOT,capture_output=True).returncode == 0
    qa_tracked = subprocess.run(["git","ls-files","--error-unmatch",str(LOCAL_QA.relative_to(ROOT)).replace("\\","/")],cwd=ROOT,capture_output=True).returncode == 0
    value = json.loads(RELEASE.read_text(encoding="utf-8"))
    allowed = tracked and qa_tracked and value["decision"]["execution_allowed_now"] is True
    return {**release_check,"release_tracked":tracked,"qa_tracked":qa_tracked,"execution_allowed":allowed}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    preflight = execution_preflight()
    if not args.verify_only:
        raise PermissionError("Network execution is intentionally unavailable in the uncommitted local candidate")
    print(json.dumps(preflight, ensure_ascii=False))


if __name__ == "__main__":
    main()
