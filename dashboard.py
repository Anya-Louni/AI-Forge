"""
dashboard.py
------------
WorkForce.dz — Air Algérie ground operations intelligence:
flight board, demand forecast, crew planning, cost optimization, and an
ops assistant, on one screen.

Run:
    streamlit run dashboard.py

Requires (pip install -r requirements.txt):
    pandas, numpy, scikit-learn, scipy, streamlit
    groq            (optional — only needed for the Ops Assistant tab; free
                      API key at console.groq.com)
    python-dotenv   (optional — lets GROQ_API_KEY live in a local .env file
                      instead of being exported in every shell session)
"""

import os
import importlib
import importlib.util
import random
from datetime import datetime, timedelta

import pandas as pd
import streamlit as st

# Loads GROQ_API_KEY (and anything else) from a local .env file, if present.
# Safe to skip if python-dotenv isn't installed -- the app falls back to
# reading GROQ_API_KEY from the real environment instead.
if importlib.util.find_spec("dotenv") is not None:
    importlib.import_module("dotenv").load_dotenv()

import generate_data
import forecast as forecast_mod
import optimize as optimize_mod

st.set_page_config(
    page_title="WorkForce.dz — Air Algérie",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Design tokens & CSS
# Palette: sky-tinted paper white, aviation-night ink, Air Algérie red,
# desert-sand gold, muted emerald for savings, amber for delays.
# Type: Fraunces (display), Inter (body/UI), IBM Plex Mono (data readouts).
# One consistent system throughout — no per-tab motifs — so the screen
# reads as a single instrument panel, not a stack of separate widgets.
# ---------------------------------------------------------------------------
CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,400;9..144,500;9..144,600&family=Inter:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500;600&display=swap');

:root {
    --bg: #F6F8FA;
    --surface: #FFFFFF;
    --ink: #16233A;
    --ink-soft: #5B6478;
    --red: #C8102E;
    --red-dark: #8F0B21;
    --gold: #B78B4A;
    --green: #1E6F5C;
    --amber: #9C6209;
    --slate: #7C8494;
    --line: #E1E5EC;
}

html, body, [data-testid="stAppViewContainer"] {
    background: var(--bg) !important;
    color: var(--ink);
    font-family: 'Inter', sans-serif;
}

h1, h2, h3, .display-font {
    font-family: 'Fraunces', serif !important;
    color: var(--ink) !important;
    font-weight: 500 !important;
    letter-spacing: -0.01em;
}

.block-container { padding-top: 1.4rem; max-width: 1280px; }

/* ---------- Sidebar ---------- */
[data-testid="stSidebar"] { background: var(--surface); border-right: 1px solid var(--line); }
[data-testid="stSidebar"] > div:first-child { border-top: 4px solid var(--red); }
.sidebar-eyebrow {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 0.72rem; letter-spacing: 0.14em; text-transform: uppercase;
    color: var(--ink-soft);
}
.stButton > button {
    background: var(--red); color: #fff; border: none; border-radius: 3px;
    font-weight: 600; letter-spacing: 0.03em; text-transform: uppercase;
    font-size: 0.8rem; padding: 0.6rem 1rem; transition: background 0.15s ease;
}
.stButton > button:hover { background: var(--red-dark); color: #fff; }

/* ---------- Masthead ---------- */
.masthead {
    display: flex; align-items: flex-start; justify-content: space-between;
    border-bottom: 2px solid var(--ink);
    padding-bottom: 0.9rem; margin-bottom: 1.2rem;
}
.masthead .wordmark { font-family: 'Fraunces', serif; font-size: 1.7rem; font-weight: 600; color: var(--ink); }
.masthead .tagline { font-family: 'Inter', sans-serif; font-size: 0.86rem; color: var(--ink-soft); max-width: 46ch; margin-top: 0.15rem; }
.masthead .meta { text-align: right; }
.live-pill {
    display: inline-flex; align-items: center; gap: 0.4rem;
    font-family: 'IBM Plex Mono', monospace; font-size: 0.72rem;
    letter-spacing: 0.08em; text-transform: uppercase; color: var(--ink-soft);
}
.live-dot { width: 8px; height: 8px; border-radius: 50%; background: var(--green); box-shadow: 0 0 0 3px rgba(30,111,92,0.15); }
.masthead .timestamp { font-family: 'IBM Plex Mono', monospace; font-size: 0.78rem; color: var(--ink-soft); margin-top: 0.25rem; }

/* ---------- Section eyebrow + title ---------- */
.eyebrow {
    font-family: 'IBM Plex Mono', monospace; font-size: 0.72rem;
    letter-spacing: 0.16em; text-transform: uppercase; color: var(--red);
    margin-bottom: 0.2rem; margin-top: 0.6rem;
}
.section-title { font-family: 'Fraunces', serif; font-size: 1.45rem; font-weight: 500; color: var(--ink); margin: 0 0 0.9rem 0; }

/* ---------- Tabs ---------- */
[data-baseweb="tab-list"] { gap: 0; border-bottom: 1px solid var(--line); background: transparent; }
[data-baseweb="tab"] {
    font-family: 'IBM Plex Mono', monospace; font-size: 0.78rem;
    letter-spacing: 0.06em; text-transform: uppercase; color: var(--ink-soft);
    padding: 0.8rem 1.3rem; background: transparent;
}
/* Streamlit renders the tab label inside a <p>, which can pick up its own
   (often white) color from the base theme -- force it explicitly here so
   labels never render invisibly on the light background. */
[data-baseweb="tab"] p {
    font-size: 0.78rem;
    color: var(--ink-soft) !important;
}
[data-baseweb="tab-highlight"] { background-color: var(--red) !important; height: 2px; }
[aria-selected="true"] { color: var(--ink) !important; font-weight: 600; }
[aria-selected="true"] p { color: var(--ink) !important; font-weight: 600; }

/* ---------- Stat cards ---------- */
.stat-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr)); gap: 0.9rem; margin: 0.4rem 0 1.6rem; }
.stat-card { background: var(--surface); border: 1px solid var(--line); border-left: 3px solid var(--ink); border-radius: 4px; padding: 0.9rem 1.1rem; }
.stat-card .label { font-family: 'IBM Plex Mono', monospace; font-size: 0.66rem; letter-spacing: 0.1em; text-transform: uppercase; color: var(--ink-soft); margin-bottom: 0.3rem; }
.stat-card .value { font-family: 'IBM Plex Mono', monospace; font-size: 1.45rem; font-weight: 600; color: var(--ink); }
.stat-card .sub { font-family: 'Inter', sans-serif; font-size: 0.74rem; color: var(--ink-soft); margin-top: 0.25rem; }

