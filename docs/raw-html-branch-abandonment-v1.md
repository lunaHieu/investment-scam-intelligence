# Raw HTML Branch Abandonment V1

Date: 2026-10-29

Owner decision: abandon the entire raw-HTML acquisition and processing branch
after Microsoft Defender detected a severe HTML Trojan.

Binding consequences:

- never restore the quarantined artifact;
- never add a Defender exclusion or whitelist;
- never open, parse, extract, transfer, package or otherwise process any raw
  HTML captured by this branch on this workstation or another environment;
- never retry the abandoned raw replay population;
- retain only non-executable metadata, reports, hashes and audit records;
- do not infer labels from availability, capture outcome, quarantine or malware
  detection;
- redirect future corpus work to independently reviewed, text-only sources that
  are sanitized before entering the project.

This decision closes the raw-byte QA, exact-text extraction and grouping path
for the abandoned artifacts. Existing raw files are not restored or accessed by
this decision; operating-system security controls remain authoritative.
