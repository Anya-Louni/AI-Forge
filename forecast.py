"""
forecast.py
-----------
Trains a demand forecasting model on warehouse_orders.csv and predicts
order volume for the next N days, per shift and zone.

Uses scikit-learn only (no Prophet/extra installs needed) so it runs
anywhere with pandas + scikit-learn installed.

Run:
    python3 forecast.py
Requires:
    warehouse_orders.csv (from generate_data.py, or your own real data
    with the same columns: date, shift, zone, orders)
"""

import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error

FORECAST_DAYS = 14  # how many days ahead to predict


def add_time_features(df):
    df = df.copy()
    df["date"] = pd.to_datetime(df["date"])
    df["day_of_week"] = df["date"].dt.dayofweek
    df["day_of_year"] = df["date"].dt.dayofyear
    df["week_of_year"] = df["date"].dt.isocalendar().week.astype(int)
    df["month"] = df["date"].dt.month
    df["days_since_start"] = (df["date"] - df["date"].min()).dt.days
    return df


def build_model(df):
    df = add_time_features(df)

    # one-hot encode categorical columns (shift, zone)
    df_enc = pd.get_dummies(df, columns=["shift", "zone"])

    feature_cols = [c for c in df_enc.columns
                     if c not in ["date", "weekday", "orders", "is_spike_day"]]

    X = df_enc[feature_cols]
    y = df_enc["orders"]

    # train/test split by time (last 14 days = test set) — avoids leakage
    split_date = df["date"].max() - pd.Timedelta(days=FORECAST_DAYS)
    train_mask = df["date"] <= split_date

    model = RandomForestRegressor(
        n_estimators=300, max_depth=12, random_state=42, n_jobs=-1
    )
    model.fit(X[train_mask], y[train_mask])

    # quick accuracy check on held-out days
    preds_test = model.predict(X[~train_mask])
    mae = mean_absolute_error(y[~train_mask], preds_test)
    print(f"Validation MAE (avg error per row): {mae:.1f} orders")

    return model, feature_cols, df["shift"].unique(), df["zone"].unique()


def forecast_future(model, feature_cols, shifts, zones, last_date):
    future_dates = pd.date_range(
        last_date + pd.Timedelta(days=1), periods=FORECAST_DAYS, freq="D"
    )

    rows = []
    for date in future_dates:
        for shift in shifts:
            for zone in zones:
                rows.append({"date": date, "shift": shift, "zone": zone})

    future_df = pd.DataFrame(rows)
    future_feat = add_time_features(future_df)
    future_enc = pd.get_dummies(future_feat, columns=["shift", "zone"])

    # make sure future_enc has exactly the same columns as training data
    for col in feature_cols:
        if col not in future_enc.columns:
            future_enc[col] = 0
    future_enc = future_enc[feature_cols]

    preds = model.predict(future_enc)
    future_df["forecast_orders"] = np.round(preds).astype(int)
    return future_df


if __name__ == "__main__":
    df = pd.read_csv("warehouse_orders.csv")
    model, feature_cols, shifts, zones = build_model(df)

    last_date = pd.to_datetime(df["date"]).max()
    forecast_df = forecast_future(model, feature_cols, shifts, zones, last_date)

    forecast_df.to_csv("forecast_output.csv", index=False)
    print(f"\nForecast saved -> forecast_output.csv ({len(forecast_df)} rows)")
    print(forecast_df.head(15))
