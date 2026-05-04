"""
Risk Classifier Training Pipeline
──────────────────────────────────
Trains a multi-label risk classifier on sentence embeddings.

Architecture:
  Input:  clause text → all-MiniLM-L6-v2 embedding (384-dim)
  Model:  5 independent LogisticRegression classifiers (one per risk category)
  Output: per-category severity prediction (None / Low / Medium / High)

The model replaces the hardcoded regex rules in risk_analyzer.py while
keeping the same output interface (category + severity per clause).

Usage:
    python -m scripts.train_risk_classifier
"""
import json
import logging
import pickle
import sys
import time
from pathlib import Path

import numpy as np

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATASET_PATH = PROJECT_ROOT / "data" / "training" / "risk_dataset.json"
MODEL_PATH = PROJECT_ROOT / "data" / "models" / "risk_classifier.pkl"

CATEGORIES = [
    "Compliance Risk",
    "Liability Risk",
    "Privacy/Data Risk",
    "Financial Risk",
    "Contractual Ambiguity",
]

SEVERITY_CLASSES = ["None", "Low", "Medium", "High"]


def load_dataset():
    """Load the training dataset and extract texts + label matrices."""
    with open(DATASET_PATH) as f:
        data = json.load(f)

    texts = [d["text"] for d in data]

    # Build label matrix: (n_samples, n_categories) with severity strings
    labels = []
    for d in data:
        row = []
        for cat in CATEGORIES:
            sev = d["labels"].get(cat)
            row.append(sev if sev is not None else "None")
        labels.append(row)

    return texts, np.array(labels)


def encode_texts(texts):
    """Encode texts using the same MiniLM model used in production."""
    sys.path.insert(0, str(PROJECT_ROOT))
    from backend.models.embeddings import encode as embed_encode, is_available

    if not is_available():
        raise RuntimeError("Embedding model not available. Install sentence-transformers.")

    log.info(f"Encoding {len(texts)} texts with MiniLM-L6-v2...")
    t0 = time.monotonic()
    embeddings = embed_encode(texts, normalize=True)
    elapsed = time.monotonic() - t0
    log.info(f"Encoded in {elapsed:.1f}s → shape {embeddings.shape}")
    return embeddings


