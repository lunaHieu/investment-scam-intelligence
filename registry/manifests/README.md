# Download Manifests

Create one immutable manifest per acquired source batch. The manifest file itself is safe to commit if it contains no credentials, personal data or raw record content.

Example file name: `mendeley_investment_deceptive_2026__v2__2026-09-07.json`.

The required shape is defined in `../../schemas/source_manifest.schema.json`. A future acquisition command must calculate a SHA-256 for every raw file, record a UTC timestamp and write the concrete source version before any parsing begins.
