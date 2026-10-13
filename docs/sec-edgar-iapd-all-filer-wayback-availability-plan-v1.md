# SEC EDGAR/IAPD all-filer Wayback availability plan V1

## Step name

Create a bounded, disjoint, no-network Wayback availability plan.

## Meaning

The plan includes only rows whose offline identity review recommends `ADVANCE_TO_CAPTURE_PLANNING_REVIEW`. All 19 ambiguous related-name cautions remain excluded. Development and external holdout retain separate IDs and namespaces, and no host may occur in both cohorts.

Each row fixes the candidate URL, normalized host, target timestamp, and fully encoded future archive-availability request URL. This is a plan artifact only: materializing it performs no request. Future execution, if separately released, may contact only the Wayback availability endpoint and may not access a live candidate domain or download archived HTML.

Availability is not a label. A snapshot result cannot by itself prove that a website is legitimate, fraudulent, or suitable for the text task.

## Result

The frozen plan contains 115 unique hosts: 91 development and 24 external holdout. All 19 identity-caution rows are excluded, cross-cohort host overlap is zero, and every encoded request decodes back to the exact frozen candidate URL and target date `20261003`. Independent verification passed. Network requests executed: zero.