def train_and_evaluate(X, y_matrix, test_size=0.2, seed=42):
    """
    Train per-category classifiers with cross-validated hyperparameter
    selection and a final held-out test evaluation.
    """
    from sklearn.model_selection import train_test_split, StratifiedKFold, cross_val_score
    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import LabelEncoder
    from sklearn.metrics import classification_report, f1_score

    # Stratified split — use the first category's labels for stratification
    primary_labels = y_matrix[:, 0]
    X_train, X_test, y_train, y_test = train_test_split(
        X, y_matrix, test_size=test_size, random_state=seed, stratify=primary_labels
    )

    log.info(f"Train: {len(X_train)} | Test: {len(X_test)}")

    classifiers = {}
    encoders = {}
    metrics = {}

    for i, cat in enumerate(CATEGORIES):
        log.info(f"\n{'─' * 50}")
        log.info(f"Training: {cat}")

        y_col_train = y_train[:, i]
        y_col_test = y_test[:, i]

        # Encode labels
        le = LabelEncoder()
        le.fit(SEVERITY_CLASSES)
        y_enc_train = le.transform(y_col_train)
        y_enc_test = le.transform(y_col_test)

        # Hyperparameter search over C values using cross-validation
        best_c, best_cv_score = 1.0, 0.0
        for c_val in [0.1, 0.5, 1.0, 5.0, 10.0]:
            clf_trial = LogisticRegression(
                max_iter=2000, C=c_val, class_weight="balanced",
                random_state=seed, solver="lbfgs",
            )
            cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=seed)
            scores = cross_val_score(clf_trial, X_train, y_enc_train, cv=cv,
                                     scoring="f1_macro")
            mean_score = scores.mean()
            if mean_score > best_cv_score:
                best_cv_score = mean_score
                best_c = c_val

        log.info(f"  Best C={best_c} (CV macro F1={best_cv_score:.3f})")

        # Train final classifier with best C on full training set
        clf = LogisticRegression(
            max_iter=2000,
            C=best_c,
            class_weight="balanced",
            random_state=seed,
            solver="lbfgs",
        )
        clf.fit(X_train, y_enc_train)

        # Evaluate on held-out test set
        y_pred = clf.predict(X_test)
        y_pred_labels = le.inverse_transform(y_pred)
        y_true_labels = le.inverse_transform(y_enc_test)

        # Per-class report
        report = classification_report(
            y_true_labels, y_pred_labels,
            labels=SEVERITY_CLASSES,
            zero_division=0,
            output_dict=True,
        )

        # Binary detection: did the model correctly identify "has risk" vs "no risk"?
        y_binary_true = (y_col_test != "None").astype(int)
        y_binary_pred = (y_pred_labels != "None").astype(int)
        detection_f1 = f1_score(y_binary_true, y_binary_pred, zero_division=0)

        # Macro F1 across all severity classes
        macro_f1 = f1_score(y_enc_test, y_pred, average="macro", zero_division=0)

        metrics[cat] = {
            "detection_f1": round(detection_f1, 3),
            "severity_macro_f1": round(macro_f1, 3),
            "best_C": best_c,
            "cv_score": round(best_cv_score, 3),
            "report": report,
        }

        log.info(f"  Detection F1 (risk vs no-risk): {detection_f1:.3f}")
        log.info(f"  Severity macro F1:              {macro_f1:.3f}")

        # Print confusion summary
        for cls in ["High", "Medium", "Low"]:
            if cls in report and report[cls]["support"] > 0:
                log.info(f"    {cls}: P={report[cls]['precision']:.2f} R={report[cls]['recall']:.2f} F1={report[cls]['f1-score']:.2f} (n={report[cls]['support']})")

        classifiers[cat] = clf
        encoders[cat] = le

    return classifiers, encoders, metrics, (X_train, X_test, y_train, y_test)


def save_model(classifiers, encoders, metrics):
    """Save the trained model bundle."""
    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)

    bundle = {
        "classifiers": classifiers,
        "encoders": encoders,
        "categories": CATEGORIES,
        "severity_classes": SEVERITY_CLASSES,
        "metrics": metrics,
        "version": "1.0",
    }

    with open(MODEL_PATH, "wb") as f:
        pickle.dump(bundle, f)

    size_kb = MODEL_PATH.stat().st_size / 1024
    log.info(f"\nModel saved to {MODEL_PATH} ({size_kb:.1f} KB)")


def main():
    print("=" * 60)
    print("RISK CLASSIFIER TRAINING")
    print("=" * 60)

    # Load data
    texts, y_matrix = load_dataset()
    log.info(f"Dataset: {len(texts)} examples, {len(CATEGORIES)} categories")

    # Encode
    X = encode_texts(texts)

    # Train and evaluate
    classifiers, encoders, metrics, splits = train_and_evaluate(X, y_matrix)

    # Summary
    print("\n" + "=" * 60)
    print("RESULTS SUMMARY")
    print("=" * 60)

    detection_f1s = []
    severity_f1s = []
    for cat in CATEGORIES:
        m = metrics[cat]
        detection_f1s.append(m["detection_f1"])
        severity_f1s.append(m["severity_macro_f1"])
        print(f"  {cat}:")
        print(f"    Detection F1:     {m['detection_f1']:.3f}")
        print(f"    Severity macro F1: {m['severity_macro_f1']:.3f}")

    avg_det = sum(detection_f1s) / len(detection_f1s)
    avg_sev = sum(severity_f1s) / len(severity_f1s)
    print(f"\n  Average detection F1:     {avg_det:.3f}")
    print(f"  Average severity macro F1: {avg_sev:.3f}")

    # Save
    save_model(classifiers, encoders, metrics)

    print("=" * 60)


if __name__ == "__main__":
    main()
