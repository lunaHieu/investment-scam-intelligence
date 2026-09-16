"""Run reproducible unlabeled clustering and outlier ranking for Crimson domains.

Only precomputed offline lexical features are used. No DNS, HTTP, WHOIS,
certificate, reputation or page-content lookup is performed. Outputs are
review-priority artifacts, never scam predictions or training labels.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from sklearn.cluster import MiniBatchKMeans
from sklearn.decomposition import PCA
from sklearn.ensemble import IsolationForest
from sklearn.metrics import (
    adjusted_rand_score,
    calinski_harabasz_score,
    davies_bouldin_score,
    silhouette_score,
)
from sklearn.preprocessing import StandardScaler


ANALYSIS_VERSION = "CRIMSON_DOMAIN_UNSUPERVISED_V1"
RANDOM_SEED = 20260914
K_CANDIDATES = (4, 6, 8, 10, 12, 16)
COUNT_FEATURES = {
    "domain_length", "label_count", "subdomain_depth_naive", "rightmost_label_length",
    "longest_label_length", "mean_label_length", "letter_count", "digit_count",
    "hyphen_count", "non_ascii_count", "digit_letter_transition_count",
    "longest_digit_run", "longest_letter_run", "punycode_label_count",
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_features(path: Path) -> tuple[list[dict], list[str], np.ndarray]:
    records = []
    feature_names = None
    seen_artifacts = set()
    seen_domains = set()
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            record = json.loads(line)
            artifact_id = record.get("artifact_id")
            domain = record.get("domain")
            features = record.get("features")
            if record.get("feature_version") != "CRIMSON_URL_LEXICAL_V1":
                raise ValueError(f"line {line_number}: unexpected feature_version")
            if artifact_id in seen_artifacts or domain in seen_domains:
                raise ValueError(f"line {line_number}: duplicate artifact or domain")
            if not isinstance(features, dict) or not features:
                raise ValueError(f"line {line_number}: missing features")
            current_names = sorted(features)
            if feature_names is None:
                feature_names = current_names
            elif current_names != feature_names:
                raise ValueError(f"line {line_number}: inconsistent feature keys")
            values = [float(features[name]) for name in current_names]
            if not all(math.isfinite(value) for value in values):
                raise ValueError(f"line {line_number}: non-finite feature value")
            records.append(record)
            seen_artifacts.add(artifact_id)
            seen_domains.add(domain)
    if not records or feature_names is None:
        raise ValueError("feature input is empty")
    matrix = np.asarray(
        [[float(record["features"][name]) for name in feature_names] for record in records],
        dtype=np.float64,
    )
    return records, feature_names, matrix


def preprocess(matrix: np.ndarray, feature_names: list[str]):
    transformed = matrix.copy()
    for index, name in enumerate(feature_names):
        if name in COUNT_FEATURES:
            if np.any(transformed[:, index] < 0):
                raise ValueError(f"count feature {name} contains a negative value")
            transformed[:, index] = np.log1p(transformed[:, index])
    variances = np.var(transformed, axis=0)
    active_indices = [index for index, value in enumerate(variances) if value > 1e-12]
    dropped_indices = [index for index, value in enumerate(variances) if value <= 1e-12]
    active_names = [feature_names[index] for index in active_indices]
    dropped_names = [feature_names[index] for index in dropped_indices]
    scaler = StandardScaler()
    scaled = scaler.fit_transform(transformed[:, active_indices])
    pca = PCA(n_components=0.95, svd_solver="full")
    reduced = pca.fit_transform(scaled)
    return scaled, reduced, active_names, dropped_names, scaler, pca


def fit_cluster_candidates(reduced: np.ndarray) -> tuple[list[dict], MiniBatchKMeans, np.ndarray]:
    candidates = []
    best = None
    for cluster_count in K_CANDIDATES:
        model = MiniBatchKMeans(
            n_clusters=cluster_count,
            random_state=RANDOM_SEED,
            batch_size=2048,
            n_init=10,
        )
        labels = model.fit_predict(reduced)
        candidate = {
            "cluster_count": cluster_count,
            "silhouette": round(float(silhouette_score(
                reduced, labels, sample_size=min(5000, len(reduced)), random_state=RANDOM_SEED
            )), 6),
            "davies_bouldin": round(float(davies_bouldin_score(reduced, labels)), 6),
            "calinski_harabasz": round(float(calinski_harabasz_score(reduced, labels)), 6),
            "inertia": round(float(model.inertia_), 6),
        }
        candidates.append(candidate)
        score = (candidate["silhouette"], -candidate["davies_bouldin"], candidate["calinski_harabasz"])
        if best is None or score > best[0]:
            best = (score, model, labels)
    assert best is not None
    return candidates, best[1], best[2]


def stability_scores(reduced: np.ndarray, base_labels: np.ndarray, cluster_count: int) -> list[dict]:
    results = []
    for seed in (20260915, 20260916, 20260917, 20260918):
        model = MiniBatchKMeans(
            n_clusters=cluster_count,
            random_state=seed,
            batch_size=2048,
            n_init=10,
        )
        labels = model.fit_predict(reduced)
        results.append({
            "seed": seed,
            "adjusted_rand_index_vs_selected": round(float(adjusted_rand_score(base_labels, labels)), 6),
        })
    return results


def select_review_queue(
    records: list[dict],
    labels: np.ndarray,
    anomaly_scores: np.ndarray,
    distances: np.ndarray,
    outlier_count: int = 50,
    representative_count: int = 50,
) -> list[dict]:
    outlier_indices = list(np.argsort(-anomaly_scores)[:outlier_count])
    selected = set(outlier_indices)
    cluster_ids = sorted(set(map(int, labels)))
    base, remainder = divmod(representative_count, len(cluster_ids))
    representative_indices = []
    for position, cluster_id in enumerate(cluster_ids):
        quota = base + int(position < remainder)
        candidates = [
            index for index in range(len(records))
            if int(labels[index]) == cluster_id and index not in selected
        ]
        candidates.sort(key=lambda index: (float(distances[index]), records[index]["artifact_id"]))
        chosen = candidates[:quota]
        representative_indices.extend(chosen)
        selected.update(chosen)
    if len(representative_indices) < representative_count:
        remaining = [index for index in range(len(records)) if index not in selected]
        remaining.sort(key=lambda index: (float(distances[index]), records[index]["artifact_id"]))
        representative_indices.extend(remaining[: representative_count - len(representative_indices)])

    queue = []
    anomaly_order = np.argsort(-anomaly_scores)
    anomaly_rank = np.empty(len(records), dtype=np.int64)
    anomaly_rank[anomaly_order] = np.arange(1, len(records) + 1)
    for index in outlier_indices:
        queue.append({
            "artifact_id": records[index]["artifact_id"],
            "domain": records[index]["domain"],
            "cluster_id": int(labels[index]),
            "queue_reason": "LEXICAL_OUTLIER",
            "anomaly_rank": int(anomaly_rank[index]),
            "anomaly_score": round(float(anomaly_scores[index]), 8),
            "distance_to_cluster_center": round(float(distances[index]), 8),
            "features": records[index]["features"],
            "review_status": "UNREVIEWED",
            "interpretation": "Review-priority candidate only; not a scam label.",
        })
    for index in representative_indices[:representative_count]:
        queue.append({
            "artifact_id": records[index]["artifact_id"],
            "domain": records[index]["domain"],
            "cluster_id": int(labels[index]),
            "queue_reason": "CLUSTER_REPRESENTATIVE",
            "anomaly_rank": int(anomaly_rank[index]),
            "anomaly_score": round(float(anomaly_scores[index]), 8),
            "distance_to_cluster_center": round(float(distances[index]), 8),
            "features": records[index]["features"],
            "review_status": "UNREVIEWED",
            "interpretation": "Review-priority candidate only; not a scam label.",
        })
    return queue


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    records, feature_names, matrix = load_features(args.input)
    scaled, reduced, active_names, dropped_names, _, pca = preprocess(matrix, feature_names)
    candidates, cluster_model, labels = fit_cluster_candidates(reduced)
    cluster_count = int(cluster_model.n_clusters)
    stability = stability_scores(reduced, labels, cluster_count)

    isolation = IsolationForest(
        n_estimators=300,
        max_samples=min(2048, len(records)),
        contamination="auto",
        random_state=RANDOM_SEED,
        n_jobs=-1,
    )
    isolation.fit(reduced)
    anomaly_scores = -isolation.score_samples(reduced)
    distances_to_all_centers = cluster_model.transform(reduced)
    assigned_distances = distances_to_all_centers[np.arange(len(records)), labels]

    cluster_profiles = []
    for cluster_id in range(cluster_count):
        indices = np.where(labels == cluster_id)[0]
        feature_means = np.mean(scaled[indices], axis=0)
        top_indices = np.argsort(-np.abs(feature_means))[:5]
        cluster_profiles.append({
            "cluster_id": cluster_id,
            "record_count": int(len(indices)),
            "record_ratio": round(float(len(indices) / len(records)), 6),
            "top_standardized_feature_means": [
                {"feature": active_names[index], "mean_z": round(float(feature_means[index]), 6)}
                for index in top_indices
            ],
        })

    queue = select_review_queue(records, labels, anomaly_scores, assigned_distances)
    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    assignments_path = output_dir / "domain_assignments.jsonl"
    queue_path = output_dir / "review_queue_100.jsonl"
    report_path = output_dir / "analysis_report.json"

    anomaly_order = np.argsort(-anomaly_scores)
    anomaly_rank = np.empty(len(records), dtype=np.int64)
    anomaly_rank[anomaly_order] = np.arange(1, len(records) + 1)
    with assignments_path.open("w", encoding="utf-8", newline="\n") as handle:
        for index, record in enumerate(records):
            handle.write(json.dumps({
                "artifact_id": record["artifact_id"],
                "domain": record["domain"],
                "analysis_version": ANALYSIS_VERSION,
                "cluster_id": int(labels[index]),
                "anomaly_rank": int(anomaly_rank[index]),
                "anomaly_score": round(float(anomaly_scores[index]), 8),
                "distance_to_cluster_center": round(float(assigned_distances[index]), 8),
                "interpretation": "Unlabeled structural analysis only; not a scam prediction.",
            }, ensure_ascii=False, separators=(",", ":")) + "\n")
    with queue_path.open("w", encoding="utf-8", newline="\n") as handle:
        for item in queue:
            handle.write(json.dumps(item, ensure_ascii=False, separators=(",", ":")) + "\n")

    ari_values = [item["adjusted_rand_index_vs_selected"] for item in stability]
    top_one_percent_count = max(1, math.ceil(len(records) * 0.01))
    top_one_percent_cutoff = float(np.sort(anomaly_scores)[-top_one_percent_count])
    report = {
        "run_at": datetime.now(timezone.utc).isoformat(),
        "analysis_version": ANALYSIS_VERSION,
        "input": str(args.input),
        "input_sha256": sha256_file(args.input),
        "record_count": len(records),
        "input_feature_count": len(feature_names),
        "active_feature_count": len(active_names),
        "active_features": active_names,
        "dropped_constant_features": dropped_names,
        "preprocessing": {
            "count_features": "log1p",
            "scaling": "StandardScaler fit on the full unlabeled feature set",
            "dimension_reduction": "PCA retaining 95% variance",
            "pca_component_count": int(reduced.shape[1]),
            "pca_explained_variance_ratio_sum": round(float(np.sum(pca.explained_variance_ratio_)), 6),
        },
        "cluster_selection": {
            "candidates": candidates,
            "selection_rule": "Highest sampled silhouette; Davies-Bouldin then Calinski-Harabasz as tie-breakers.",
            "selected_cluster_count": cluster_count,
            "cluster_profiles": cluster_profiles,
        },
        "stability": {
            "runs": stability,
            "mean_adjusted_rand_index": round(float(np.mean(ari_values)), 6),
            "minimum_adjusted_rand_index": round(float(np.min(ari_values)), 6),
            "interpretation": "ARI near 1 indicates stable assignments; low ARI means clusters are exploratory and seed-sensitive.",
        },
        "outlier_ranking": {
            "method": "IsolationForest on PCA representation",
            "n_estimators": 300,
            "max_samples": min(2048, len(records)),
            "top_one_percent_count": top_one_percent_count,
            "top_one_percent_score_cutoff": round(top_one_percent_cutoff, 8),
            "interpretation": "Higher score means lexically unusual within Crimson, not more likely to be a scam.",
        },
        "review_queue": {
            "record_count": len(queue),
            "reason_counts": dict(Counter(item["queue_reason"] for item in queue)),
            "unique_domain_count": len({item["domain"] for item in queue}),
            "policy": "50 highest lexical outliers plus 50 closest cluster representatives; no website access.",
        },
        "outputs": {
            "assignments": str(assignments_path),
            "assignments_sha256": sha256_file(assignments_path),
            "review_queue": str(queue_path),
            "review_queue_sha256": sha256_file(queue_path),
        },
        "network_operations": 0,
        "labels_created": 0,
        "training_allowed": False,
        "limitations": [
            "All records originate from Crimson, so clusters describe within-source structure only.",
            "K-means favors roughly spherical separation in the transformed space.",
            "Outlier scores are relative to this snapshot and have no fraud-probability meaning.",
            "No public-suffix, temporal, DNS, content or evidence signal is included.",
        ],
    }
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "record_count": len(records),
        "selected_cluster_count": cluster_count,
        "cluster_sizes": {str(item["cluster_id"]): item["record_count"] for item in cluster_profiles},
        "mean_stability_ari": report["stability"]["mean_adjusted_rand_index"],
        "review_queue": report["review_queue"],
        "network_operations": 0,
        "labels_created": 0,
        "outputs": {"report": str(report_path), "assignments": str(assignments_path), "queue": str(queue_path)},
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
