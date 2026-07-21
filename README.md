Ground operations intelligence for airlines — flight status, demand
forecasting, and crew cost optimization on one screen.

This project takes historical order data, forecasts upcoming demand, and
turns that into an optimized staffing schedule — showing exactly how much
a fixed, "naive" staffing approach would cost versus an AI-optimized one.
A live-style flight board ties that staffing plan back to real airport
activity, and an Ops Assistant tab lets you ask plain-language questions
about the results.

## What's in the app

| Tab | What it shows |
|---|---|
| **Overview** | A command-center snapshot: flights in the next 6 hours, average delay, peak crew required, and projected savings, plus a flight preview and demand trend. |
| **Flight Board** | A filterable table of today's arrivals and departures — flight number, route, aircraft, scheduled vs. estimated time, delay, gate, and status. |
| **Demand Forecast** | Forecasted order volume over the chosen horizon, broken down by shift. |
| **Staffing & Costs** | Naive vs. AI-optimized staffing cost comparison, cost per order, and the full recommended shift-by-shift schedule. |
| **Ops Assistant** | A chat interface (powered by Groq) that answers questions about the current forecast, schedule, and flight board. |

> The flight board and historical order data are synthetic for this
> prototype. In production, these would come from the airport's live
> flight feed (AODB/FIDS) and the warehouse's real order history.

---

## 1. Prerequisites

- **Python 3.9 or later** — check with `python --version` (or `python3 --version` on Mac/Linux)
- **Git**
- A free **Groq API key** (see step 4) — only needed for the Ops Assistant tab; the rest of the app works without it

---

## 2. Clone the repo

```bash
git clone <repo-url>
cd <repo-folder>
```

---

## 3. Set up a virtual environment

A virtual environment keeps this project's Python packages separate from
everything else on your machine. Create one **once**, then reactivate it
every time you come back to the project (step 3b).

### First-time setup

**Mac / Linux:**
```bash
python3 -m venv venv
source venv/bin/activate
python -m pip install -r requirements.txt
```

**Windows (PowerShell):**
```powershell
python -m venv venv
venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

> If PowerShell blocks the activation script with an error about running
> scripts being disabled, run this once and try again:
> ```powershell
> Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
> ```
> Type `Y` when prompted.

You'll know the venv is active when your terminal prompt starts with
`(venv)`.

### Every time after that

You don't need to recreate the venv or reinstall packages — just
reactivate it in a fresh terminal:

**Mac / Linux:**
```bash
source venv/bin/activate
```

**Windows (PowerShell):**
```powershell
venv\Scripts\Activate.ps1
```

---

## 4. Add your Groq API key

The Ops Assistant tab calls [Groq](https://console.groq.com), which has a
free tier — no credit card required.

1. Create a free account at **console.groq.com** and generate an API key.
2. In the project folder, copy `.env.example` to a new file named `.env`:
   ```bash
   cp .env.example .env          # Mac/Linux
   copy .env.example .env        # Windows
   ```
3. Open `.env` and paste your key:
   ```
   GROQ_API_KEY=gsk_your_real_key_here
   ```

`.env` is listed in `.gitignore`, so it will never be committed — each
teammate keeps their own key locally. If you skip this step, every tab
except Ops Assistant still works fine.

**If you ever paste a real key into a chat, a shared doc, or a public
repo, treat it as compromised** — regenerate a new one at console.groq.com
and delete the old one.

---

## 5. Run the app

With the venv active:

```bash
streamlit run dashboard.py
```

This opens automatically in your browser, usually at
`http://localhost:8501`. If it doesn't open on its own, paste that URL in
manually.

In the app, open the sidebar and click **Run pipeline** — that generates
the flight board, demand forecast, and staffing plan for the session.
Everything else (parameter tweaks, etc.) is optional and tucked into
**Advanced settings**.

---

## Project structure

```
.
├── dashboard.py            # Main Streamlit app (this is what you run)
├── generate_data.py        # Generates synthetic historical order data
├── forecast.py              # Trains the demand forecasting model
├── optimize.py               # Solves the staffing schedule & cost comparison
├── requirements.txt         # Python dependencies
├── .env.example              # Template for your local .env (copy, don't edit directly)
├── .env                        # Your real API key — created locally, never committed
├── .gitignore
└── .streamlit/
    └── config.toml           # App theme (colors, light mode)
```

Running the pipeline also writes a few CSVs to the project folder
(`warehouse_orders.csv`, `forecast_output.csv`, `optimized_schedule.csv`)
— these are regenerated each run and are gitignored.

---

## Troubleshooting

**`ModuleNotFoundError` for pandas / streamlit / groq / etc.**
Your venv probably isn't active, or `requirements.txt` wasn't installed.
Reactivate the venv (step 3, "every time after that") and rerun
`python -m pip install -r requirements.txt`.

**`No module named uv` when running `pip install ...`**
Something's shadowing `pip` in your shell. Use `python -m pip install ...`
instead of a bare `pip install ...` — this calls pip directly through
Python and sidesteps the issue.

**PowerShell: `source` is not recognized**
`source` is a Mac/Linux (bash) command. On Windows PowerShell, activate
the venv with `venv\Scripts\Activate.ps1` instead.

**"No GROQ_API_KEY found" warning in the Ops Assistant tab**
Either `.env` doesn't exist yet (see step 4) or `python-dotenv` isn't
installed — rerun `python -m pip install -r requirements.txt`. Every
other tab works fine without this.

**Port 8501 already in use**
Another Streamlit app is probably still running in another terminal
window. Close it, or run this one on a different port:
```bash
streamlit run dashboard.py --server.port 8502
```

**Blank page or a wall of red error text after clicking "Run pipeline"**
Take a screenshot of the full error and share it — it's almost always a
one-line fix (usually a column name mismatch between `generate_data.py`,
`forecast.py`, and `optimize.py`).