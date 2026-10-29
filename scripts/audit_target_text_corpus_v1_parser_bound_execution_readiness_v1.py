"""Independently audit the local parser-bound stack before commit review."""

from __future__ import annotations

import ast
import hashlib
import json
import subprocess
from pathlib import Path
from urllib.parse import urlparse

from scripts.process_target_text_corpus_v1_parser_bound_pdf_lifecycle_v1 import (
    resolve_runtime_paths,
)
from scripts.verify_target_text_corpus_v1_parser_bound_content_release_v1 import (
    RELEASE,
    ROOT,
)


LOCAL_QA = (
    ROOT
    / "registry"
    / "analyses"
    / "target_text_corpus_v1_parser_bound_content_release_local_qa_v1.json"
)
ALLOWED_AUTHORITIES = {
    "api.github.com",
    "raw.githubusercontent.com",
    "aclanthology.org",
    "huggingface.co",
}
HTTP_TRANSPORT = "scripts/http_transport_target_text_corpus_v1_parser_bound_content_v1.py"


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git(*arguments: str) -> str:
    return subprocess.run(
        ["git", *arguments],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    ).stdout.strip()


def verify_hash_graph(qa: dict) -> list[str]:
    checked: list[str] = []
    for reference in [*qa["inputs"], *qa["implementation"]]:
        path = ROOT / reference["path"]
        if not path.is_file():
            raise FileNotFoundError(f"QA reference is missing: {reference['path']}")
        if sha256_file(path) != reference["sha256"]:
            raise ValueError(f"QA hash mismatch: {reference['path']}")
        checked.append(reference["path"])
    return checked


def expected_local_files(qa: dict) -> set[str]:
    return {
        *(item["path"] for item in qa["inputs"]),
        *(item["path"] for item in qa["implementation"]),
        str(LOCAL_QA.relative_to(ROOT)).replace("\\", "/"),
    }


def actual_untracked_files() -> set[str]:
    lines = git("status", "--porcelain=v1", "--untracked-files=all").splitlines()
    unexpected_status = [line for line in lines if line and not line.startswith("?? ")]
    if unexpected_status:
        raise ValueError(f"Tracked/index state is not clean: {unexpected_status}")
    return {line[3:].replace("\\", "/") for line in lines if line.startswith("?? ")}


def repository_state(managed_files: set[str]) -> tuple[str, set[str]]:
    untracked = actual_untracked_files()
    if untracked == managed_files:
        return "PRE_COMMIT_LOCAL", untracked
    tracked = {
        line.replace("\\", "/")
        for line in git("ls-files").splitlines()
        if line
    }
    if not untracked and managed_files.issubset(tracked):
        return "COMMITTED_TRACKED", untracked
    raise ValueError(
        f"Managed file state mismatch: missing_local={sorted(managed_files-untracked)}, "
        f"extra_untracked={sorted(untracked-managed_files)}, "
        f"missing_tracked={sorted(managed_files-tracked)}"
    )


def network_surface(script_paths: list[str]) -> dict:
    urllib_request_imports: list[str] = []
    build_opener_calls: list[str] = []
    forbidden_clients: list[str] = []
    for relative in script_paths:
        if not relative.startswith("scripts/") or not relative.endswith(".py"):
            continue
        source = (ROOT / relative).read_text(encoding="utf-8")
        tree = ast.parse(source, filename=relative)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = {alias.name for alias in node.names}
                if "urllib.request" in names:
                    urllib_request_imports.append(relative)
                if names.intersection({"requests", "httpx", "aiohttp", "socket"}):
                    forbidden_clients.append(relative)
            elif isinstance(node, ast.ImportFrom):
                if node.module == "urllib.request":
                    urllib_request_imports.append(relative)
                if node.module in {"requests", "httpx", "aiohttp", "socket"}:
                    forbidden_clients.append(relative)
            elif isinstance(node, ast.Call):
                if isinstance(node.func, ast.Attribute) and node.func.attr == "build_opener":
                    build_opener_calls.append(relative)
                if (
                    isinstance(node.func, ast.Attribute)
                    and node.func.attr in {"run", "Popen", "call", "check_output"}
                    and node.args
                    and isinstance(node.args[0], (ast.List, ast.Tuple))
                    and node.args[0].elts
                    and isinstance(node.args[0].elts[0], ast.Constant)
                    and isinstance(node.args[0].elts[0].value, str)
                    and node.args[0].elts[0].value.lower() in {
                        "curl", "curl.exe", "wget", "wget.exe",
                        "powershell", "powershell.exe", "pwsh", "pwsh.exe",
                    }
                ):
                    forbidden_clients.append(relative)
    return {
        "urllib_request_imports":sorted(set(urllib_request_imports)),
        "build_opener_calls":sorted(set(build_opener_calls)),
        "forbidden_clients":sorted(set(forbidden_clients)),
    }


