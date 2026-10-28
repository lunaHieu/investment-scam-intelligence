# Project Direction Plan R15

Date: 2026-10-29

The owner permanently abandoned the raw-HTML branch after endpoint security
detected a severe Trojan. No restoration, whitelist, sandbox transfer, raw
verification, extraction or retry is permitted. Only metadata/report audit
records remain usable.

The next data path is text-only: inventory existing safe text corpora, define a
sanitization and provenance gate, then admit only text artifacts that pass
independent schema, deduplication, leakage and evidence review. Detection or
quarantine must never become a class label.
