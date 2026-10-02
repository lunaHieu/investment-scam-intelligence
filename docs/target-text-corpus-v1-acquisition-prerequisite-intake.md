# Target Text Corpus V1 acquisition prerequisite intake

Status: **intake structure ready; both external inputs are still missing**.

This gate separates public, reproducible metadata from private access identity. It prevents an email address or other contact identity from being committed to the public repository while still making readiness auditable.

## What must be supplied later

### 1. CFTC RED reference artifact

Download the reference artifact manually, or use an explicit official download offered by CFTC, and place the untouched file under:

`D:\nckh 2026-2027\ISI_Data\raw\cftc_red_list\`

Do not rename, convert, clean, or overwrite it before registration. When it exists, the project will record its exact path, byte SHA-256, acquisition time, format, and record count. The artifact is reference provenance only: RED List inclusion does not itself prove fraud or a legal violation.

### 2. SEC EDGAR User-Agent identity

The private file location is:

`D:\nckh 2026-2027\ISI_Data\private\sec_edgar_user_agent_v1.json`

It will eventually contain only these locally held fields:

```json
{
  "organization_or_project": "truthful project or organization name",
  "contact_email": "monitored contact email",
  "purpose": "academic investment-scam intelligence research"
}
```

Do not commit this file or paste its contents into a registry. A future readiness registry may state only that a valid private file exists; it must not reveal the identity, email, or private-file hash. SEC access remains limited to documented API/bulk endpoints, one request per second for this project, with immediate stop on HTTP 429 or a policy change.

## Files created now

- Public JSON Schema for the two-entry readiness ledger.
- Public example ledger containing no contact identity.
- Local ledger at `D:\nckh 2026-2027\ISI_Data\governance\target_text_corpus_v1\acquisition_prerequisite_ledger_v1.json`.
- Empty storage directories for the CFTC artifact and private SEC configuration.

The local ledger currently records both entries as `MISSING`. Therefore the balanced enumeration wave, all network execution, captures, labels, training, validation, and test remain blocked.
