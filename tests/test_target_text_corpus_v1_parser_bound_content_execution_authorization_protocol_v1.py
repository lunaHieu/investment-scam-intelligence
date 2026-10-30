import copy
import json
import tempfile
import unittest
from pathlib import Path

from scripts.verify_target_text_corpus_v1_parser_bound_content_execution_authorization_protocol_v1 import (
    PASS_STATUS,
    PROTOCOL,
    verify,
)


class ParserBoundExecutionAuthorizationProtocolV1Tests(unittest.TestCase):
    def test_committed_stack_is_bound_but_execution_remains_closed(self):
        result = verify()
        self.assertEqual(result["status"], PASS_STATUS)
        self.assertEqual(result["checks"]["resource_count"], 8)
        self.assertFalse(result["checks"]["owner_network_authorization_received"])
        self.assertFalse(result["decision"]["network_execution_allowed_now"])
        self.assertEqual(result["safety_contract"]["network_operations"], 0)

    def test_generic_continue_instruction_cannot_be_promoted_to_authorization(self):
        value = json.loads(PROTOCOL.read_text(encoding="utf-8"))
        self.assertFalse(value["required_owner_authorization"]["generic_continue_instruction_is_sufficient"])
        self.assertTrue(value["required_owner_authorization"]["must_name_network_execution"])

    def test_tampered_open_gate_is_rejected(self):
        value = json.loads(PROTOCOL.read_text(encoding="utf-8"))
        tampered = copy.deepcopy(value)
        tampered["decision"]["network_execution_allowed_now"] = True
        temp_root = PROTOCOL.parents[1] / "tmp"
        temp_root.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=temp_root) as directory:
            path = Path(directory) / "tampered.json"
            path.write_text(json.dumps(tampered), encoding="utf-8")
            result = verify(path)
        self.assertEqual(result["status"], "FAIL")
        self.assertIn("Closed decision gate opened: network_execution_allowed_now", result["errors"])


if __name__ == "__main__":
    unittest.main()