def pdf_runtime_versions() -> dict:
    python, pdftoppm, pdfinfo = resolve_runtime_paths()
    for path in (python, pdftoppm, pdfinfo):
        if not path.is_file():
            raise FileNotFoundError(f"Bundled PDF dependency missing: {path}")
    output = subprocess.run(
        [
            str(python),
            "-c",
            "import json,pdfplumber,pypdf;print(json.dumps({'pypdf':pypdf.__version__,'pdfplumber':pdfplumber.__version__}))",
        ],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    ).stdout
    versions = json.loads(output)
    return {
        **versions,
        "pdftoppm_exists":True,
        "pdfinfo_exists":True,
    }


def audit() -> dict:
    release = json.loads(RELEASE.read_text(encoding="utf-8"))
    qa = json.loads(LOCAL_QA.read_text(encoding="utf-8"))
    checked = verify_hash_graph(qa)

    managed_files = expected_local_files(qa)
    state, actual_untracked = repository_state(managed_files)
    head = git("rev-parse", "HEAD")
    origin = git("rev-parse", "origin/main")
    merge_base = git("merge-base", "HEAD", "origin/main")
    ahead = int(git("rev-list", "--count", "origin/main..HEAD"))
    behind = int(git("rev-list", "--count", "HEAD..origin/main"))
    if merge_base != origin or behind != 0 or ahead not in {0, 1}:
        raise ValueError("Local HEAD is not equal to or exactly one commit ahead of origin/main")

    authorities = {urlparse(resource["url"]).hostname for resource in release["resources"]}
    if authorities != ALLOWED_AUTHORITIES:
        raise ValueError(f"Authority allowlist mismatch: {sorted(authorities)}")
    for item in release["inputs"]:
        path = ROOT / item["path"]
        if not path.is_file() or sha256_file(path) != item["sha256"]:
            raise ValueError(f"Release input mismatch: {item['path']}")

    script_paths = [item["path"] for item in qa["implementation"]]
    surface = network_surface(script_paths)
    if surface["urllib_request_imports"] != [HTTP_TRANSPORT]:
        raise ValueError("urllib.request is not isolated to the HTTP transport")
    if surface["build_opener_calls"] != [HTTP_TRANSPORT]:
        raise ValueError("Real opener construction is not isolated")
    if surface["forbidden_clients"]:
        raise ValueError(f"Unapproved network client found: {surface['forbidden_clients']}")

    http_source = (ROOT / HTTP_TRANSPORT).read_text(encoding="utf-8")
    orchestrator_source = (
        ROOT / "scripts/orchestrate_target_text_corpus_v1_parser_bound_content_v1.py"
    ).read_text(encoding="utf-8")
    for required in (
        "authorize_live_transport",
        'preflight["execution_allowed"] is not True',
        "capability is not _LIVE_CAPABILITY",
        "NoRedirectHandler",
    ):
        if required not in http_source:
            raise ValueError(f"HTTP capability invariant missing: {required}")
    if "capability = authorize_live_transport()" not in orchestrator_source:
        raise ValueError("Live orchestrator does not acquire capability first")

    output = ROOT / release["planned_output"]
    partial = ROOT / release["planned_partial"]
    if output.exists() or partial.exists() or Path(str(partial) + ".tmp").exists():
        raise FileExistsError("Planned output, partial, or checkpoint temp exists")
    if release["decision"]["execution_allowed_now"] is not False:
        raise ValueError("Local release opened execution")
    if release["pdf_lifecycle_contract"]["visual_review_status_after_automated_lifecycle"] != "PENDING_REQUIRED":
        raise ValueError("PDF visual-review gate opened")
    for key in ("commit_allowed_by_this_qa", "push_allowed_by_this_qa", "dataset_acquisition_allowed", "training_allowed"):
        if qa["decision"][key] is not False:
            raise ValueError(f"Local QA opened a forbidden decision: {key}")

    runtime = pdf_runtime_versions()
    if runtime["pypdf"] != "6.10.0" or runtime["pdfplumber"] != "0.11.9":
        raise ValueError("Bundled PDF package version changed")
    return {
        "status":"PASS_STACK_INTEGRITY_VERIFIED_EXECUTION_REMAINS_CLOSED",
        "repository_state":state,
        "head":head,
        "origin_main":origin,
        "ahead":ahead,
        "behind":behind,
        "qa_hashes_verified":len(checked),
        "managed_files":len(managed_files),
        "untracked_files":len(actual_untracked),
        "authorities":sorted(authorities),
        "network_surface":surface,
        "pdf_runtime":runtime,
        "planned_outputs_absent":True,
        "execution_allowed":False,
        "commit_allowed":False,
        "push_allowed":False,
        "dataset_acquisition_allowed":False,
        "training_allowed":False,
    }


def main() -> None:
    print(json.dumps(audit(), ensure_ascii=False))


if __name__ == "__main__":
    main()
