# Investment Decision workspace

Open http://127.0.0.1:8767/, select a company, then **Research → Investment Decision**. The AI company panel and stock overview also have direct shortcuts. Three primary navigation choices remain. The single Explore selector contains overview, valuation, fundamentals, AI bottlenecks, position/IDR risk, and model health.

Ten companies are supported: NVDA, TSM, INTC, AMD, MU, AVGO, ETN, VRT, ALAB and CRDO. Company statements are a separate 1 October 2026 evidence bundle; original reports, options and the 30 September quant snapshot retain their dates. Public quotes refresh every 60 seconds through the local service; they can be delayed and are not executable broker prices.

The 5/10-year valuation calculator projects revenue, terminal net margin, diluted shares and an exit P/E. Required USD return discounts the assumed terminal value into a hurdle-supporting entry price. The three default cases are generic editable examples across the universe, not company forecasts, likelihoods or buy ratings. Loss-making terminal earnings cannot support a positive P/E valuation. Dividends, fees and taxes are excluded from displayed returns. Details and independent formula tests are in [DECISION_MATH.md](DECISION_MATH.md).

Statements use actual consolidated GAAP/TIFRS amounts. TTM flows are latest annual + current fiscal YTD − comparable prior fiscal YTD, or the latest full year where appropriate. Latest diluted weighted shares seed a forward share-count scenario; they are not an exact TTM EPS denominator. TSM revenue stays TWD in financial evidence. Valuation translates it at the Fed H.10 observation dated 25 September, 31.82 TWD/USD, and divides ordinary diluted shares by five per ADR. That spot translation is not historical USD reporting or a future currency forecast. Micron incorporates its 30 September full-year release. Reported CFO less gross capex is kept separate from adjusted company FCF and is not automatically treated as FCFE.

Missing quantified borrowing debt for ALAB/CRDO stays unavailable rather than zero. ROIC is available only where matched beginning/end capital, debt, cash and effective tax inputs support the stated book-capital definition. Source hashes, exact components, notes and filing cutoffs are retained in `results/2026-10-01/decision-fundamentals.json` and `data/2026-10-01/investment-decision/`.

AI bottleneck evidence is a company-specific quarterly review checklist: capacity, qualification, customer concentration, order conversion, margins, spending and cash/share economics. These are analytical prompts and thesis break conditions, not measured live shortage or backlog indices. Existing eight-company target styles remain illustrative; AMD and INTC are additional watchlist research. Actual capital, owned weights and contributions have not been provided. Drift and sizing standards therefore remain planning inputs, rather than actual portfolio triggers.

IDR stress compounds the same-period USD sleeve return with USD/IDR movement: `(1 + USD return) × (1 + FX change) − 1`. The current AI style supplies target weights, with no assumed outside reserve or owned positions. A −50% equity shock plus −10% USD/IDR shock produces −55% IDR return. Stronger IDR can add to losses for an Indonesian investor holding USD assets. These shocks have no probability or worst-case claim.

Historical model health shows retained RMSE against mean/zero baselines and purged interval coverage. It does not validate long-term business assumptions. The separate forward register freezes 5/20-session model predictions with source/report hashes, UTC registration and last training target. Registration must precede the first post-origin regular session open. The initial batch contains 182 records: 168 eligible/pending US records, 14 late/excluded IHSG records, and zero matured outcomes. A future outcome remains unavailable until its full horizon has completed. No prospective accuracy is fabricated.

The local `/api/forecast-monitor` endpoint checks at most once per 15 minutes when requested. The page requests it only in Model health. It scores frozen predictions against completed daily adjusted closes; it does not refit or create fresh forecasts. New model snapshots require a new audited quant run and registration before their first post-origin session. Offline HTML retains the embedded ledger snapshot; automatic scoring requires the local service and internet. Each settlement stores its outcome data vintage and raw-response hash. Late/unknown registrations never become eligible retrospectively.

Rebuild and verify from the project root:

```powershell
python market_models/test_decision_math.py
python market_models/test_forecast_monitor.py
python market_models/combine_reports.py
python market_models/verify_combined.py
node --check market_models/results/2026-09-29/combined-script-check.js
node market_models/verify_decision.cjs
node market_models/verify_live.cjs
```

The HTML includes all display data and new interface assets. It remains usable as a saved file; `Start-Live-Dashboard.cmd` starts the loopback service for quotes and forward outcomes. Formula tests independently compare browser JavaScript with Python. Integration tests cover 60 company/view combinations, ticker routes, missing/loss inputs, live-refresh preservation and IDR arithmetic. Browser checks cover desktop and narrow mobile layout. No broker credentials or order execution are involved.
