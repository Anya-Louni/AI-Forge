"""
optimize.py
-----------
Takes forecast_output.csv (from forecast.py) and produces a cost-optimal
staffing schedule using linear programming (scipy.optimize.linprog).

The problem:
    For every (day, shift) we know the forecasted required headcount.
    We can cover that headcount with:
        - "regular" workers  -> cheaper, but limited total capacity per week
        - "temp/overtime" workers -> more expensive, unlimited availability
    We minimize total labor cost while making sure every shift is covered.

This is a linear relaxation (continuous, not integer) which is standard
for a fast prototype. A production version would use integer/mixed-integer
programming (e.g. PuLP or OR-Tools CBC solver) for exact whole-worker
counts -- here we round up, which is a safe (slightly conservative)
approximation.

Run:
    python3 optimize.py
Requires:
    forecast_output.csv (produced by forecast.py)
"""

import pandas as pd
import numpy as np
from scipy.optimize import linprog

# ---- CONFIG (tune these to your pitch / real client numbers) ----
PRODUCTIVITY_PER_WORKER = 25       # orders one worker can handle per shift
COST_REGULAR_PER_SHIFT = 3000      # DZD, cost of one regular worker per shift
COST_TEMP_PER_SHIFT = 4500         # DZD, cost of one temp/overtime worker per shift
NUM_REGULAR_WORKERS = 35           # size of the permanent workforce pool
MAX_SHIFTS_PER_WORKER_PER_WEEK = 5 # labor law style constraint (rest days)


def load_and_aggregate():
    df = pd.read_csv("forecast_output.csv", parse_dates=["date"])
    # aggregate across zones -> one required headcount per (date, shift)
    agg = (
        df.groupby(["date", "shift"], as_index=False)["forecast_orders"]
        .sum()
        .rename(columns={"forecast_orders": "total_orders"})
    )
    agg["required_workers"] = np.ceil(
        agg["total_orders"] / PRODUCTIVITY_PER_WORKER
    ).astype(int)
    agg["iso_week"] = agg["date"].dt.isocalendar().week.astype(int)
    agg["iso_year"] = agg["date"].dt.isocalendar().year.astype(int)
    return agg


def solve_schedule(agg):
    n = len(agg)
    # variable vector x = [reg_1..reg_n, temp_1..temp_n]
    c = np.concatenate([
        np.full(n, COST_REGULAR_PER_SHIFT),
        np.full(n, COST_TEMP_PER_SHIFT),
    ])

    # --- Constraint 1: coverage -> reg_i + temp_i >= required_i
    # linprog only takes <=, so negate: -reg_i - temp_i <= -required_i
    A_cov = np.zeros((n, 2 * n))
    for i in range(n):
        A_cov[i, i] = -1          # regular
        A_cov[i, n + i] = -1      # temp
    b_cov = -agg["required_workers"].values

    # --- Constraint 2: weekly regular-worker capacity
    # sum of regular workers assigned across all shifts in a week
    # <= NUM_REGULAR_WORKERS * MAX_SHIFTS_PER_WORKER_PER_WEEK
    agg["week_key"] = agg["iso_year"].astype(str) + "-W" + agg["iso_week"].astype(str)
    week_keys = agg["week_key"].unique()
    A_week = np.zeros((len(week_keys), 2 * n))
    b_week = np.zeros(len(week_keys))
    weekly_capacity = NUM_REGULAR_WORKERS * MAX_SHIFTS_PER_WORKER_PER_WEEK
    for w_idx, wk in enumerate(week_keys):
        rows = agg.index[agg["week_key"] == wk]
        for i in rows:
            A_week[w_idx, i] = 1   # only regular vars count against capacity
        b_week[w_idx] = weekly_capacity

    A_ub = np.vstack([A_cov, A_week])
    b_ub = np.concatenate([b_cov, b_week])

    # --- Bounds: regular workers per shift capped at NUM_REGULAR_WORKERS,
    # temp workers unbounded (but costly, so LP will minimize their use)
    bounds = [(0, NUM_REGULAR_WORKERS)] * n + [(0, None)] * n

    result = linprog(c, A_ub=A_ub, b_ub=b_ub, bounds=bounds, method="highs")

    if not result.success:
        raise RuntimeError(f"Optimization failed: {result.message}")

    reg = np.ceil(result.x[:n]).astype(int)
    temp = np.ceil(result.x[n:]).astype(int)

    agg["regular_assigned"] = reg
    agg["temp_assigned"] = temp
    agg["total_assigned"] = reg + temp
    agg["shift_cost"] = reg * COST_REGULAR_PER_SHIFT + temp * COST_TEMP_PER_SHIFT
    return agg


RUSH_SURCHARGE_MULT = 1.3  # last-minute emergency temp costs even more than planned temp


def compare_to_naive_baseline(agg):
    """
    Naive baseline: most warehouses without forecasting run a FIXED
    weekly roster sized on the AVERAGE required headcount per shift-type
    (they don't see daily spikes coming). Two things happen with this:
      - On quiet days: they overstaff and pay for idle capacity.
      - On spike days: they get caught understaffed and have to scramble
        with emergency last-minute temp labor at a rush surcharge.
    This mirrors real warehouse practice and is what the AI schedule
    (which reacts to the forecast day-by-day) improves on.
    """
    fixed_level = agg.groupby("shift")["required_workers"].mean().to_dict()
    agg["naive_staff"] = agg["shift"].map(fixed_level).apply(np.ceil).astype(int)

    shortfall = (agg["required_workers"] - agg["naive_staff"]).clip(lower=0)
    agg["naive_cost"] = (
        agg["naive_staff"] * COST_REGULAR_PER_SHIFT
        + shortfall * COST_TEMP_PER_SHIFT * RUSH_SURCHARGE_MULT
    )

    total_optimized_cost = agg["shift_cost"].sum()
    total_naive_cost = agg["naive_cost"].sum()
    savings = total_naive_cost - total_optimized_cost
    pct_savings = 100 * savings / total_naive_cost if total_naive_cost else 0

    print(f"\n--- Cost comparison over {agg['date'].nunique()} days ---")
    print(f"Naive fixed-staffing cost:   {total_naive_cost:,.0f} DZD")
    print(f"AI-optimized schedule cost:  {total_optimized_cost:,.0f} DZD")
    print(f"Estimated savings:           {savings:,.0f} DZD ({pct_savings:.1f}%)")
    return agg


if __name__ == "__main__":
    agg = load_and_aggregate()
    schedule = solve_schedule(agg)
    schedule = compare_to_naive_baseline(schedule)

    out_cols = ["date", "shift", "total_orders", "required_workers",
                "regular_assigned", "temp_assigned", "total_assigned",
                "shift_cost", "naive_staff", "naive_cost"]
    schedule[out_cols].to_csv("optimized_schedule.csv", index=False)
    print("\nSchedule saved -> optimized_schedule.csv")
    print(schedule[out_cols].head(12))
