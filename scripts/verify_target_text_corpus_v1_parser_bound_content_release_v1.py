"""Verify local parser-bound content release without network access."""
import hashlib,json
from pathlib import Path
from urllib.parse import urlparse
ROOT=Path(__file__).resolve().parents[1];RELEASE=ROOT/"configs"/"target_text_corpus_v1_parser_bound_content_release_v1.json"
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def verify(require_absent=False):
 v=json.loads(RELEASE.read_text(encoding="utf-8"))
 if v["status"]!="FROZEN_EXECUTION_CLOSED":raise ValueError("Release status changed")
 for i in v["inputs"]:
  p=ROOT/i["path"]
  if not p.is_file() or sha(p)!=i["sha256"]:raise ValueError(f"Input hash mismatch: {i['path']}")
 resources=v["resources"]
 if [r["resource_id"] for r in resources]!=[f"PBC{i:02}" for i in range(1,9)]:raise ValueError("Resource identity changed")
 if [r["source_endpoint_id"] for r in resources]!=[f"RFE{i:02}" for i in range(1,9)]:raise ValueError("HEAD lineage changed")
 if len({r["url"] for r in resources})!=8:raise ValueError("Duplicate resource URL")
 allowed={"api.github.com","raw.githubusercontent.com","aclanthology.org","huggingface.co"}
 if any(urlparse(r["url"]).hostname not in allowed for r in resources):raise ValueError("Authority outside allowlist")
 if sum(r["maximum_bytes"] for r in resources)!=v["execution_contract"]["maximum_total_response_bytes"]:raise ValueError("Total byte bound mismatch")
 if resources[4]["parser"]!="PDF_SCAMBENCH_METHODS_V1" or resources[4]["maximum_pages"]!=24 or resources[4]["temporary_file_must_be_deleted"] is not True:raise ValueError("PDF contract changed")
 for r in (resources[5],resources[7]):
  if not {"rows","content","text","message","examples","preview"}.issubset(set(r["forbidden_keys"])):raise ValueError("HF record rejection weakened")
 c=v["execution_contract"]
 for k in ("default_follow_redirects","raw_response_retention_allowed","dataset_landing_or_viewer_pages_allowed","dataset_file_download_allowed","repository_clone_allowed","candidate_live_domain_access_allowed","author_contact_allowed","labeling_allowed","validation_or_test_open_allowed","model_operations_allowed"):
  if c[k] is not False:raise ValueError(f"Closed capability opened: {k}")
 for k in ("structured_extractions_only","reject_before_parse_if_content_type_or_size_mismatch","reject_and_discard_if_forbidden_key_found","pdf_visual_review_required_before_evidence_acceptance","no_overwrite","incremental_journal_required","execution_requires_committed_release_and_qa"):
  if c[k] is not True:raise ValueError(f"Safeguard removed: {k}")
 if c["dataset_record_detection_json_resources"]!=["PBC06","PBC08"] or c["dataset_record_detection_markdown_resources"]!=["PBC07"] or c["parser_specific_metadata_keys_may_not_be_retained_unless_allowlisted"] is not True:raise ValueError("Record detection scope changed")
 decision=v["decision"]
 if decision["release_frozen"] is not True or decision["execution_requires_separate_owner_authorization_after_commit"] is not True:raise ValueError("Release decision contract changed")
 if decision["execution_allowed_now"] is not False:raise ValueError("Frozen release opened execution")
 dep=v["pdf_dependency_contract"]
 if dep["bundle_version"]!="26.1025.11240" or dep["project_venv_install_required"] is not False or dep["resolve_from_workspace_dependency_runtime_at_execution"] is not True:raise ValueError("PDF dependency contract changed")
 if dep["required_tools"]!=["pdftoppm","pdfinfo"]:raise ValueError("PDF render tooling changed")
 lifecycle=v["pdf_lifecycle_contract"]
 if lifecycle["render_dpi"]!=100 or lifecycle["visual_review_status_after_automated_lifecycle"]!="PENDING_REQUIRED":raise ValueError("PDF lifecycle bounds changed")
 for k in ("temporary_pdf_and_rendered_pages_must_be_deleted","extracted_text_may_be_retained_only_for_matched_sections","evidence_acceptance_remains_closed","live_orchestrator_must_invoke_pdf_lifecycle"):
  if lifecycle[k] is not True:raise ValueError(f"PDF lifecycle safeguard removed: {k}")
 transport=v["http_transport_contract"]
 if transport["descriptive_user_agent"]!="ISI-ParserBoundContent/1.0 (gpt-5; https://github.com/lunaHieu/investment-scam-intelligence)":raise ValueError("HTTP User-Agent changed")
 if transport["timeout_seconds"]!=30 or transport["read_chunk_bytes"]!=65536:raise ValueError("HTTP transport bounds changed")
 for k in ("automatic_redirects_allowed","automatic_retry_allowed"):
  if transport[k] is not False:raise ValueError(f"Unsafe HTTP transport option opened: {k}")
 for k in ("network_execution_requires_capability","capability_requires_successful_execution_preflight"):
  if transport[k] is not True:raise ValueError(f"HTTP capability gate weakened: {k}")
 if transport["redirect_statuses"]!=[301,302,303,307,308]:raise ValueError("Redirect statuses changed")
 orchestrator=v["orchestrator_contract"]
 if orchestrator["partial_format"]!="ATOMIC_JSON_CHECKPOINT":raise ValueError("Partial checkpoint format changed")
 for k in ("reserve_partial_before_transport","checkpoint_after_each_resource","fsync_before_replace","stop_after_first_failure","independent_verify_before_final","finalize_with_atomic_replace"):
  if orchestrator[k] is not True:raise ValueError(f"Orchestrator safeguard removed: {k}")
 if orchestrator["automatic_resume_allowed"] is not False:raise ValueError("Automatic resume opened")
 out,part=ROOT/v["planned_output"],ROOT/v["planned_partial"]
 if require_absent and (out.exists() or part.exists()):raise FileExistsError("Planned output exists")
 return {"status":"PASS_LOCAL_PARSER_BOUND_RELEASE_VERIFIED_EXECUTION_CLOSED","resources":8,"maximum_bytes":c["maximum_total_response_bytes"],"output_exists":out.exists(),"partial_exists":part.exists()}
if __name__=="__main__":print(json.dumps(verify(),ensure_ascii=False))