/* ---------- Empty state ---------- */
.empty-state { border: 1px dashed var(--line); border-radius: 8px; padding: 3rem 2rem; text-align: center; background: var(--surface); color: var(--ink-soft); }
.empty-state .eyebrow { display: block; margin-bottom: 0.6rem; }
.empty-state p { font-size: 0.95rem; margin: 0; }

/* ---------- Flight board table ---------- */
.flight-table { width: 100%; border-collapse: collapse; font-size: 0.85rem; margin-bottom: 0.6rem; }
.flight-table th {
    background: #EEF1F5; color: var(--ink); text-align: left; padding: 0.55rem 0.75rem;
    font-family: 'IBM Plex Mono', monospace; font-size: 0.64rem; letter-spacing: 0.08em;
    text-transform: uppercase; font-weight: 600; border-bottom: 2px solid var(--line);
}
.flight-table td { padding: 0.5rem 0.75rem; border-bottom: 1px solid var(--line); color: var(--ink); }
.flight-table tr:nth-child(even) td { background: rgba(22,35,58,0.02); }
.flight-no { font-family: 'IBM Plex Mono', monospace; font-weight: 600; }
.status-pill {
    display: inline-block; padding: 0.2rem 0.55rem; border-radius: 3px;
    font-family: 'IBM Plex Mono', monospace; font-size: 0.64rem; font-weight: 600;
    text-transform: uppercase; letter-spacing: 0.04em; white-space: nowrap;
}
.status-ontime { background: rgba(30,111,92,0.12); color: var(--green); }
.status-delayed { background: rgba(156,98,9,0.14); color: var(--amber); }
.status-boarding, .status-landing { background: rgba(31,90,166,0.12); color: #1F5AA6; }
.status-landed, .status-departed { background: rgba(124,132,148,0.14); color: var(--slate); }
.status-cancelled { background: rgba(200,16,46,0.14); color: var(--red-dark); }
.delay-text { color: var(--amber); font-family: 'IBM Plex Mono', monospace; font-weight: 600; }

/* ---------- Dataframe polish ---------- */
[data-testid="stDataFrame"] { border: 1px solid var(--line); border-radius: 6px; }

hr { border-color: var(--line); }
#MainMenu, footer { visibility: hidden; }
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Small render helpers
# ---------------------------------------------------------------------------
def section_header(eyebrow, title):
    st.markdown(
        f'<div class="eyebrow">{eyebrow}</div><div class="section-title">{title}</div>',
        unsafe_allow_html=True,
    )


def human_dzd(n):
    """Format a DZD amount as a plain, fully expanded number with commas."""
    sign = "-" if n < 0 else ""
    n = abs(n)
    return f"{sign}{n:,.0f} DZD"


def stat_card_html(label, value, sub="", accent="ink"):
    sub_html = f'<div class="sub">{sub}</div>' if sub else ""
    return (
        f'<div class="stat-card" style="border-left-color:var(--{accent});">'
        f'<div class="label">{label}</div>'
        f'<div class="value">{value}</div>'
        f"{sub_html}"
        f"</div>"
    )


def stat_row(cards):
    html = '<div class="stat-grid">' + "".join(stat_card_html(**c) for c in cards) + "</div>"
    st.markdown(html, unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Synthetic flight board
# Self-contained here (no dependency on generate_data / forecast / optimize)
# so the ops screen has a live-feeling flight feed even though this is a
# demo. In production this would read from the airport's AODB / FIDS feed.
# ---------------------------------------------------------------------------
AIRLINE_CODE = "AH"

ROUTES = [
    ("CDG", "intl"), ("ORY", "intl"), ("MRS", "intl"), ("LYS", "intl"),
    ("IST", "intl"), ("DXB", "intl"), ("LHR", "intl"), ("FRA", "intl"),
    ("BCN", "intl"), ("MAD", "intl"), ("FCO", "intl"), ("TUN", "intl"),
    ("CMN", "intl"), ("YUL", "intl"),
    ("ORN", "domestic"), ("CZL", "domestic"), ("AAE", "domestic"),
    ("TMR", "domestic"), ("OGX", "domestic"), ("BJA", "domestic"), ("GHA", "domestic"),
]
AIRCRAFT = {
    "intl": ["Airbus A330-200", "Airbus A321neo"],
    "domestic": ["Boeing 737-800", "ATR 72-600"],
}
GATES = [f"{letter}{n}" for letter in "ABC" for n in range(1, 13)]

STATUS_CLASS = {
    "On Time": "status-ontime",
    "Delayed": "status-delayed",
    "Boarding": "status-boarding",
    "Landing": "status-landing",
    "Landed": "status-landed",
    "Departed": "status-departed",
    "Cancelled": "status-cancelled",
}


def generate_flight_board(now, n_flights=24, seed=None):
    rng = random.Random(seed)
    used_numbers = set()
    rows = []
    for _ in range(n_flights):
        iata, region = rng.choice(ROUTES)
        direction = rng.choice(["Arrival", "Departure"])
        aircraft = rng.choice(AIRCRAFT[region])

        base = 1000 if region == "domestic" else rng.choice([1200, 1700, 1900])
        num = base + rng.randint(1, 98)
        while num in used_numbers:
            num += 1
        used_numbers.add(num)
        flight_no = f"{AIRLINE_CODE}{num}"

        sched_time = now + timedelta(minutes=rng.randint(-180, 360))

        roll = rng.random()
        if roll < 0.62:
            delay = 0
        elif roll < 0.90:
            delay = rng.randint(8, 35)
        elif roll < 0.98:
            delay = rng.randint(36, 75)
        else:
            delay = None  # cancelled

        route_label = f"ALG \u2192 {iata}" if direction == "Departure" else f"{iata} \u2192 ALG"

        if delay is None:
            status = "Cancelled"
            est_time = sched_time
        else:
            est_time = sched_time + timedelta(minutes=delay)
            minutes_to_go = (est_time - now).total_seconds() / 60
            if direction == "Departure":
                if minutes_to_go < -10:
                    status = "Departed"
                elif minutes_to_go <= 15:
                    status = "Boarding"
                else:
                    status = "Delayed" if delay > 15 else "On Time"
            else:
                if minutes_to_go < -10:
                    status = "Landed"
                elif minutes_to_go <= 15:
                    status = "Landing"
                else:
                    status = "Delayed" if delay > 15 else "On Time"

        rows.append({
            "flight_no": flight_no,
            "direction": direction,
            "route": route_label,
            "aircraft": aircraft,
            "scheduled": sched_time,
            "estimated": est_time,
            "delay_min": delay,
            "gate": rng.choice(GATES),
            "status": status,
        })

    return pd.DataFrame(rows).sort_values("scheduled").reset_index(drop=True)


def render_flight_table(df):
    if df.empty:
        return '<p style="color:var(--ink-soft);font-size:.85rem;">No flights match this filter.</p>'

    rows_html = []
    for _, r in df.iterrows():
        status_cls = STATUS_CLASS.get(r["status"], "status-landed")
        dm = r["delay_min"]
        if pd.isna(dm) or dm == 0:
            delay_cell = "\u2014"
        else:
            delay_cell = f'<span class="delay-text">+{int(dm)} min</span>'
        est = "\u2014" if r["status"] == "Cancelled" else r["estimated"].strftime("%H:%M")
        rows_html.append(
            "<tr>"
            f'<td class="flight-no">{r["flight_no"]}</td>'
            f'<td>{r["direction"]}</td>'
            f'<td>{r["route"]}</td>'
            f'<td>{r["aircraft"]}</td>'
            f'<td>{r["scheduled"].strftime("%H:%M")}</td>'
            f'<td>{est}</td>'
            f'<td>{delay_cell}</td>'
            f'<td>{r["gate"]}</td>'
            f'<td><span class="status-pill {status_cls}">{r["status"]}</span></td>'
            "</tr>"
        )

    header = (
        "<tr><th>Flight</th><th>Type</th><th>Route</th><th>Aircraft</th>"
        "<th>Scheduled</th><th>Estimated</th><th>Delay</th><th>Gate</th><th>Status</th></tr>"
    )
    return f'<table class="flight-table">{header}{"".join(rows_html)}</table>'


# ---------------------------------------------------------------------------
# Sidebar: parameters the jury / a manager could tweak live
# ---------------------------------------------------------------------------
st.sidebar.markdown('<div class="sidebar-eyebrow">Air Algerie -- Ops Console</div>', unsafe_allow_html=True)
st.sidebar.markdown("## Get started")
st.sidebar.write(
    "Click below to generate today's flight board, demand forecast, "
    "and staffing plan."
)

run_button = st.sidebar.button("Run pipeline", type="primary", use_container_width=True)

with st.sidebar.expander("Advanced settings"):
    st.caption(
        "Optional. Defaults are tuned for a typical day at ALG -- only "
        "change these to test a different scenario."
    )
    forecast_days = st.slider("Forecast horizon (days)", 7, 30, 14)
    productivity = st.number_input(
        "Orders handled per worker per shift",
        5, 100, optimize_mod.PRODUCTIVITY_PER_WORKER,
        help="How many orders one worker can process in a single shift.",
    )
    num_regular = st.number_input(
        "Regular workforce size",
        5, 200, optimize_mod.NUM_REGULAR_WORKERS,
        help="Permanent staff available before temp workers are added.",
    )
    cost_regular = st.number_input(
        "Cost per regular worker/shift (DZD)",
        500, 20000, optimize_mod.COST_REGULAR_PER_SHIFT,
    )
    cost_temp = st.number_input(
        "Cost per temp worker/shift (DZD)",
        500, 30000, optimize_mod.COST_TEMP_PER_SHIFT,
        help="Usually higher than the regular rate to reflect temp agency fees.",
    )

st.sidebar.markdown("<hr>", unsafe_allow_html=True)
st.sidebar.caption(
    "Synthetic data is used for this prototype demo. In production, this "
    "would ingest a real warehouse's order history, shift logs, and the "
    "airport's live flight feed."
)

# ---------------------------------------------------------------------------
# Masthead
# ---------------------------------------------------------------------------
st.markdown(
    f'''
    <div class="masthead">
        <div>
            <div class="wordmark">WorkForce.dz</div>
            <div class="tagline">Ground operations intelligence for Air Algerie --
            flight status, demand forecasting and crew cost optimization on one screen.</div>
        </div>
        <div class="meta">
            <div class="live-pill"><span class="live-dot"></span>Live snapshot</div>
            <div class="timestamp">{datetime.now().strftime("%A %d %B %Y -- %H:%M")}</div>
        </div>
    </div>
    ''',
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Pipeline: generate -> forecast -> optimize -> flight board
# ---------------------------------------------------------------------------
if run_button:
    forecast_mod.FORECAST_DAYS = forecast_days
    optimize_mod.PRODUCTIVITY_PER_WORKER = productivity
    optimize_mod.NUM_REGULAR_WORKERS = num_regular
    optimize_mod.COST_REGULAR_PER_SHIFT = cost_regular
    optimize_mod.COST_TEMP_PER_SHIFT = cost_temp

    with st.spinner("Generating historical data..."):
        hist_df = generate_data.generate()
        hist_df.to_csv("warehouse_orders.csv", index=False)

    with st.spinner("Training forecasting model..."):
        model, feature_cols, shifts, zones = forecast_mod.build_model(hist_df)
        last_date = pd.to_datetime(hist_df["date"]).max()
        forecast_df = forecast_mod.forecast_future(
            model, feature_cols, shifts, zones, last_date
        )
        forecast_df.to_csv("forecast_output.csv", index=False)

    with st.spinner("Optimizing staff schedule..."):
        agg = optimize_mod.load_and_aggregate()
        schedule = optimize_mod.solve_schedule(agg)
        schedule = optimize_mod.compare_to_naive_baseline(schedule)
        schedule.to_csv("optimized_schedule.csv", index=False)

    with st.spinner("Pulling the flight board..."):
        flights_ref_time = datetime.now()
        flights_df = generate_flight_board(flights_ref_time, n_flights=24)

    st.session_state["hist_df"] = hist_df
    st.session_state["forecast_df"] = forecast_df
    st.session_state["schedule"] = schedule
    st.session_state["flights"] = flights_df
    st.session_state["flights_ref_time"] = flights_ref_time
    st.success("Pipeline complete.")

# ---------------------------------------------------------------------------
# Show results (if pipeline has been run at least once this session)
# ---------------------------------------------------------------------------
if "schedule" not in st.session_state:
    st.markdown(
        '<div class="empty-state">'
        '<span class="eyebrow">Ready when you are</span>'
        "<p>Set your parameters in the console on the left, then run the pipeline "
        "to generate today's flight board, demand forecast and staffing plan.</p>"
        "</div>",
        unsafe_allow_html=True,
    )
    st.stop()

forecast_df = st.session_state["forecast_df"]
schedule = st.session_state["schedule"]
flights_df = st.session_state["flights"]
flights_ref_time = st.session_state["flights_ref_time"]

tab_overview, tab_flights, tab_forecast, tab_staffing, tab_ai = st.tabs(
    ["Overview", "Flight Board", "Demand Forecast", "Staffing & Costs", "Ops Assistant"]
)

# --- Tab: Overview ---
with tab_overview:
    section_header("Command center", "Today at a glance")

    upcoming = flights_df[
        (flights_df["scheduled"] >= flights_ref_time)
        & (flights_df["scheduled"] <= flights_ref_time + timedelta(hours=6))
    ]
    valid_delays = flights_df["delay_min"].dropna()
    avg_delay = valid_delays.mean() if len(valid_delays) else 0
    cancelled_ct = int((flights_df["status"] == "Cancelled").sum())

    total_optimized = schedule["shift_cost"].sum()
    total_naive = schedule["naive_cost"].sum()
    savings = total_naive - total_optimized
    pct = 100 * savings / total_naive if total_naive else 0
    peak_crew = schedule["total_assigned"].max()

    stat_row([
        {"label": "Flights, next 6h", "value": str(len(upcoming)), "sub": f"{cancelled_ct} cancelled today", "accent": "ink"},
        {"label": "Avg delay today", "value": f"{avg_delay:.0f} min", "sub": f"{len(valid_delays)} flights tracked", "accent": "amber"},
        {"label": "Peak crew required", "value": f"{int(peak_crew)}", "sub": "workers, busiest shift", "accent": "gold"},
        {"label": "Projected savings", "value": human_dzd(savings), "sub": f"{pct:.1f}% vs fixed staffing", "accent": "green"},
    ])

    section_header("Next up", "Flight board preview")
    preview = flights_df.sort_values("scheduled").head(8)
    st.markdown(render_flight_table(preview), unsafe_allow_html=True)

    section_header("Status mix", "Flights today")
    counts = flights_df["status"].value_counts()
    st.bar_chart(counts, color=["#C8102E"], height=240)

    section_header("Demand signal", "Forecast orders, next horizon")
    daily_forecast = (
        forecast_df.groupby("date")["forecast_orders"].sum().reset_index().set_index("date")
    )
    st.line_chart(daily_forecast, color=["#16233A"], height=230)

# --- Tab: Flight Board ---
with tab_flights:
    section_header("Flight board", f"Snapshot as of {flights_ref_time.strftime('%H:%M')}")
    st.caption(
        "Synthetic flight data for this prototype. In production this would read "
        "the airport's AODB / FIDS feed directly, which is also what would drive "
        "the demand forecast in real time."
    )

    fcol1, fcol2 = st.columns(2)
    with fcol1:
        direction_filter = st.multiselect(
            "Type", ["Arrival", "Departure"], default=["Arrival", "Departure"]
        )
    with fcol2:
        status_options = sorted(flights_df["status"].unique().tolist())
        status_filter = st.multiselect("Status", status_options, default=status_options)

    filtered = flights_df[
        flights_df["direction"].isin(direction_filter) & flights_df["status"].isin(status_filter)
    ].sort_values("scheduled")

    st.markdown(render_flight_table(filtered), unsafe_allow_html=True)

# --- Tab: Demand Forecast ---
with tab_forecast:
    section_header("Demand signal", "Forecasted order volume")

    daily = forecast_df.groupby("date")["forecast_orders"].sum().reset_index()
    total_forecast = daily["forecast_orders"].sum()
    peak_row = daily.loc[daily["forecast_orders"].idxmax()]
    avg_daily = daily["forecast_orders"].mean()

    stat_row([
        {"label": "Total forecast orders", "value": f"{total_forecast:,.0f}", "sub": f"over {forecast_days} days", "accent": "ink"},
        {"label": "Peak day", "value": pd.to_datetime(peak_row["date"]).strftime("%d %b"), "sub": f"{peak_row['forecast_orders']:,.0f} orders", "accent": "red"},
        {"label": "Avg daily orders", "value": f"{avg_daily:,.0f}", "sub": "across all zones & shifts", "accent": "gold"},
    ])

    daily_idx = daily.set_index("date")
    st.line_chart(daily_idx, color=["#C8102E"], height=300)

    section_header("By shift", "Forecast split across shifts")
    by_shift = (
        forecast_df.groupby(["date", "shift"])["forecast_orders"].sum().unstack("shift")
    )
    palette = ["#16233A", "#C8102E", "#B78B4A", "#1E6F5C"]
    colors = [palette[i % len(palette)] for i in range(len(by_shift.columns))]
    st.line_chart(by_shift, color=colors, height=300)

    with st.expander("Raw forecast data"):
        st.dataframe(forecast_df, use_container_width=True)

# --- Tab: Staffing & Costs ---
with tab_staffing:
    section_header("Staffing plan", "Cost comparison")

    total_optimized = schedule["shift_cost"].sum()
    total_naive = schedule["naive_cost"].sum()
    savings = total_naive - total_optimized
    pct = 100 * savings / total_naive if total_naive else 0
    orders_sum = schedule["total_orders"].sum()
    cost_per_order = total_optimized / orders_sum if orders_sum else 0

    stat_row([
        {"label": "Naive fixed-staffing cost", "value": human_dzd(total_naive), "accent": "ink"},
        {"label": "AI-optimized cost", "value": human_dzd(total_optimized), "accent": "red"},
        {"label": "Estimated savings", "value": human_dzd(savings), "sub": f"{pct:+.1f}% vs naive", "accent": "green"},
        {"label": "Cost per order", "value": f"{cost_per_order:,.1f} DZD", "accent": "gold"},
    ])

    cost_by_date = (
        schedule.groupby("date")[["shift_cost", "naive_cost"]]
        .sum()
        .rename(columns={"shift_cost": "Optimized", "naive_cost": "Naive"})
    )
    st.bar_chart(cost_by_date, color=["#C8102E", "#DDE1E8"], height=280)

    section_header("Manifest", "Recommended staffing schedule")
    display_cols = [
        "date", "shift", "total_orders", "required_workers",
        "regular_assigned", "temp_assigned", "total_assigned", "shift_cost"
    ]
    st.dataframe(schedule[display_cols], use_container_width=True)

# --- Tab: Ops Assistant ---
with tab_ai:
    section_header("Ops assistant", "Ask about today's forecast, schedule or flight board")
    st.caption(
        "This assistant reads the outputs already generated on this screen and "
        "explains them in plain language -- it doesn't replace the forecast or "
        "optimizer, it answers questions about their results. Powered by Groq."
    )

    api_key = os.environ.get("GROQ_API_KEY", "")
    if not api_key:
        st.warning(
            "No GROQ_API_KEY found. Groq's free tier just needs an API key from "
            "console.groq.com -- set it before launching, e.g.:\n\n"
            "`export GROQ_API_KEY=gsk_...` (Mac/Linux) or "
            "`set GROQ_API_KEY=gsk_...` (Windows), then relaunch "
            "`streamlit run dashboard.py`."
        )
    else:
        try:
            from groq import Groq
        except ImportError:
            st.error("Run `pip install groq` to enable the ops assistant.")
            st.stop()

        if "chat_history" not in st.session_state:
            st.session_state["chat_history"] = []

        for msg in st.session_state["chat_history"]:
            with st.chat_message(msg["role"]):
                st.write(msg["content"])

        question = st.chat_input("e.g. Why do we need extra staff on Thursday afternoon?")
        if question:
            st.session_state["chat_history"].append({"role": "user", "content": question})
            with st.chat_message("user"):
                st.write(question)

            summary_cols = [
                "date", "shift", "total_orders", "required_workers",
                "regular_assigned", "temp_assigned", "shift_cost"
            ]
            schedule_summary = schedule[summary_cols].to_string(index=False)

            flight_cols = ["flight_no", "direction", "route", "scheduled", "estimated", "delay_min", "status"]
            flight_summary = flights_df[flight_cols].to_string(index=False)

            system_prompt = (
                "You are a ground operations assistant embedded in Air Algerie's "
                "WorkForce.dz staffing dashboard. Answer the manager's question "
                "using ONLY the data provided below. Be concise, concrete, and "
                "reference actual numbers, dates, and flight numbers. If the data "
                "doesn't answer the question, say so.\n\n"
                f"STAFFING SCHEDULE:\n{schedule_summary}\n\n"
                f"FLIGHT BOARD:\n{flight_summary}"
            )

            client = Groq(api_key=api_key)
            with st.chat_message("assistant"):
                with st.spinner("Thinking..."):
                    try:
                        response = client.chat.completions.create(
                            model="llama-3.3-70b-versatile",
                            max_tokens=500,
                            messages=[
                                {"role": "system", "content": system_prompt},
                                {"role": "user", "content": question},
                            ],
                        )
                        answer = response.choices[0].message.content
                    except Exception as e:
                        answer = f"Error calling Groq API: {e}"
                    st.write(answer)

            st.session_state["chat_history"].append({"role": "assistant", "content": answer})