import json
import tempfile
import unittest
from pathlib import Path

from scripts.execute_target_text_corpus_v1_parser_bound_content_v1 import (
    TransportResponse, execution_preflight, parse_checksums, parse_github_commit,
    parse_github_tree, parse_hf_repository, parse_manifest, parse_markdown_document,
    parse_resource, process_transport_response, run_injected_transport_harness,
)
from scripts.verify_target_text_corpus_v1_parser_bound_content_release_v1 import RELEASE


H40="a"*40
H64="b"*64


def resources():
    return json.loads(RELEASE.read_text(encoding="utf-8"))["resources"]


def response(resource, body, content_type=None, final_url=None, redirects=0, status=200):
    return TransportResponse(
        status_code=status,
        final_url=final_url or resource["url"],
        headers={"Content-Type":content_type or resource["content_types"][0]},
        body=body,
        redirect_count=redirects,
    )


class ParserBoundExecutorV1Tests(unittest.TestCase):
    def test_preflight_keeps_execution_closed_before_and_after_commit(self):
        value=execution_preflight()
        self.assertEqual(value["release_tracked"],value["qa_tracked"])
        self.assertFalse(value["execution_allowed"])

    def test_github_commit_retains_only_allowlisted_metadata(self):
        value={"sha":H40,"html_url":"https://example.invalid/c","commit":{"author":{"date":"2026-01-01"},"committer":{"date":"2026-01-02"},"tree":{"sha":H40},"message":"not retained"},"parents":[{"sha":H40}],"files":[{"patch":"not retained"}]}
        parsed=parse_github_commit(value);self.assertNotIn("message",parsed);self.assertNotIn("files",parsed)

    def test_tree_filters_paths_without_content(self):
        value={"sha":H40,"truncated":False,"tree":[{"path":"metadata/checksums.json","mode":"100644","type":"blob","sha":H40,"size":10},{"path":"data/records.jsonl","mode":"100644","type":"blob","sha":H40,"size":999}]}
        parsed=parse_github_tree(value,["metadata/"],["DATASET_CARD.md"]);self.assertEqual([x["path"] for x in parsed["entries"]],["metadata/checksums.json"])

    def test_truncated_tree_fails_closed(self):
        with self.assertRaises(ValueError):
            parse_github_tree({"sha":H40,"truncated":True,"tree":[]},["metadata/"],[])

    def test_manifest_and_checksum_schemas(self):
        self.assertEqual(parse_manifest({"files":[{"path":"x","sha256":H64,"size":1}]})["files"][0]["size"],1)
        self.assertEqual(parse_checksums({"x":H64})["entries"][0]["path"],"x")

    def test_hf_forbidden_record_key_fails_closed(self):
        with self.assertRaises(ValueError):parse_hf_repository({"sha":H40,"rows":[]},["rows","text"])

    def test_markdown_rejects_delimited_records(self):
        data=("a,b,c,d\n"*10).encode()
        with self.assertRaises(ValueError):parse_markdown_document(data,["files"])

    def test_pdf_only_validates_magic_before_backend(self):
        resource={"parser":"PDF_SCAMBENCH_METHODS_V1","maximum_bytes":100}
        value=parse_resource(resource,b"%PDF-1.7 synthetic")
        self.assertEqual(value["status"],"PDF_VALIDATED_PENDING_BUNDLED_BACKEND_AND_VISUAL_REVIEW")

    def test_transport_success_never_retains_body(self):
        resource=resources()[0]
        body=json.dumps({"sha":H40,"html_url":"https://example.invalid","commit":{"author":{},"committer":{},"tree":{"sha":H40}},"parents":[]}).encode()
        row=process_transport_response(resource,response(resource,body))
        self.assertEqual(row["outcome"],"SUCCESS")
        self.assertFalse(row["raw_response_retained"])
        self.assertNotIn("body",row)

    def test_content_type_rejected_before_invalid_json_parse(self):
        resource=resources()[0]
        row=process_transport_response(resource,response(resource,b"not json",content_type="text/html"))
        self.assertEqual(row["diagnostic_code"],"CONTENT_TYPE_MISMATCH")

    def test_oversized_response_fails_closed(self):
        resource=resources()[3]
        row=process_transport_response(resource,response(resource,b"x"*(resource["maximum_bytes"]+1)))
        self.assertEqual(row["diagnostic_code"],"BYTE_CEILING_EXCEEDED")

    def test_markdown_redirect_requires_immutable_revision(self):
        resource=resources()[6]
        row=process_transport_response(resource,response(resource,b"# Files\nmetadata only",final_url="https://huggingface.co/wrong",redirects=1))
        self.assertEqual(row["diagnostic_code"],"IMMUTABLE_REDIRECT_IDENTITY_MISMATCH")

    def test_journal_is_exclusive_and_stops_after_failure(self):
        selected=resources()[:2]
        calls=[]
        def fake_transport(resource):
            calls.append(resource["resource_id"])
            return response(resource,b"not-json",content_type="text/html")
        with tempfile.TemporaryDirectory() as directory:
            journal=Path(directory)/"journal.jsonl"
            rows=run_injected_transport_harness(selected,fake_transport,journal)
            self.assertEqual(calls,["PBC01"])
            self.assertEqual([row["outcome"] for row in rows],["PARSER_REJECTED","SKIPPED_AFTER_FAILURE"])
            events=[json.loads(line) for line in journal.read_text(encoding="utf-8").splitlines()]
            self.assertEqual([event["event"] for event in events],["RESERVED","RESOURCE_RESULT","RESOURCE_RESULT","HARNESS_COMPLETE"])
            with self.assertRaises(FileExistsError):
                run_injected_transport_harness(selected,fake_transport,journal)

    def test_transport_exception_records_type_without_message(self):
        resource=resources()[0]
        with tempfile.TemporaryDirectory() as directory:
            journal=Path(directory)/"journal.jsonl"
            rows=run_injected_transport_harness([resource],lambda _:(_ for _ in ()).throw(OSError("secret")),journal)
            self.assertEqual(rows[0]["diagnostic_code"],"TRANSPORT_OSERROR")
            self.assertNotIn("secret",journal.read_text(encoding="utf-8"))


if __name__=="__main__":unittest.main()
