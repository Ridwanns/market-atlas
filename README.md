# Market Atlas

An interactive English research dashboard for US and Indonesian markets, AI infrastructure, ten stock models, and 5/10-year investment scenarios.

**Website:** https://ridwanns.github.io/market-atlas/

## Navigation

Three primary destinations: Overview, AI Portfolio and Research. Research → Investment Decision opens actual fundamentals, editable valuation cases, AI thesis checks, IDR stress and model health. All ten companies are included: NVDA, TSM, INTC, AMD, MU, AVGO, ETN, VRT, ALAB and CRDO. Quant research also includes S&P 500, Nasdaq Composite and IHSG.

## Data freshness

The online version uses dated public-feed snapshots, retrieved by GitHub Actions approximately every two hours on weekdays. The browser checks for a changed snapshot every 60 seconds. It is **not** a guaranteed real-time exchange feed; Actions delays, provider delays and closed sessions apply. Failed feeds remain missing or retain their original dated observation with an error. No brokerage credentials are required.

Fundamentals have a 1 October 2026 availability cutoff and company-specific financial periods. Short-horizon models are fitted through 30 September 2026 and do not refit when prices change. Five/ten-year valuation inputs are editable illustrations without scenario probabilities. Missing quantities remain unavailable. Model tests do not establish a trading edge.

The separate forward register freezes predictions before the first post-origin session open and excludes late registrations. This initial batch has 168 eligible pending records and 14 late/excluded records, with no matured outcomes at publication. The publishing job checks completed daily outcomes, compares matching-origin baselines and preserves their raw data hashes. It does not backdate predictions or create new model runs.

## Publishing

GitHub Pages deploys only `site/`. `.github/workflows/pages.yml` retrieves snapshots, preserves dated JSON and deploys on a main-branch push, manual dispatch, or the weekday schedule. Scheduled runs are best effort. This follows the snapshot architecture in the owner's existing `Stocks-Dashboard-Global` repository without altering that site.

`site/dashboard.html.gz` is the complete reviewed research artifact with an online data adapter. The small entry page decompresses it using the browser's standard gzip stream API; modern Chrome, Edge, Firefox and Safari support it. Compression reduces transfer size while retaining all research. `source/` contains the new analytical/interface modules; `data/quant-snapshot.json.gz` retains the frozen quant output needed to score registered forecasts. It is not a complete archive of every third-party research repository or original raw acquisition file.

## Verification and sources

The local dashboard passed 20 independent arithmetic/browser parity tests, five forward-ledger tests, 60 company/view integration combinations and retained model/quote regression checks. Formula references and unit definitions are in `source/DECISION_MATH.md`. SEC/company filings and dated conversion evidence are embedded in the dashboard. Font and design-source notices are in `notices/`. The site contains no order execution.

To run the publishing data job locally, use Python 3.12: `python tools/fetch_snapshot.py`. To preview the static site, use `python -m http.server 8080 --directory site`. Source updates are prepared from the original local `market_models/combined-market-report.html`; model runs and fundamentals retain their own audit trails.
