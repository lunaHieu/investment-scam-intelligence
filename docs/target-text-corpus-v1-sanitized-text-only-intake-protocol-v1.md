# Sanitized Text-Only Intake Protocol V1

Only UTF-8 TXT, CSV, JSON and JSONL are eligible. HTML, scripts, SVG, active
documents and archives containing active content are forbidden. The parser must
run offline without rendering or following links. Every batch needs provenance,
terms, source version and hashes before parsing, plus a clean endpoint-security
scan. Any malware/PUA detection abandons the entire batch without restore or
whitelist.

Sanitization makes text inert but does not create labels. Evidence and content
remain separate; primary review, blind second review and reconciliation remain
mandatory. This protocol authorizes no acquisition or admission by itself.
