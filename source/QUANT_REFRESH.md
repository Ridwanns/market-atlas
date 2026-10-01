# Refreshed quant workspace — 30 September 2026

The single English dashboard now fits ten stocks (NVDA, TSM ADR, INTC, AMD, MU, AVGO, ETN, VRT, ALAB, CRDO) and three price indices (S&P 500, Nasdaq Composite, IHSG). Select a ticker, open Research → All stock models, or use the company’s Open quant models button in AI Portfolio. One Explore selector controls the graphs; exact results and sources stay inside a closed disclosure.

Daily models use completed sessions through 30 September. Public quotes and USD/IDR refresh every 60 seconds and carry their observation dates, session and provider delay where available. A quote refresh does not retrain a model or refresh earnings, options or valuation inputs. Live prices require the local service started by `Start-Live-Dashboard.cmd`.

Each asset has Ridge, OLS, KNN-50, interpreted histogram gradient boosting, AR(1), expanding-mean and zero-return forecasts at 5 and 20 trading sessions. Evaluation includes chronological matured labels, train-only feature scaling, nonoverlapping scored origins, RMSE/MAE/direction accuracy, baseline comparisons, past-error intervals and a separately fitted purged split-conformal boosting study. Low historical error is not a validated trading edge; retrospective model ranking is visible rather than treated as a buy signal.

Other families include Gaussian GARCH(1,1), EWMA and rolling variance; HAR on a Garman–Klass OHLC proxy; forward-filtered two-state Gaussian HMM; rolling historical VaR/ES and exceptions; Kalman SPY beta where currency definitions match; CAPM, FF3 and FF5 with three-lag HAC uncertainty; delayed MA20/MA50 timing with trading-cost comparisons; and two seeded 5,000-path scenario studies with interactive fans and terminal histograms. Factor data ends August 2026. IHSG does not receive a substituted USD factor/beta model. Stock adjusted-close proxies and local price indices have different dividend/currency definitions.

ALAB has 635 actual price observations and only 35 five-session / 8 twenty-session scored origins. Its twenty-session empirical and purged intervals remain unavailable. ALAB and CRDO use a disclosed 252-label training threshold; longer histories use 756. Risk windows and counts are shown. VRT’s linked provider history before 10 February 2020 includes its predecessor/SPAC phase.

The new boosting model uses fixed 80-round histogram regression stumps (learning rate 0.05, 32 bins, minimum leaf 40, L2 10). Two-state Gaussian HMM training uses an interpreted scaled EM implementation, with forward filtering only during evaluation. These are explicitly documented repository adaptations; they do not claim numerical identity with the archived sklearn/hmmlearn implementations. Current fitted parameters never enter historical test scores.

Three AI portfolio styles also have 252 shared-session USD risk studies: covariance with 10% diagonal shrinkage, annual volatility, variance contributions, costed daily constant-weight historical replay and historical VaR/ES. Current illustrative weights are replayed retrospectively; these are neither optimized allocations nor a point-in-time strategy. FX and taxes are excluded. Statistical 5/20-session results are not validated 5–10-year investment forecasts, and current intrinsic valuation is outside this refresh.

Reproduce using the existing Python environment:

```powershell
python market_models/ai_quant.py
python market_models/verify_ai_quant.py
python market_models/combine_reports.py
python market_models/verify_combined.py
node market_models/verify_live.cjs
```

Use `--reuse-models` on the first command to assemble the already fitted new snapshot without retraining. Raw responses, CSVs and individual fits are in `data/2026-09-30/quant-refresh/`; the complete new report and independent verification are in `results/2026-09-30/`. Raw and implementation hashes, inspected repository source paths and exact adaptation settings are retained. The original 29 September analytical bundle and embedded research modules remain unchanged.
