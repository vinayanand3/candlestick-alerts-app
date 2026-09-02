# Confluence Auto-Alert Trading App (TSLA • AAPL • NVDA • META)

A minimalist, high-conviction auto-alert trading platform analyzing candles to generate **fewer, higher-quality, explainable alerts** for **Tesla (TSLA), Apple (AAPL), NVIDIA (NVDA), and Meta Platforms (META)**.

---

## ⚡ The 5 Core Alert Methods Implemented

1. **Confluence Scoring Engine (Core Engine)**:
   - Evaluates multi-factor signals instead of triggering on single indicators:
     - **Candle Structure** (+2 / -2)
     - **Trend Alignment** (+2 / -2)
     - **EMA Stack (9/21/50)** (+1 / -1)
     - **Volume & Momentum** (+1 / -1)
     - **RSI / MACD** (+1 / -1)
     - **Support / Resistance Interaction** (+2 / -2)
     - **Breakout Confirmation** (+2 / -2)
   - Converts net scores into a calibrated **0–100 Confidence Score**. Alerting requires $\ge 75\%$ confidence.

2. **Breakout + Retest Confirmation**:
   - Requires price break $\rightarrow$ candle close beyond level $\rightarrow$ volume confirmation $\rightarrow$ retest hold $\rightarrow$ signal confirmation. Eliminates false breakouts.

3. **Candle Pattern + Market Context**:
   - Candlestick formations (Engulfing, Hammer, Shooting Star, Marubozu) are evaluated in market context (e.g. bounce at support vs mid-range noise).

4. **Momentum & Volume Acceleration**:
   - Detects early directional momentum moves via Price Rate of Change (ROC), Volume surge ($>1.3\times$ 20MA), and candle body expansion vs ATR.

5. **Market Regime Adaptive Thresholds**:
   - Classifies market into `TRENDING UP`, `TRENDING DOWN`, `RANGE`, or `HIGH VOLATILITY`.
   - In high-volatility regimes, the engine requires higher confluence scores before firing.

---

## 🛡️ Anti-Spam Signal State Machine

Prevents consecutive duplicate alert spam on identical conditions:
- **`CONFIRMED`**: High-confidence setup triggers with precise **Entry Zone**, **Invalidation (Stop Loss)**, and **Target (Take Profit)**.
- **`ACTIVE`**: Position is active and tracking.
- **`WEAKENING`**: Warns when momentum fades or confidence softens below 60%.
- **`EXIT`**: Fired when profit target is secured, stop loss is hit, or structure breaks.

---

## Architecture

The application has two independently deployable pieces:

- `static/`: the HTML and JavaScript dashboard, suitable for GitHub Pages.
- `app.py` and `v4_engine/`: the Python API and analysis engine, which require a Python web host.

GitHub Pages cannot execute the Python API. Configure the public API address in `static/config.js` after the backend has been deployed.

## Run locally

Python 3.11 is recommended.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
uvicorn app:app --host 127.0.0.1 --port 8000
```

On Windows PowerShell, activate the environment with:

```powershell
.venv\Scripts\Activate.ps1
```

Open `http://127.0.0.1:8000` in a browser. The dashboard and API share the same host locally, so `apiBaseUrl` should remain blank.

## Run tests

The repository currently contains a legacy root suite and the V4 suite:

```bash
python -m unittest discover -v
python -m unittest discover -s tests -v
```

## Deploy the API

The included `render.yaml` describes a Render-compatible Python web service. For any Python host, use:

```bash
pip install -r requirements.txt
uvicorn app:app --host 0.0.0.0 --port "$PORT"
```

Set `ALLOWED_ORIGINS` to the exact GitHub Pages origin, for example:

```text
https://YOUR_GITHUB_USERNAME.github.io
```

The API health check is available at `/api/health`.

## Deploy the dashboard to GitHub Pages

1. Deploy the API and copy its HTTPS URL.
2. Set `apiBaseUrl` in `static/config.js` to that URL.
3. Push the repository to a GitHub repository whose default branch is `main`.
4. In the repository settings, open Pages and choose GitHub Actions as the source.
5. The workflow in `.github/workflows/pages.yml` publishes the `static` directory.

## Data and risk notes

- Live mode reports an error when Yahoo Finance is unavailable. It never silently substitutes simulated prices.
- Simulation runs only when the dashboard is explicitly switched to Simulate.
- QQQ macro analysis uses daily QQQ, SPY, TQQQ, SQQQ, and IEF data in live mode.
- Option prices and returns are rough scenarios, not live option-chain quotes.
- This software is for research and education. It is not investment advice or an order-execution system.
