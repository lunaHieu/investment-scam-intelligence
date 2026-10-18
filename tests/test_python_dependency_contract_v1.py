import ast
import re
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PYPROJECT = ROOT / "pyproject.toml"
EMBEDDING_LOCK = ROOT / "configs" / "text_semantic_challenger_v4_requirements.lock.txt"

IMPORT_TO_DISTRIBUTION = {
    "joblib": "joblib",
    "numpy": "numpy",
    "scipy": "scipy",
    "sklearn": "scikit-learn",
    "tokenizers": "tokenizers",
    "torch": "torch",
    "transformers": "transformers",
}
EXPECTED_BASELINE = {
    "joblib==1.6.0",
    "numpy==2.2.6",
    "scikit-learn==1.7.2",
    "scipy==1.15.3",
}
EXPECTED_EMBEDDING = {
    "numpy==2.2.6",
    "scikit-learn==1.7.2",
    "tokenizers==0.22.1",
    "torch==2.9.1",
    "transformers==4.57.6",
}


def imported_roots(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".", 1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            roots.add(node.module.split(".", 1)[0])
    return roots


def locked_requirements() -> set[str]:
    return {
        line.strip()
        for line in EMBEDDING_LOCK.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }


def optional_group(pyproject: str, name: str) -> set[str]:
    match = re.search(rf"^{name} = \[(.*?)^\]$", pyproject, re.MULTILINE | re.DOTALL)
    if match is None:
        raise AssertionError(f"Missing optional dependency group: {name}")
    return set(re.findall(r'"([^"]+)"', match.group(1)))


class PythonDependencyContractV1Tests(unittest.TestCase):
    def test_all_third_party_imports_are_declared(self) -> None:
        imported: set[str] = set()
        for directory in (ROOT / "scripts", ROOT / "src"):
            for path in directory.rglob("*.py"):
                imported.update(imported_roots(path))

        local_roots = {"scripts", "src", "isi"}
        local_roots.update(path.stem for path in (ROOT / "scripts").glob("*.py"))
        third_party = imported - sys.stdlib_module_names - local_roots
        self.assertEqual(third_party, set(IMPORT_TO_DISTRIBUTION))

    def test_optional_groups_are_exact_and_fully_locked(self) -> None:
        pyproject = PYPROJECT.read_text(encoding="utf-8")
        self.assertRegex(pyproject, re.compile(r"^requires-python = \">=3\.10\"$", re.MULTILINE))
        self.assertRegex(pyproject, re.compile(r"^dependencies = \[\]$", re.MULTILINE))
        self.assertEqual(optional_group(pyproject, "baseline"), EXPECTED_BASELINE)
        self.assertEqual(optional_group(pyproject, "embedding"), EXPECTED_EMBEDDING)

        lock = locked_requirements()
        declared = EXPECTED_BASELINE | EXPECTED_EMBEDDING
        self.assertEqual({item for item in lock if item in declared}, declared)
        for requirement in lock:
            self.assertRegex(
                requirement,
                re.compile(r"^[A-Za-z0-9_.-]+==[^=\s]+$"),
            )


if __name__ == "__main__":
    unittest.main()
