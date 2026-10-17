# SEC EDGAR/IAPD Wayback Availability Retry V6

Date: 2026-10-17  
Status: frozen, independently verified, cooldown active

V6 preserves all 107 resolved V5 rows and may retry only the eight V5 errors. The release cannot execute before `2026-10-18T08:47:59.207293+07:00`, exactly 24 hours after the V5 report creation time.

The executor permits one request per unresolved candidate, a minimum 60-second delay, immediate stop on HTTP 429, no output overwrite, and only the archive availability endpoint. Network/DNS errors remain unresolved and cannot be interpreted as unavailable snapshots.

Capture planning, archived-page download, candidate live-domain access, labeling, training, scoring, validation, and test access remain closed.

Independent release QA passed with 115 plan rows, 107 preserved resolved rows, eight retry rows, a full 86,400-second cooldown, and zero network operations during preparation.
