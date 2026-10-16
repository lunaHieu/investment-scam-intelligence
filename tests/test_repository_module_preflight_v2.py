import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from scripts.run_repository_module_preflight_v2 import run_preflight
from scripts.verify_repository_module_preflight_v2 import verify


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs" / "repository_module_preflight_v2.json"
REGISTRY = ROOT / "registry" / "analyses" / "repository_module_preflight_v2.json"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class RepositoryModulePreflightV2Tests(unittest.TestCase):
    def test_exact_v5_modules_import_offline_and_verify(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "report.json"
            report = run_preflight(CONFIG, output)
            self.assertEqual(report["status"], "PASS_ALL_V5_MODULES_IMPORTABLE")
            self.assertEqual(report["module_count"], 3)
            self.assertEqual(report["passed_count"], 3)
            self.assertEqual(report["failed_count"], 0)
            self.assertEqual(report["safety_contract"]["network_operations"], 0)
            result = verify(CONFIG, output)
            self.assertTrue(result["valid"])
            self.assertEqual(result["main_functions_invoked"], 0)

    def test_runner_refuses_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "report.json"
            output.write_text(json.dumps({"existing": True}), encoding="utf-8")
            with self.assertRaises(FileExistsError):
                run_preflight(CONFIG, output)

    def test_verifier_rejects_changed_module_population(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "report.json"
            report = run_preflight(CONFIG, output)
            changed = copy.deepcopy(report)
            changed["results"] = changed["results"][:-1]
            output.write_text(json.dumps(changed), encoding="utf-8")
            with self.assertRaises(ValueError):
                verify(CONFIG, output)

    def test_registry_hashes_and_closed_gates_are_current(self) -> None:
        data = json.loads(REGISTRY.read_text(encoding="utf-8"))
        for item in data["inputs"] + data["implementation"] + data["outputs"]:
            path = Path(item["path"])
            if not path.is_absolute():
                path = ROOT / path
            self.assertTrue(path.is_file(), item["path"])
            self.assertEqual(sha256_file(path), item["sha256"], item["path"])
        self.assertEqual(data["findings"]["module_count"], 3)
        self.assertEqual(data["findings"]["passed_count"], 3)
        self.assertEqual(data["findings"]["failed_count"], 0)
        self.assertEqual(data["findings"]["v5_modules_importable"], 3)
        self.assertFalse(data["decision"]["network_execution_allowed"])
        self.assertFalse(data["decision"]["training_allowed"])


if __name__ == "__main__":
    unittest.main()
