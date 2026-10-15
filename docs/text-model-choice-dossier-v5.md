# Text model choice dossier V5

## Step and meaning

This is workstream P7. It answers which kind of model fits the project at its current data maturity without fitting, scoring, tuning, or opening another partition. “Stronger” is treated as better verified generalization, not simply more parameters.

## Evidence

The current text evidence is heterogeneous and strongly source-shaped. On the frozen 3,916-row / 3,783-group train-only OOF comparison, the word TF-IDF linear reference reached pooled Macro-F1 0.721038. The frozen E5-small-v2 embedding plus linear classifier reached 0.689907, declined on every source, and failed all six development gates. Its nearest-neighbor structure was 94.51% same-source, supporting source/style geometry as the main unresolved problem. Character augmentation and stop-word style guards had already failed their own promotion gates.

The failure is therefore not evidence that transformers are generally weak. It is evidence that adding semantic model capacity did not fix this dataset's source/label geometry under the exact tested protocol.

The intended V1-Core corpus is also not ready for model selection. The diagnostic target-text pilot has only 15 decisive owner-accepted labels and 7 `UNCERTAIN`; none is training-eligible. Verified Vietnamese supply is zero against a minimum of eight `CONFIRMED` and eight `LEGITIMATE` groups. Mendeley contains no usable image assets.

## Model-family decision

| Model family | Current role | Decision | Reason |
| --- | --- | --- | --- |
| Word TF-IDF + regularized logistic regression | Reproducible text reference | Retain as internal champion; do not deploy | It remains the strongest frozen development reference and is cheap, interpretable, and auditable, but source robustness is inadequate |
| Character or word+character sparse model | Stress test only | Retired on the current partition | It missed its promotion threshold and increased source predictability |
| Stop-word/style-guard sparse model | Stress test only | Retired on the current partition | It reduced pooled and worst-source performance and failed all confirmation gates |
| Frozen E5 embedding + linear classifier | Completed semantic challenger | Rejected | It underperformed on every source and failed all six gates |
| Fine-tuned multilingual encoder | Future controlled hypothesis | Deferred | There is no verified Vietnamese training supply and no completed V1-Core development split |
| Large generative model as the binary classifier | None | Not appropriate now | Harder to reproduce and calibrate; current bottleneck is evidence/data geometry rather than model capacity |
| AI agent | Workflow assistant only | Use for acquisition bookkeeping, QA, bounded evidence summaries, and packet preparation | An agent may orchestrate tools but must not become ground truth or silently replace human/independent review |
| Image or multimodal model | None | Blocked | No compatible image assets exist |

## Recommended architecture by phase

### Current phase

Keep the word TF-IDF logistic model as a frozen reference only. Continue data acquisition, grouping, provenance, and review. Use AI agents for reproducible workflow automation with hash-bound outputs and explicit gates, not for autonomous labels.

### After V1-Core readiness

Only after a fresh grouped development corpus and untouched external holdout are frozen, run a new predeclared comparison:

1. sparse word baseline;
2. one exact multilingual encoder revision with a regularized linear head;
3. optionally, one fully specified fine-tuning protocol if sample size, class/channel balance, Vietnamese coverage, and compute budget justify it.

All three must use group-disjoint folds, source/channel robustness metrics, abstention/uncertainty analysis, and a frozen promotion rule. Existing opened cohorts cannot be reused to choose architecture or hyperparameters.

### Deployment-oriented research

Prefer a bounded system: classifier score plus an `UNCERTAIN` route, evidence retrieval, and human review. An AI agent can coordinate those components, but the classification core and its decision thresholds must remain versioned, testable, and independently auditable.

## Bottom line

The appropriate model today is the “weaker” sparse linear baseline because it is the best supported reference, not because it is deployment-ready. A stronger multilingual encoder may become appropriate only after the data gates are met. A large AI agent should support the pipeline, not replace the classifier, reviewer, or evidence policy.
