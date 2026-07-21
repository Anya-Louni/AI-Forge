"""
generate_data.py
-----------------
Creates a synthetic (but realistic) warehouse order-volume dataset.

Why synthetic data? There is no free public dataset that contains real
warehouse order volume + shift + labor data at the granularity we need.
So we simulate it with realistic patterns (weekly seasonality, growth
trend, random spikes for promos/holidays, noise). This is standard
practice for early-stage prototypes and is fine to state clearly in a
jury demo: "synthetic data calibrated to realistic warehouse patterns."

Output: warehouse_orders.csv with columns:
    date, shift, orders, zone
"""

import numpy as np
import pandas as pd

np.random.seed(42)  # fixed seed = reproducible results every run

# ---- CONFIG (tweak these for your story / jury demo) ----
START_DATE = "2024-01-01"
NUM_DAYS = 365 * 2          # 2 years of daily history
SHIFTS = ["morning", "afternoon", "night"]
ZONES = ["landside", "airside", "bonded_storage"]  # airport-style zones
BASE_ORDERS_PER_SHIFT = {"morning": 220, "afternoon": 260, "night": 90}
WEEKLY_PATTERN = {  # multiplier per weekday, 0=Monday
    0: 1.05, 1: 1.00, 2: 1.00, 3: 1.05, 4: 1.20, 5: 0.70, 6: 0.55
}
GROWTH_PER_YEAR = 0.12      # 12% yearly growth trend
NOISE_STD = 0.12            # 12% random noise
HOLIDAY_SPIKE_PROB = 0.03   # ~3% of days get a demand spike (promo/holiday)
HOLIDAY_SPIKE_MULT = (1.5, 2.2)  # random spike multiplier range


def generate():
    dates = pd.date_range(START_DATE, periods=NUM_DAYS, freq="D")
    rows = []

    for day_idx, date in enumerate(dates):
        weekday = date.weekday()
        weekly_mult = WEEKLY_PATTERN[weekday]
        trend_mult = 1 + GROWTH_PER_YEAR * (day_idx / 365)

        # Random chance of a demand spike (promo, holiday, seasonal surge)
        is_spike = np.random.rand() < HOLIDAY_SPIKE_PROB
        spike_mult = np.random.uniform(*HOLIDAY_SPIKE_MULT) if is_spike else 1.0

        for shift in SHIFTS:
            base = BASE_ORDERS_PER_SHIFT[shift]
            for zone in ZONES:
                # each zone takes a share of total volume
                zone_share = {"landside": 0.45, "airside": 0.35, "bonded_storage": 0.20}[zone]
                noise = np.random.normal(1.0, NOISE_STD)

                orders = base * weekly_mult * trend_mult * spike_mult * zone_share * noise
                orders = max(0, round(orders))

                rows.append({
                    "date": date.strftime("%Y-%m-%d"),
                    "weekday": date.day_name(),
                    "shift": shift,
                    "zone": zone,
                    "orders": orders,
                    "is_spike_day": is_spike
                })

    df = pd.DataFrame(rows)
    return df


if __name__ == "__main__":
    df = generate()
    out_path = "warehouse_orders.csv"
    df.to_csv(out_path, index=False)
    print(f"Generated {len(df)} rows -> {out_path}")
    print(df.head(10))
    print("\nSummary stats (orders):")
    print(df["orders"].describe())
