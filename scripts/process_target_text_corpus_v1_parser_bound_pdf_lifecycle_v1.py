"""Safely extract and render PBC05 while always deleting temporary artifacts."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import tempfile
from pathlib import Path

from scripts.verify_target_text_corpus_v1_parser_bound_content_release_v1 import (
    ROOT,
)


def resolve_runtime_paths() -> tuple[Path, Path, Path]:
    dependency_root = (
        Path.home()
        / ".cache"
        / "codex-runtimes"
        / "codex-primary-runtime"
        / "dependencies"
    )
    python = dependency_root / "python" / "python.exe"
    poppler = dependency_root / "native" / "poppler" / "Library" / "bin"
    return python, poppler / "pdftoppm.exe", poppler / "pdfinfo.exe"


def _require_runtime(paths: tuple[Path, ...]) -> None:
    missing = [str(path) for path in paths if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"Bundled PDF runtime is incomplete: {missing}")


def _run(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def process_pdf_lifecycle(
    resource: dict,
    data: bytes,
    *,
    temporary_root: Path | None = None,
    python_path: Path | None = None,
    pdftoppm_path: Path | None = None,
    pdfinfo_path: Path | None = None,
) -> dict:
    """Extract matched text, render every page, then delete PDF and PNG files."""

    if resource["resource_id"] != "PBC05" or resource["parser"] != "PDF_SCAMBENCH_METHODS_V1":
        raise ValueError("PDF lifecycle is restricted to PBC05")
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
        with tempfile.TemporaryDirectory(prefix="pbc05-lifecycle-", dir=root) as directory:
            work_path = Path(directory)
            pdf_path = work_path / "source.pdf"
            with pdf_path.open("xb") as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            digest = hashlib.sha256(data).hexdigest()
            if hashlib.sha256(pdf_path.read_bytes()).hexdigest() != digest:
                raise ValueError("Temporary PDF hash mismatch")

            info = _run([str(pdfinfo), str(pdf_path)])
            if "Pages:" not in info.stdout or "Encrypted:       no" not in info.stdout:
                raise ValueError("PDF structural preflight failed")
            extraction = json.loads(
                _run([
                    str(python),
                    "-m",
                    "scripts.extract_scambench_pdf_sections_v1",
                    str(pdf_path),
                ]).stdout
            )
            page_count = int(extraction["page_count"])
            if page_count < 1 or page_count > int(resource["maximum_pages"]):
                raise ValueError("PDF page limit violated")
            if extraction["visual_review_status"] != "PENDING_REQUIRED":
                raise ValueError("PDF extractor opened the visual-review gate")

            render_dir = work_path / "rendered"
            render_dir.mkdir()
            prefix = render_dir / "page"
            _run([
                str(pdftoppm), "-png", "-r", "100", str(pdf_path), str(prefix)
            ])
            rendered = sorted(render_dir.glob("page-*.png"))
            if len(rendered) != page_count:
                raise ValueError("Rendered page cardinality mismatch")
            for image in rendered:
                payload = image.read_bytes()
                if not payload.startswith(b"\x89PNG\r\n\x1a\n") or len(payload) < 100:
                    raise ValueError("Rendered page failed PNG integrity check")
            result = {
                "status":"PDF_EXTRACTED_VISUAL_REVIEW_PENDING",
                "sha256":digest,
                "bytes":len(data),
                "page_count":page_count,
                "sections":extraction["sections"],
                "rendered_page_count":len(rendered),
                "render_integrity_status":"PASS_PNG_STRUCTURE_AND_PAGE_COUNT",
                "visual_review_status":"PENDING_REQUIRED",
                "temporary_artifacts_deleted":False,
            }
    finally:
        if work_path is not None and work_path.exists():
            raise RuntimeError("Temporary PDF lifecycle directory was not deleted")
    if result is None:
        raise RuntimeError("PDF lifecycle produced no result")
    result["temporary_artifacts_deleted"] = True
    return result
