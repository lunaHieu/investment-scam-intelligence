# Text Baseline V2 – Wayback holdout V3 error analysis

## Scope

This is one frozen diagnostic pass over all 30 V3 predictions, the eight errors, and the eleven records within 0.10 of the fixed 0.50 threshold. It performs no fit, threshold change, feature selection, relabeling, or re-scoring after inspection.

The model and split hashes are verified before analysis. Nearest-neighbor comparison uses only the 4,754 train+validation rows that were already used to fit the frozen model. The internal test, auxiliary, and quarantine partitions are not loaded or transformed.

## Main findings

- Five of eight errors are within 0.10 of the fixed threshold; eleven of all 30 records are in this near-threshold band.
- False positives remain more common than false negatives: five versus three.
- Generic direct-address and marketing terms such as `your`, `you`, `our`, `security`, and `future` repeatedly push legitimate advisory pages toward label 1.
- Conventional trading language such as `trade`, `markets`, `forex`, `management`, and `capital` can push warned trading pages toward label 0.
- The nearest frozen fit row comes from `spam_email` for 19/30 records and 6/8 errors. Similarities are low, so these are weak style analogies rather than close semantic matches.
- Descriptive calibration remains limited (Brier score `0.179321`, ten-bin ECE `0.196744`) and is defined against source labels, not verified real-world fraud outcomes.

## Interpretation

The model transfers better to V3 than to the opened V2 benchmark at the aggregate level, but the error structure still reflects the mixed-source training corpus. It often treats marketing or direct-address style as suspicious and some conventional finance vocabulary as legitimate. These associations explain model behavior; they are not fraud evidence and must not become decision rules.

The V3 result and this diagnostic are now opened. They cannot be used to tune a challenger and then be reported again as independent evaluation. Any future representation hypothesis must be declared first, developed only on eligible train/validation data, and tested on a new untouched external cohort.

## Reproduction

```powershell
.\.venv\Scripts\python.exe scripts\verify_text_baseline_v2_wayback_holdout_v3_error_analysis.py --registry registry\analyses\text_baseline_v2_wayback_holdout_v3_error_analysis.json
```
