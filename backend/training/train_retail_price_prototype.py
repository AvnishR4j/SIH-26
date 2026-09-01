"""Train a clearly labelled generic-retail price prototype from UCI Online Retail II.

This script deliberately does not integrate its output into live price decisions.
It creates a compact baseline artifact and a metrics report that can later be
replaced by a validated Indian-artisan training set.
"""

from __future__ import annotations

import json
import pickle
from pathlib import Path
from zipfile import ZipFile

import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, root_mean_squared_error
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

BACKEND_DIR = Path(__file__).resolve().parents[1]
RAW_ARCHIVE = BACKEND_DIR / "data" / "raw" / "online_retail_ii.zip"
RAW_WORKBOOK = BACKEND_DIR / "data" / "raw" / "online_retail_ii.xlsx"
MODEL_DIR = BACKEND_DIR / "models"
MODEL_PATH = MODEL_DIR / "generic_retail_price_prototype.pkl"
REPORT_PATH = MODEL_DIR / "generic_retail_price_prototype.json"
RANDOM_STATE = 42
MAX_TRAINING_ROWS = 250_000


def load_transactions(archive_path: Path, workbook_path: Path) -> pd.DataFrame:
    if workbook_path.exists():
        return pd.read_excel(workbook_path, sheet_name=None).pipe(
            lambda sheets: pd.concat(sheets.values(), ignore_index=True)
        )
    if not archive_path.exists():
        raise FileNotFoundError(
            "Download the official UCI archive or workbook to "
            f"{archive_path.parent} before running this script."
        )
    with ZipFile(archive_path) as archive:
        spreadsheets = [name for name in archive.namelist() if name.lower().endswith(".xlsx")]
        if not spreadsheets:
            raise ValueError("The UCI archive did not contain an Excel workbook.")
        frames = [pd.read_excel(archive.open(name)) for name in spreadsheets]
    return pd.concat(frames, ignore_index=True)


def prepare_dataset(transactions: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series]:
    price_column = "UnitPrice" if "UnitPrice" in transactions.columns else "Price"
    required = {"Description", "Quantity", price_column, "Country"}
    missing = required.difference(transactions.columns)
    if missing:
        raise ValueError(f"Dataset is missing expected columns: {sorted(missing)}")

    cleaned = transactions.dropna(
        subset=["Description", "Quantity", price_column, "Country"]
    ).copy()
    cleaned = cleaned[(cleaned["Quantity"] > 0) & (cleaned[price_column] > 0)]
    cleaned["description"] = cleaned["Description"].astype(str).str.strip().str.lower()
    cleaned["country"] = cleaned["Country"].astype(str).str.strip()
    cleaned["quantity"] = cleaned["Quantity"].astype(float)
    target = cleaned[price_column].astype(float)
    features = cleaned[["description", "country", "quantity"]]
    if len(features) > MAX_TRAINING_ROWS:
        sampled = features.sample(n=MAX_TRAINING_ROWS, random_state=RANDOM_STATE)
        return sampled, target.loc[sampled.index]
    return features, target


def main() -> None:
    transactions = load_transactions(RAW_ARCHIVE, RAW_WORKBOOK)
    features, target = prepare_dataset(transactions)
    train_features, test_features, train_target, test_target = train_test_split(
        features, target, test_size=0.2, random_state=RANDOM_STATE
    )
    preprocessor = ColumnTransformer(
        transformers=[
            (
                "categorical",
                Pipeline(
                    steps=[
                        ("impute", SimpleImputer(strategy="most_frequent")),
                        (
                            "encode",
                            OneHotEncoder(handle_unknown="ignore", min_frequency=10),
                        ),
                    ]
                ),
                ["description", "country"],
            ),
            ("numeric", SimpleImputer(strategy="median"), ["quantity"]),
        ]
    )
    model = Pipeline(
        steps=[
            ("features", preprocessor),
            # A sparse-friendly baseline is deliberate: this dataset has many product descriptions.
            ("regressor", Ridge(alpha=1.0, solver="lsqr")),
        ]
    )
    model.fit(train_features, train_target)
    predictions = model.predict(test_features)

    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    with MODEL_PATH.open("wb") as artifact:
        pickle.dump(model, artifact)
    report = {
        "model_status": "prototype_only",
        "dataset": "UCI Online Retail II",
        "dataset_scope": "Historic UK retail transactions; not Indian handicrafts.",
        "rows_used": len(features),
        "features": ["description", "country", "quantity"],
        "target": "unit_price",
        "test_mean_absolute_error": round(
            float(mean_absolute_error(test_target, predictions)), 4
        ),
        "test_root_mean_squared_error": round(
            float(root_mean_squared_error(test_target, predictions)), 4
        ),
        "not_for": [
            "automatic price changes",
            "live material-rate prediction",
            "Indian artisan pricing claims",
        ],
        "calibration_required": [
            "verified KalaSetu artisan records",
            "dated material-rate sources",
            "human review before Shopify updates",
        ],
    }
    REPORT_PATH.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
