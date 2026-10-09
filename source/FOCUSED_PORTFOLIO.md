# Focused Market Atlas dashboard

Selected on 9 October 2026: NVDA 40%, TSM 25%, MU 20%, SPY 15%.

These are user-selected equity target weights, not verified owned positions,
optimized weights, trade orders or current buy ratings. Emergency funds and
dated IDR spending requirements are outside this 100% equity illustration.
SPY is a broad equity ETF; its holdings can overlap with the direct stocks.
No live fund-holdings look-through or aggregate NVDA/MU exposure is invented.

The primary watchlist and portfolio show only these four holdings. Quant
navigation also keeps S&P 500, Nasdaq Composite and IHSG. The company decision
workspace focuses on NVDA, TSM and MU; SPY uses an ETF context and its own quant
models without substituting corporate EPS scenarios. Original research is
retained in dated archives.

SPY is fitted from its retained adjusted-close CSV using the same 30 September
2026 quant protocol, including forecast baselines, conformal intervals, GARCH,
HAR, filtered HMM, tail risk, simulations, factor attribution and timing.
The extension is dated 9 October; it does not claim an October 9 model cutoff.
Adding these models does not backdate a prospective SPY forecast registration.

Portfolio diagnostics use four matched price series, 253 prices / 252 returns,
10% diagonal covariance shrinkage and the explicit 40/25/20/15 target vector.
Historical replay uses daily constant weights, 10 bps per traded notional,
including entry. Displayed NAV, drawdown, VaR/ES and variance contributions are
computed for this basket. FX, taxes and real execution constraints are excluded.
This retrospective basket and period are not a point-in-time strategy backtest.

Rebuild: `python focus_portfolio.py`, then `python build_focus_dashboard.py`.
Package: `python publish_github_pages.py`, preserving newer remote snapshots.
The original quant bundle and fundamentals stay frozen. Prices use the existing
separately dated quote service and published weekday snapshot workflow.

## Animated model explorer

The existing quant panel now has Play/Pause, Restart, a scrubber and 0.5×/1×/2×
speed controls. It plays once on opening; reduced-motion preferences show the
complete charts without automatic playback. Leaving the panel or hiding the
browser pauses playback. No additional tabs are introduced.

Historical charts reveal retained dated observations within each chart's own
range, including forecasts/errors, volatility, regime/beta, drawdown and timing.
Monte Carlo reveals the same stored seeded paths and pointwise bands session by
session; its histogram remains the explicitly labelled full-horizon distribution.
Factor coefficients use a labelled visual reveal of a fixed fit. No estimates,
fits, simulation seeds, risk statistics or data vintages change with playback.

Animation QA covered all 56 asset/view combinations, both simulation methods for
the four holdings, exact retained percentile readouts, play/pause, speed, restart,
keyboard/slider inspection, 5/20-session horizons, path toggle and 390px layout.

Verification: 30 Python checks passed, including independent alignment/covariance
checks, retained arithmetic, quote regressions and ledger eligibility. Browser
checks covered 56 quant asset/view combinations, budget weights and amounts,
ETF/company routing, home navigation from indices and a 390px mobile viewport.
