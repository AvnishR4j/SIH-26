# Price-model prototype

This folder contains the reproducible first-stage ML prototype for KalaSetu pricing.

It uses UCI Online Retail II only to exercise the data and model pipeline. The data
describes historic UK online retail transactions, not Indian handicrafts. Therefore,
the model output must be treated as a generic comparison signal and must not replace
the cost-based minimum price or be labelled as a live artisan-market price.

## Run locally

1. Install training-only dependencies with `python -m pip install -r requirements-ml.txt`.
2. Download the official archive into `backend/data/raw/online_retail_ii.zip`.
   An equivalent `.xlsx` workbook may instead be placed at
   `backend/data/raw/online_retail_ii.xlsx` when a trusted transfer mirror is needed.
3. Run `python training/train_retail_price_prototype.py` from `backend/`.
4. The generated model report and artifact are written to `backend/models/`.

The next calibration phase requires verified KalaSetu artisan records with product
type, material, dimensions or weight, labour hours, direct costs, selling price, date,
and location. The production price recommendation remains the transparent formula
until that calibration is validated.
