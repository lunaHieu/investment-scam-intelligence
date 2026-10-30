"""Bounded PBC05 PDF lifecycle with stage-specific hash-only diagnostics."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Callable

from scripts.process_target_text_corpus_v1_parser_bound_pdf_lifecycle_v1 import (
    resolve_runtime_paths,
)
from scripts.verify_target_text_corpus_v1_parser_bound_content_release_v1 import ROOT


Runner = Callable[..., subprocess.CompletedProcess]


class PdfLifecycleProcessError(RuntimeError):
    def __init__(self, stage: str, completed: subprocess.CompletedProcess):
        self.stage = stage
        self.returncode = int(completed.returncode)
        stdout = (completed.stdout or "").encode("utf-8", errors="replace")
        stderr = (completed.stderr or "").encode("utf-8", errors="replace")
        self.details = {
            "stage": stage,
            "returncode": self.returncode,
            "stdout_bytes": len(stdout),
            "stdout_sha256": hashlib.sha256(stdout).hexdigest(),
            "stderr_bytes": len(stderr),
            "stderr_sha256": hashlib.sha256(stderr).hexdigest(),
        }
        self.diagnostic_code = None
        if stage == "SECTION_EXTRACTION":
            try:
                payload = json.loads(completed.stdout or "{}")
                code = payload.get("diagnostic_code")
                allowed_codes = {
                    "PDF_INVALID_MAGIC",
                    "PDF_OPEN_OR_PARSE_ERROR",
                    "PDF_PAGE_LIMIT_EXCEEDED",
                    "PDF_PAGE_TEXT_EXTRACTION_ERROR",
                    "PDF_EXTRACTION_RUNTIME_ERROR",
                }
                if payload.get("status") == "PDF_EXTRACTION_REJECTED" and code in allowed_codes:
                    self.diagnostic_code = code
            except (json.JSONDecodeError, AttributeError, TypeError):
                pass
        super().__init__(f"{stage} returned {self.returncode}")


class PdfLifecycleLaunchError(RuntimeError):
    def __init__(self, stage: str, error: OSError):
        self.stage = stage
        self.details = {"stage": stage, "exception_type": type(error).__name__}
        super().__init__(f"{stage} could not be launched")


def _require_runtime(paths: tuple[Path, ...]) -> None:
    missing = [str(path) for path in paths if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"Bundled PDF runtime is incomplete: {missing}")


def _run_stage(stage: str, command: list[str], runner: Runner) -> subprocess.CompletedProcess:
    try:
        completed = runner(
            command,
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
    except OSError as error:
        raise PdfLifecycleLaunchError(stage, error) from error
    if completed.returncode != 0:
        raise PdfLifecycleProcessError(stage, completed)
    return completed


def process_pdf_lifecycle_v2(
    resource: dict,
    data: bytes,
    *,
    temporary_root: Path | None = None,
    python_path: Path | None = None,
    pdftoppm_path: Path | None = None,
    pdfinfo_path: Path | None = None,
    runner: Runner = subprocess.run,
) -> dict:
    if resource["resource_id"] != "PBC05" or resource["parser"] != "PDF_SCAMBENCH_METHODS_V1":
        raise ValueError("PDF lifecycle V2 is restricted to PBC05")
    if len(data) > int(resource["maximum_bytes"]):
        raise ValueError("PDF exceeds byte ceiling")
    if not data.startswith(b"%PDF-"):
        raise ValueError("PDF magic mismatch")

    default_python, default_pdftoppm, default_pdfinfo = resolve_runtime_paths()
    python = python_path or default_python
    pdftoppm = pdftoppm_path or default_pdftoppm
    pdfinfo = pdfinfo_path or default_pdfinfo
    _require_runtime((python, pdftoppm, pdfinfo))
    root = temporary_root or (ROOT / "tmp" / "pdfs")
    root.mkdir(parents=True, exist_ok=True)
    result: dict | None = None
    work_path: Path | None = None
    try:
        with tempfile.TemporaryDirectory(prefix="pbc05-lifecycle-v2-", dir=root) as directory:
            work_path = Path(directory)
            pdf_path = work_path / "source.pdf"
            with pdf_path.open("xb") as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            digest = hashlib.sha256(data).hexdigest()
            if hashlib.sha256(pdf_path.read_bytes()).hexdigest() != digest:
                raise ValueError("Temporary PDF hash mismatch")

            info = _run_stage("PDFINFO", [str(pdfinfo), str(pdf_path)], runner)
            if "Pages:" not in info.stdout or "Encrypted:       no" not in info.stdout:
                raise ValueError("PDF structural preflight failed")
            extraction = json.loads(
                _run_stage(
                    "SECTION_EXTRACTION",
                    [str(python), "-m", "scripts.extract_scambench_pdf_sections_v1", str(pdf_path)],
                    runner,
                ).stdout
            )
            page_count = int(extraction["page_count"])
            if page_count < 1 or page_count > int(resource["maximum_pages"]):
                raise ValueError("PDF page limit violated")
            if extraction["visual_review_status"] != "PENDING_REQUIRED":
                raise ValueError("PDF extractor opened the visual-review gate")

            render_dir = work_path / "rendered"
            render_dir.mkdir()
            prefix = render_dir / "page"
            _run_stage(
                "PDFTOPPM_RENDER",
                [str(pdftoppm), "-png", "-r", "100", str(pdf_path), str(prefix)],
                runner,
            )
            rendered = sorted(render_dir.glob("page-*.png"))
            if len(rendered) != page_count:
                raise ValueError("Rendered page cardinality mismatch")
            for image in rendered:
                payload = image.read_bytes()
                if not payload.startswith(b"\x89PNG\r\n\x1a\n") or len(payload) < 100:
                    raise ValueError("Rendered page failed PNG integrity check")
            result = {
                "status": "PDF_EXTRACTED_VISUAL_REVIEW_PENDING",
                "sha256": digest,
                "bytes": len(data),
                "page_count": page_count,
                "sections": extraction["sections"],
                "rendered_page_count": len(rendered),
                "render_integrity_status": "PASS_PNG_STRUCTURE_AND_PAGE_COUNT",
                "visual_review_status": "PENDING_REQUIRED",
                "temporary_artifacts_deleted": False,
            }
    finally:
        if work_path is not None and work_path.exists():
            raise RuntimeError("Temporary PDF lifecycle V2 directory was not deleted")
    if result is None:
        raise RuntimeError("PDF lifecycle V2 produced no result")
    result["temporary_artifacts_deleted"] = True
    return result
