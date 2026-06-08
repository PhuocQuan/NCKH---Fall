from __future__ import annotations

import argparse
from pathlib import Path

import joblib
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report, confusion_matrix
from sklearn.model_selection import train_test_split

from src.feature_extractor import FEATURE_NAMES


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train an AI fall classifier from feature CSV.")
    parser.add_argument("--csv", required=True, help="Training CSV path.")
    parser.add_argument("--output", default="models/fall_classifier.joblib", help="Output model path.")
    parser.add_argument("--label-column", default="label", help="Label column name.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    data = pd.read_csv(args.csv)
    missing = [name for name in FEATURE_NAMES + [args.label_column] if name not in data.columns]
    if missing:
        raise ValueError(f"CSV thieu cot: {', '.join(missing)}")

    x = data[FEATURE_NAMES]
    y = data[args.label_column]
    x_train, x_test, y_train, y_test = train_test_split(
        x,
        y,
        test_size=0.2,
        random_state=42,
        stratify=y,
    )

    model = RandomForestClassifier(
        n_estimators=200,
        max_depth=8,
        class_weight="balanced",
        random_state=42,
    )
    model.fit(x_train, y_train)

    predictions = model.predict(x_test)
    print(classification_report(y_test, predictions))
    print(confusion_matrix(y_test, predictions))

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, output)
    print(f"Saved model to {output}")


if __name__ == "__main__":
    main()
