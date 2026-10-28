import hashlib
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LEGACY_MANIFEST = Path(
    "registry/manifests/"
    "mendeley_investment_deceptive_2026__v2__2026-09-07.json"
)
LEGACY_MANIFEST_SHA256 = (
    "2991888803d52f6d65686af3d760abdeb4219b1d63b238f1d4dcccf979c001a9"
)


def run_git(*args: str, cwd: Path = ROOT) -> str:
    process = subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return process.stdout


class RepositoryCheckoutQualityV1Tests(unittest.TestCase):
    def test_current_state_pointer_targets_existing_artifacts(self) -> None:
        pointer = (ROOT / "CURRENT_STATE.md").read_text(encoding="utf-8")
        required = (
            "docs/project-direction-plan-r8.md",
            "docs/reproducibility-current-state-v42.md",
            "registry/analyses/project_state_gap_ledger_v45.json",
            "docs/current-test-suite-lifecycle-v4.md",
            "registry/analyses/crimson_primary_review_readiness_v1.json",
            "registry/analyses/target_text_corpus_v1_ready_channel_wayback_availability_continuation_result_v1.json",
            "registry/analyses/target_text_corpus_v1_ready_channel_cdx_canary_result_v1.json",
            "registry/analyses/target_text_corpus_v1_ready_channel_cdx_bulk_result_v1.json",
            "registry/analyses/target_text_corpus_v1_ready_channel_capture_plan_v1.json",
            "registry/analyses/target_text_corpus_v1_ready_channel_capture_release_v1.json",
            "registry/analyses/target_text_corpus_v1_ready_channel_capture_result_v1.json",
        )
        for relative in required:
            self.assertIn(relative, pointer)
            self.assertTrue((ROOT / relative).is_file(), relative)

    def test_hash_stable_checkout_with_windows_line_endings_enabled(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            clone = Path(directory) / "clone"
            run_git(
                "clone",
                "--local",
                "--no-hardlinks",
                "--no-checkout",
                str(ROOT),
                str(clone),
            )
            run_git("config", "core.autocrlf", "true", cwd=clone)
            run_git("checkout", "--force", "HEAD", cwd=clone)

            eol_inventory = run_git("ls-files", "--eol", cwd=clone).splitlines()
            unstable = [
                line
                for line in eol_inventory
                if "eol=lf" in line and "w/lf" not in line
            ]
            self.assertEqual(unstable, [])
            self.assertEqual(run_git("status", "--porcelain", cwd=clone), "")

            legacy_bytes = (clone / LEGACY_MANIFEST).read_bytes()
            self.assertEqual(
                hashlib.sha256(legacy_bytes).hexdigest(),
                LEGACY_MANIFEST_SHA256,
            )
            attributes = run_git(
                "check-attr", "text", "eol", "--", LEGACY_MANIFEST.as_posix(), cwd=clone
            )
            self.assertIn("text: unset", attributes)
            self.assertIn("eol: unspecified", attributes)


if __name__ == "__main__":
    unittest.main()
