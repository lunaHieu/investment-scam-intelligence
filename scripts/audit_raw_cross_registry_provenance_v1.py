"""Verify raw-file provenance through hash-pinned JSON registry chains offline."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter, deque
from pathlib import Path
from typing import Any, Iterable


REPO_ROOT = Path(__file__).resolve().parents[1]
RAW_ROOT = Path(r"D:\nckh 2026-2027\ISI_Data\raw")
SHA256_RE = re.compile(r"^[0-9a-fA-F]{64}$")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def is_within(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def resolve_claim_path(value: str, repo_root: Path) -> Path | None:
    if not value or value.startswith(("http://", "https://")):
        return None
    candidate = Path(value)
    if not candidate.is_absolute():
        candidate = repo_root / candidate
    return candidate.resolve()


def choose_hash(container: dict[str, Any], path_key: str) -> tuple[str, str] | None:
    candidates = [
        (key, value.lower())
        for key, value in container.items()
        if isinstance(value, str) and SHA256_RE.fullmatch(value)
    ]
    if not candidates:
        return None
    preferred = [
        f"{path_key}_sha256",
        path_key.replace("path", "sha256"),
        path_key.replace("output", "sha256"),
        "sha256",
        "file_sha256",
        "content_sha256",
    ]
    by_key = {key: value for key, value in candidates}
    for key in preferred:
        if key in by_key:
            return key, by_key[key]
    path_like_values = sum(
        isinstance(value, str)
        and not SHA256_RE.fullmatch(value)
        and any(token in key.casefold() for token in ("path", "file", "output", "artifact"))
        for key, value in container.items()
    )
    if len(candidates) == 1 and path_like_values == 1:
        return candidates[0]
    return None


def iter_hash_pinned_paths(data: Any, repo_root: Path) -> Iterable[tuple[str, Path, str, str]]:
    if isinstance(data, dict):
        for key, value in data.items():
            if isinstance(value, str) and any(token in key.casefold() for token in ("path", "file", "output", "artifact")):
                target = resolve_claim_path(value, repo_root)
                selected = choose_hash(data, key)
                if target is not None and selected is not None:
                    hash_key, expected_sha256 = selected
                    yield key, target, hash_key, expected_sha256
        for value in data.values():
            yield from iter_hash_pinned_paths(value, repo_root)
    elif isinstance(data, list):
        for value in data:
            yield from iter_hash_pinned_paths(value, repo_root)


def root_json_paths(repo_root: Path) -> list[Path]:
    paths: list[Path] = []
    for directory in (repo_root / "configs", repo_root / "registry"):
        paths.extend(path.resolve() for path in directory.rglob("*.json") if path.is_file())
    return sorted(set(paths), key=lambda item: str(item).casefold())


def should_follow_json_target(path: Path, raw_root: Path) -> bool:
    """Restrict transitive reads to provenance artifacts, never model/evaluation data."""
    name = path.name.casefold()
    provenance_tokens = (
        "acquisition",
        "capture",
        "manifest",
        "artifact_audit",
        "normalization",
        "crosswalk",
        "inventory",
        "readiness",
    )
    if is_within(path, raw_root):
        return "manifest" in name
    return any(token in name for token in provenance_tokens)


def trace_verified_claims(repo_root: Path, raw_root: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]], int]:
    queue = deque((path, "GIT_TRACKED_JSON_ROOT") for path in root_json_paths(repo_root))
    parsed: set[Path] = set()
    hash_cache: dict[Path, str] = {}
    claims: list[dict[str, Any]] = []
    parse_failures: list[dict[str, Any]] = []
    while queue:
        source, source_anchor = queue.popleft()
        source = source.resolve()
        if source in parsed:
            continue
        parsed.add(source)
        try:
            data = json.loads(source.read_text(encoding="utf-8-sig"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            parse_failures.append({"path": str(source), "error": type(exc).__name__})
            continue
        for path_key, target, hash_key, expected in iter_hash_pinned_paths(data, repo_root):
            exists = target.is_file()
            if exists and target not in hash_cache:
                hash_cache[target] = sha256_file(target)
            actual = hash_cache.get(target)
            matches = exists and actual == expected
            claim = {
                "source_document": str(source),
                "source_anchor": source_anchor,
                "path_key": path_key,
                "hash_key": hash_key,
                "target_path": str(target),
                "expected_sha256": expected,
                "exists": exists,
                "actual_sha256": actual,
                "hash_matches": matches,
                "target_is_raw": is_within(target, raw_root),
            }
            claims.append(claim)
            if (
                matches
                and target.suffix.casefold() == ".json"
                and target not in parsed
                and should_follow_json_target(target, raw_root)
            ):
                queue.append((target, f"VERIFIED_CHAIN_FROM:{source}"))
    return claims, parse_failures, len(parsed)


def raw_files(raw_root: Path) -> list[Path]:
    return sorted((path.resolve() for path in raw_root.rglob("*") if path.is_file()), key=lambda item: str(item).casefold())


def build_report(repo_root: Path = REPO_ROOT, raw_root: Path = RAW_ROOT) -> dict[str, Any]:
    claims, parse_failures, parsed_document_count = trace_verified_claims(repo_root, raw_root)
    raw_claims = [claim for claim in claims if claim["target_is_raw"]]
    claims_by_path: dict[Path, list[dict[str, Any]]] = {}
    for claim in raw_claims:
        claims_by_path.setdefault(Path(claim["target_path"]).resolve(), []).append(claim)

    inventory: list[dict[str, Any]] = []
    category_counts: Counter[str] = Counter()
    directory_counts: dict[str, Counter[str]] = {}
    for path in raw_files(raw_root):
        path_claims = claims_by_path.get(path, [])
        verified = [claim for claim in path_claims if claim["hash_matches"]]
        mismatched = [claim for claim in path_claims if claim["exists"] and not claim["hash_matches"]]
        if verified:
            category = "VERIFIED_HASH_PINNED_CHAIN"
        elif mismatched:
            category = "HASH_MISMATCH"
        elif path_claims:
            category = "CLAIM_TARGET_MISSING_AT_AUDIT"
        else:
            category = "NO_HASH_PINNED_CHAIN_FOUND"
        relative = path.relative_to(raw_root)
        top_directory = relative.parts[0]
        category_counts[category] += 1
        directory_counts.setdefault(top_directory, Counter())[category] += 1
        inventory.append(
            {
                "relative_path": relative.as_posix(),
                "byte_count": path.stat().st_size,
                "category": category,
                "verified_claim_count": len(verified),
                "claim_sources": sorted({claim["source_document"] for claim in verified}),
            }
        )

    mismatch_claims = [claim for claim in raw_claims if claim["exists"] and not claim["hash_matches"]]
    missing_claims = [claim for claim in raw_claims if not claim["exists"]]
    all_verified = category_counts["NO_HASH_PINNED_CHAIN_FOUND"] == 0 and not mismatch_claims
    status = "PASS_ALL_RAW_HASH_PINNED" if all_verified else "PASS_PARTIAL_PROVENANCE_GAPS_PRESERVED"
    return {
        "audit_id": "ISI_RAW_CROSS_REGISTRY_PROVENANCE_AUDIT_V1",
        "status": status,
        "verification_mode": "READ_ONLY_OFFLINE_TRANSITIVE_HASH_CHAIN",
        "scope": {
            "repo_root": str(repo_root),
            "raw_root": str(raw_root),
            "root_json_count": len(root_json_paths(repo_root)),
            "parsed_json_document_count": parsed_document_count,
            "parse_failure_count": len(parse_failures),
        },
        "summary": {
            "raw_file_count": len(inventory),
            "raw_byte_count": sum(item["byte_count"] for item in inventory),
            "verified_hash_pinned_chain_files": category_counts["VERIFIED_HASH_PINNED_CHAIN"],
            "no_hash_pinned_chain_found_files": category_counts["NO_HASH_PINNED_CHAIN_FOUND"],
            "hash_mismatch_files": category_counts["HASH_MISMATCH"],
            "verified_raw_claim_count": sum(claim["hash_matches"] for claim in raw_claims),
            "mismatched_raw_claim_count": len(mismatch_claims),
            "missing_raw_claim_target_count": len(missing_claims),
        },
        "by_top_level_directory": {
            directory: dict(sorted(counts.items())) for directory, counts in sorted(directory_counts.items())
        },
        "parse_failures": parse_failures,
        "mismatched_raw_claims": mismatch_claims,
        "missing_raw_claims": missing_claims,
        "raw_inventory": inventory,
        "decision": {
            "existing_raw_hash_mismatch_detected": bool(mismatch_claims),
            "complete_raw_provenance_chain_established": all_verified,
            "uncovered_files_require_manual_provenance_resolution": category_counts["NO_HASH_PINNED_CHAIN_FOUND"],
            "next_gate": "Resolve each uncovered raw file by locating an existing immutable acquisition record or by explicitly quarantining it; never manufacture provenance retroactively.",
            "training_allowed": False,
            "validation_or_test_opening_allowed": False,
            "labeling_allowed": False,
        },
        "safety_contract": {
            "network_operations": 0,
            "raw_file_modifications": 0,
            "labels_created": 0,
            "model_operations": 0,
            "validation_or_test_openings": 0,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    partial = args.output.with_suffix(args.output.suffix + ".partial")
    if args.output.exists() or partial.exists():
        raise FileExistsError("Refusing to overwrite raw cross-registry provenance audit")
    report = build_report()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    partial.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    partial.replace(args.output)
    print(json.dumps({key: report[key] for key in ("audit_id", "status", "scope", "summary", "by_top_level_directory", "decision")}, ensure_ascii=False, indent=2))
    return 0 if report["status"].startswith("PASS_") else 1


if __name__ == "__main__":
    raise SystemExit(main())
