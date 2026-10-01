# Investment Decision arithmetic

Research checked 1 October 2026. These are transparent calculators for user-selected assumptions. Bear, base, and bull labels carry no probabilities. Neither their returns nor any target entry price is a fitted forecast, an investment recommendation, or evidence of a likely outcome. Defaults in the interface must say **illustrative assumptions** and remain editable.

## Basis and sources

The terminal multiple approach applies an **equity** multiple to per-share equity earnings. The selected exit P/E materially affects the scenario and does not convert it into intrinsic DCF value. [Aswath Damodaran, NYU Stern: Estimating Terminal Value](https://pages.stern.nyu.edu/~adamodar/New_Home_Page/valquestions/termvalapproaches.htm).

DCF must match its cash flows to its discount rate: equity cash flows use cost of equity; enterprise cash flows use cost of capital and require adjustments to reach equity value. The optional calculator here accepts only **FCFE per quoted share**, not enterprise cash flows. [Damodaran: An Introduction to Valuation](https://pages.stern.nyu.edu/~adamodar/New_Home_Page/background/valintro.htm).

Income, cash flow, and share counts are separate measures. [SEC: Beginners' Guide to Financial Statements](https://www.sec.gov/about/reports-publications/beginners-guide-financial-statements). Diluted EPS incorporates potential dilution. [SEC filing: EPS accounting note](https://www.sec.gov/Archives/edgar/data/1098151/000143774926026575/R13.htm). Cash from operations less capex is displayed as a reported cash-generation measure when available; it is not silently relabeled FCFE, which also depends on financing and other equity claims. [Damodaran: Equity Valuation and FCFE](https://pages.stern.nyu.edu/~adamodar/New_Home_Page/lectures/val.html).

## Revenue, earnings, dilution, and exit P/E

For annual revenue growth `g`, terminal net margin `m`, annual dilution `d`, and horizon `N`:

```
revenueN = revenue0 × (1 + g)^N
sharesN = quoted-share dilutedShares0 × (1 + d)^N
netIncomeN = revenueN × m
EPSN = netIncomeN / sharesN
terminalPriceUSD = EPSN × exitPE
price CAGRUSD = (terminalPriceUSD / entryPriceUSD)^(1/N) − 1
maximumEntryUSD = terminalPriceUSD / (1 + requiredUSDReturn)^N
```

Revenue and shares are both in **billions**, so their scale cancels into USD per share. Historical revenue is the reported base, rather than an inferred forward forecast. The terminal margin and exit multiple are scenario assumptions. `path` holds years 1 through N; the same assumed margin and multiple are applied each year, so the graph is an illustrative earnings path and not a market-price forecast.

`d > 0` means net dilution; `d < 0` represents net share reduction. Shares include the latest stated diluted-share basis and its date; outstanding shares and weighted-average diluted shares have different meanings. Terminal earnings at or below zero remain visible, but P/E price, CAGR, and target entry become **unavailable**. They are never represented as a zero target price.

TSM requires two separate unit conversions: native-currency revenue into USD using an explicitly sourced dated conversion, and ordinary diluted shares divided by the number represented by one ADR. The math names require USD and quoted-share units; passing `currency: 'TWD'` or `listingBasis: 'ordinary-share'` is rejected. A spot translation of historical TWD revenue is an estimate, not the exact sum of each reporting period's USD revenue. A historical conversion does not assume a future TWD/USD path.

Optional dividends are either one constant annual USD amount per share or an array of annual amounts, paid at year end. Defaults exclude dividends. `cagrUsd` remains **price only**, `totalReturnUsd` includes dividends held as cash without reinvestment, and `irrUsd` includes their timing. With dividends, maximum entry is the present value of every annual dividend plus terminal proceeds at the selected required return. Taxes, withholding, future reinvestment, and sell fees are not included.

## Optional equity DCF

Provide explicit yearly USD **FCFE per quoted share** forecasts, or a valid FCFE base with a per-share growth assumption. Per-share FCFE growth must already reflect dilution. The interface must keep this method unavailable until the input basis is established or a user supplies it. It must not substitute raw CFO minus capex automatically.

```
terminalEquityPerShareN = FCFEN × (1 + terminalGrowth) / (costOfEquity − terminalGrowth)
equityValuePerShare0 = Σ FCFEt / (1 + costOfEquity)^t
                     + terminalEquityPerShareN / (1 + costOfEquity)^N
```

Sustainable terminal FCFE must be positive; `costOfEquity > terminalGrowth`. Negative early cash flows can be modeled with an explicit annual array. Terminal cash is year **N+1**; terminal value is discounted from **N**, avoiding an extra or missing discount year. This is equity valuation, so no net-debt subtraction is applied. The output includes the fraction of modeled value attributable to terminal value to expose sensitivity. Constant growth perpetuities require economically sustainable assumptions; mathematical validity alone cannot establish that.

## IDR stress and costs

The FX rate is **IDR per USD**. Positive FX change means USD strengthens against IDR; negative change means IDR strengthens.

```
stockReturnIDR = (1 + stockReturnUSD) × (1 + USDIDRchange) − 1
portfolioReturnIDR = Σ weighti × stockReturnIDRi + cashWeight × cashReturnIDR
```

Weights represent starting values and must sum to one, including explicit cash. IDR cash has zero nominal IDR return; USD cash receives the FX change. Scenarios hold weights at their initial values and do not trade or rebalance during the shock. Portfolio styles are target allocations, not evidence of positions held. A stock shock and an FX shock are cumulative over the same period. In `scenario`, optional `annualFxChange` instead means annual FX growth over N years; `cagrIdr` is the price-only USD CAGR combined with that annual change. Dividend cash is converted separately at the modeled year-end FX factor.

For an IDR monthly budget, an FX spread that increases the purchase rate, a proportional commission on invested USD, and a fixed USD commission:

```
convertedUSD = budgetIDR / [midUSDIDR × (1 + FXspread)]
investableUSD = (convertedUSD − fixedCommissionUSD) / (1 + commissionRate)
FXcostIDR = budgetIDR − convertedUSD × midUSDIDR
brokercostIDR = (investableUSD × commissionRate + fixedCommissionUSD) × midUSDIDR
totalCostIDR = budgetIDR − investableUSD × midUSDIDR
```

The two costs reconcile to the budget exactly, without charging spread or commission twice. Real broker tariffs may have minimums, tiering, taxes, or other fees; use explicit applicable fee inputs rather than treating illustrative defaults as a broker quote. Future monthly purchases need a separate price/FX path and cannot be modeled as one upfront investment.

## Browser API

Load `decision-math.js`; it exposes `window.DecisionMath` and CommonJS `module.exports`. Rates are decimals, never percentage integers. Functions do not mutate inputs. Every return includes `{ok, status, errors}`. Missing or invalid inputs produce null outcomes rather than zero. There is no probability or trading-action output.

| Function | Inputs | Key outputs |
|---|---|---|
| `scenario` | `priceUsd`, `revenueBillionsUsd`, `dilutedSharesBillions`, `years`, `revenueGrowth`, `netMargin`, `dilution`, `exitPe`; optional `requiredReturn`, `annualFxChange`, `dividendsPerShareUsd`, `currency`, `listingBasis` | `terminalRevenueBillionsUsd`, `terminalSharesBillions`, `terminalNetIncomeBillionsUsd`, `terminalEpsUsd`, `terminalPriceUsd`, `cagrUsd`, `cagrIdr`, `totalReturnUsd`, `totalReturnIdr`, `maxPriceUsd`, `dividendsTotalUsd`, `irrUsd`, `path` |
| `scenarioEps` | Same common inputs as `scenario`, with `baseEpsUsd` and `earningsGrowth` replacing revenue/shares/margin | Same outputs; revenue/shares/total income are null |
| `equityDcf` | `cashFlowType:'FCFE'`, `currency:'USD'`, `listingBasis:'quoted-share'`, `costOfEquity`, `terminalGrowth`, plus `fcfePerShareForecastUsd` array **or** `fcfePerShareUsd`, `fcfeGrowth`, `years` | `valuePerShareUsd`, `pvForecastUsd`, `terminalValueUsd`, `pvTerminalUsd`, `terminalValueShare`, `path` |
| `combinedReturn` | `assetReturn`, `fxReturn` | `returnIdr` |
| `compoundIdr` | `usdReturn`, `fxReturn` | `returnIdr` (alias using USD name) |
| `portfolioStress` | `positions:[{symbol,weight,assetReturn}]`, `fxReturn`; optional `cashWeight` (0), `cashCurrency` ('IDR') | `returnIdr`, `returnUsd`, `rows`, `weightTotal`, `cashWeight`, `cashCurrency`, `cashReturnIdr` |
| `monthlyBudget` | `budgetIdr`, `usdIdr`, `fxSpread`, `brokerFeeRate`; optional fixed `brokerFeeUsd` (0) | `investableUsd`, `convertedUsd`, `fxCostIdr`, `brokerFeeUsd`, `brokerCostIdr`, `totalCostIdr` |

`scenarioEps.earningsGrowth` is growth of total earnings before incremental dilution, not reported EPS growth. If a forecast EPS already includes future dilution, do not deduct dilution a second time. A negative initial EPS cannot recover through positive constant multiplication; use the revenue/margin route to model a profitability change.

Horizon is an integer from 1 to 100. Entry price, shares, and exit P/E must be positive. Revenue growth can reach -100%; dilution and required return must exceed -100%. Negative terminal margins are allowed. Non-numeric, infinite, or missing financial inputs are rejected. Cash at a zero modeled USD/IDR rate has no finite USD value, so its USD return is null while its nominal IDR return remains defined.

## Verification

`test_decision_math.py` checks hand-calculated price/share scale, ADR share representation, dilution/buybacks, missing and negative earnings, dividend timing, DCF discount years, FX direction, portfolio weights/cash denomination, and fee reconciliation. It also executes the actual browser JavaScript with Node and compares it with the Python reproduction. Run from `market_models`:

```
python -m unittest test_decision_math -v
```
