import contextlib
import io
import unittest

from scripts.validate_registry import analysis_training_gate_closed, main


class ValidateRegistryTests(unittest.TestCase):
    def test_training_gate_accepts_current_and_legacy_explicit_closure_only(self) -> None:
        self.assertTrue(
            analysis_training_gate_closed({"safety_contract": {"training_allowed": False}})
        )
        self.assertTrue(
            analysis_training_gate_closed(
                {"safety_contract": {}, "decision": {"training_allowed": False}}
            )
        )
        for analysis in (
            {},
            {"safety_contract": {"training_allowed": None}, "decision": {"training_allowed": False}},
            {"safety_contract": {"training_allowed": True}, "decision": {"training_allowed": False}},
        ):
            self.assertFalse(analysis_training_gate_closed(analysis))

    def test_current_registry_passes_as_one_closed_contract(self) -> None:
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            main()
        self.assertIn("Registry valid:", output.getvalue())


if __name__ == "__main__":
    unittest.main()
