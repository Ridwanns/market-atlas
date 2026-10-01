"""Independent reproducible arithmetic for decision-math.js; rates are decimals.

These functions calculate editable scenarios, never forecasts or trade signals.
See DECISION_MATH.md for currencies, quoted-share units, timing, and sources.
"""
from __future__ import annotations

import math


def _finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _absent(value):
    return value is None or value == ""


def _power(base, exponent):
    try:
        return math.pow(base, exponent)
    except (OverflowError, ValueError):
        return math.inf


def _divide(numerator, denominator):
    if denominator == 0:
        return math.nan if numerator == 0 else math.copysign(math.inf, numerator)
    return numerator / denominator


def _result(status, errors=None, **extra):
    return dict(ok=status == "ok", status=status, errors=errors or [], **extra)


def _empty_scenario():
    return dict(terminalRevenueBillionsUsd=None, terminalSharesBillions=None,
                terminalNetIncomeBillionsUsd=None, terminalEpsUsd=None,
                terminalPriceUsd=None, cagrUsd=None, cagrIdr=None,
                totalReturnUsd=None, totalReturnIdr=None, maxPriceUsd=None,
                dividendsTotalUsd=None, irrUsd=None, path=[])


def _number_check(inputs, key, errors, predicate=None, message="", optional=False):
    value = inputs.get(key)
    if optional and _absent(value):
        return
    if not _finite(value):
        errors.append(key + (" is missing." if _absent(value) else " must be a finite number."))
    elif predicate is not None and not predicate(value):
        errors.append(key + " " + message)


def _scenario_checks(inputs, eps_mode=False):
    errors = []
    _number_check(inputs, "priceUsd", errors, lambda x: x > 0, "must be positive.")
    _number_check(inputs, "years", errors, lambda x: int(x) == x and 0 < x <= 100,
                  "must be an integer from 1 to 100.")
    _number_check(inputs, "earningsGrowth" if eps_mode else "revenueGrowth", errors,
                  lambda x: x >= -1, "must be at least -100%.")
    _number_check(inputs, "dilution", errors, lambda x: x > -1, "must be greater than -100%.")
    _number_check(inputs, "exitPe", errors, lambda x: x > 0, "must be positive.")
    _number_check(inputs, "requiredReturn", errors, lambda x: x > -1,
                  "must be greater than -100%.", optional=True)
    _number_check(inputs, "annualFxChange", errors, lambda x: x > -1,
                  "must be greater than -100%.", optional=True)
    if eps_mode:
        _number_check(inputs, "baseEpsUsd", errors)
    else:
        _number_check(inputs, "revenueBillionsUsd", errors, lambda x: x >= 0, "cannot be negative.")
        _number_check(inputs, "dilutedSharesBillions", errors, lambda x: x > 0, "must be positive.")
        _number_check(inputs, "netMargin", errors)
    if not _absent(inputs.get("currency")) and inputs["currency"] != "USD":
        errors.append("currency must be USD; convert the base first.")
    if not _absent(inputs.get("listingBasis")) and inputs["listingBasis"] != "quoted-share":
        errors.append("listingBasis must be quoted-share, including ADR conversion.")
    dividends = inputs.get("dividendsPerShareUsd")
    if not _absent(dividends):
        values = dividends if isinstance(dividends, list) else [dividends]
        if any(not _finite(x) or x < 0 for x in values):
            errors.append("dividendsPerShareUsd must contain nonnegative finite USD amounts.")
        if isinstance(dividends, list) and len(dividends) != inputs.get("years"):
            errors.append("dividendsPerShareUsd must have one amount for each year.")
    return errors


def _receipt_irr(price, receipts):
    if all(value == 0 for value in receipts):
        return -1

    def npv(rate):
        return sum(_divide(value, _power(1 + rate, i + 1)) for i, value in enumerate(receipts)) - price

    low, high = -.999999999, 1.
    while npv(high) > 0 and high < 1e12:
        high = high * 2 + 1
    if npv(high) > 0:
        return None
    for _ in range(180):
        middle = (low + high) / 2
        if npv(middle) > 0:
            low = middle
        else:
            high = middle
    return (low + high) / 2


def _finish_scenario(inputs, path, **extra):
    base = _empty_scenario()
    base.update(extra, path=path, terminalEpsUsd=path[-1]["epsUsd"])
    if any(isinstance(value, (int, float)) and not math.isfinite(value)
           for row in path for value in row.values()):
        return _result("invalid", ["The assumptions overflow the model; use smaller rates or horizon."], **_empty_scenario())
    if path[-1]["epsUsd"] <= 0:
        return _result("loss-making", ["P/E valuation is unavailable when terminal earnings are zero or negative."], **base)
    terminal_price = path[-1]["epsUsd"] * inputs["exitPe"]
    dividends = inputs.get("dividendsPerShareUsd")
    years = int(inputs["years"])
    if _absent(dividends):
        dividends = [0] * years
    elif not isinstance(dividends, list):
        dividends = [dividends] * years
    dividend_total = sum(dividends)
    receipts = dividends.copy()
    receipts[-1] += terminal_price
    hurdle = inputs.get("requiredReturn")
    max_price = None if _absent(hurdle) else sum(_divide(value, _power(1 + hurdle, i + 1))
                                               for i, value in enumerate(receipts))
    calculated = dict(terminalPriceUsd=terminal_price,
                      cagrUsd=_power(terminal_price / inputs["priceUsd"], 1 / years) - 1,
                      totalReturnUsd=(terminal_price + dividend_total) / inputs["priceUsd"] - 1,
                      maxPriceUsd=max_price, dividendsTotalUsd=dividend_total,
                      irrUsd=_receipt_irr(inputs["priceUsd"], receipts))
    fx = inputs.get("annualFxChange")
    if not _absent(fx):
        calculated["cagrIdr"] = (1 + calculated["cagrUsd"]) * (1 + fx) - 1
        calculated["totalReturnIdr"] = sum(value * _power(1 + fx, i + 1)
                                           for i, value in enumerate(receipts)) / inputs["priceUsd"] - 1
    if any(value is not None and not _finite(value) for value in calculated.values()):
        return _result("invalid", ["The valuation overflowed; use smaller rates or horizon."], **base)
    base.update(calculated)
    return _result("ok", **base)


def scenario(inputs=None):
    inputs = inputs or {}
    errors = _scenario_checks(inputs)
    if errors:
        return _result("missing" if any(" is missing." in x for x in errors) else "invalid", errors, **_empty_scenario())
    path = []
    for year in range(1, int(inputs["years"]) + 1):
        revenue = inputs["revenueBillionsUsd"] * _power(1 + inputs["revenueGrowth"], year)
        shares = inputs["dilutedSharesBillions"] * _power(1 + inputs["dilution"], year)
        earnings = revenue * inputs["netMargin"]
        eps = _divide(earnings, shares)
        path.append(dict(year=year, revenueBillionsUsd=revenue, sharesBillions=shares,
                         netIncomeBillionsUsd=earnings, epsUsd=eps,
                         priceUsd=eps * inputs["exitPe"] if eps > 0 else None))
    terminal = path[-1]
    return _finish_scenario(inputs, path, terminalRevenueBillionsUsd=terminal["revenueBillionsUsd"],
                            terminalSharesBillions=terminal["sharesBillions"],
                            terminalNetIncomeBillionsUsd=terminal["netIncomeBillionsUsd"])


def scenario_eps(inputs=None):
    inputs = inputs or {}
    errors = _scenario_checks(inputs, eps_mode=True)
    if errors:
        return _result("missing" if any(" is missing." in x for x in errors) else "invalid", errors, **_empty_scenario())
    path = []
    for year in range(1, int(inputs["years"]) + 1):
        eps = inputs["baseEpsUsd"] * _power((1 + inputs["earningsGrowth"]) / (1 + inputs["dilution"]), year)
        path.append(dict(year=year, revenueBillionsUsd=None, sharesBillions=None,
                         netIncomeBillionsUsd=None, epsUsd=eps,
                         priceUsd=eps * inputs["exitPe"] if eps > 0 else None))
    return _finish_scenario(inputs, path)


def equity_dcf(inputs=None):
    inputs = inputs or {}
    errors = []
    empty = dict(valuePerShareUsd=None, pvForecastUsd=None, terminalValueUsd=None,
                 pvTerminalUsd=None, terminalValueShare=None, path=[])
    if inputs.get("cashFlowType") != "FCFE":
        errors.append("cashFlowType must explicitly be FCFE; CFO minus capex alone is not sufficient.")
    if inputs.get("currency") != "USD":
        errors.append("currency must explicitly be USD.")
    if inputs.get("listingBasis") != "quoted-share":
        errors.append("listingBasis must explicitly be quoted-share.")
    _number_check(inputs, "costOfEquity", errors, lambda x: x > -1, "must be greater than -100%.")
    _number_check(inputs, "terminalGrowth", errors, lambda x: x > -1, "must be greater than -100%.")
    rate, growth = inputs.get("costOfEquity"), inputs.get("terminalGrowth")
    if _finite(rate) and _finite(growth) and rate <= growth:
        errors.append("costOfEquity must exceed terminalGrowth.")
    forecast = inputs.get("fcfePerShareForecastUsd")
    if isinstance(forecast, list):
        if not 1 <= len(forecast) <= 100 or any(not _finite(x) for x in forecast):
            errors.append("fcfePerShareForecastUsd must have 1 to 100 finite annual USD values.")
    else:
        _number_check(inputs, "fcfePerShareUsd", errors)
        _number_check(inputs, "fcfeGrowth", errors, lambda x: x >= -1, "must be at least -100%.")
        _number_check(inputs, "years", errors, lambda x: int(x) == x and 0 < x <= 100,
                      "must be an integer from 1 to 100.")
        if not errors:
            forecast = [inputs["fcfePerShareUsd"] * _power(1 + inputs["fcfeGrowth"], year)
                        for year in range(1, int(inputs["years"]) + 1)]
    if errors:
        return _result("missing" if any(" is missing." in x for x in errors) else "invalid", errors, **empty)
    if forecast[-1] <= 0:
        return _result("loss-making", ["Positive sustainable terminal FCFE is required for this perpetuity model."], **empty)
    path = [dict(year=i + 1, fcfePerShareUsd=cash,
                 presentValueUsd=_divide(cash, _power(1 + rate, i + 1))) for i, cash in enumerate(forecast)]
    pv_forecast = sum(row["presentValueUsd"] for row in path)
    terminal_value = forecast[-1] * (1 + growth) / (rate - growth)
    pv_terminal = _divide(terminal_value, _power(1 + rate, len(forecast)))
    value = pv_forecast + pv_terminal
    if not all(_finite(x) for x in (pv_forecast, terminal_value, pv_terminal, value)):
        return _result("invalid", ["The DCF assumptions overflow the model."], **empty)
    if value <= 0:
        empty["path"] = path
        return _result("unavailable", ["The modeled equity cash flows do not produce a positive value."], **empty)
    return _result("ok", valuePerShareUsd=value, pvForecastUsd=pv_forecast,
                   terminalValueUsd=terminal_value, pvTerminalUsd=pv_terminal,
                   terminalValueShare=pv_terminal / value, path=path)


def combined_return(inputs=None):
    inputs = inputs or {}
    errors = []
    _number_check(inputs, "assetReturn", errors, lambda x: x >= -1, "must be at least -100%.")
    _number_check(inputs, "fxReturn", errors, lambda x: x >= -1, "must be at least -100%.")
    if errors:
        return _result("invalid", errors, returnIdr=None)
    value = (1 + inputs["assetReturn"]) * (1 + inputs["fxReturn"]) - 1
    if not _finite(value):
        return _result("invalid", ["The returns overflow the model."], returnIdr=None)
    return _result("ok", returnIdr=value)


def compound_idr(inputs=None):
    inputs = inputs or {}
    return combined_return(dict(assetReturn=inputs.get("usdReturn"), fxReturn=inputs.get("fxReturn")))


def portfolio_stress(inputs=None):
    inputs = inputs or {}
    errors = []
    _number_check(inputs, "fxReturn", errors, lambda x: x >= -1, "must be at least -100%.")
    positions = inputs.get("positions")
    if not isinstance(positions, list):
        errors.append("positions must be an array.")
    cash = inputs.get("cashWeight")
    cash = 0 if _absent(cash) else cash
    _number_check(dict(cashWeight=cash), "cashWeight", errors, lambda x: 0 <= x <= 1, "must be between 0 and 1.")
    currency = inputs.get("cashCurrency") or "IDR"
    if currency not in ("IDR", "USD"):
        errors.append("cashCurrency must be IDR or USD.")
    if isinstance(positions, list):
        for i, position in enumerate(positions):
            if not isinstance(position, dict):
                errors.append(f"position {i} must be an object.")
                continue
            row_errors = []
            _number_check(position, "weight", row_errors, lambda x: 0 <= x <= 1, "must be between 0 and 1.")
            _number_check(position, "assetReturn", row_errors, lambda x: x >= -1, "must be at least -100%.")
            errors.extend(f"position {i}: {error}" for error in row_errors)
    weight_total = (sum(p["weight"] for p in positions) + cash
                    if isinstance(positions, list) and _finite(cash)
                    and all(isinstance(p, dict) and _finite(p.get("weight")) for p in positions) else None)
    if weight_total is not None and abs(weight_total - 1) > 1e-8:
        errors.append("Position weights plus cashWeight must total 1.")
    if errors:
        return _result("invalid", errors, returnIdr=None, returnUsd=None, rows=[], weightTotal=weight_total)
    fx = inputs["fxReturn"]
    rows = [dict(symbol=p.get("symbol") or "", weight=p["weight"], returnUsd=p["assetReturn"],
                 returnIdr=(1 + p["assetReturn"]) * (1 + fx) - 1,
                 contributionIdr=p["weight"] * ((1 + p["assetReturn"]) * (1 + fx) - 1)) for p in positions]
    cash_return = fx if currency == "USD" else 0
    usd_return = (None if currency == "IDR" and cash > 0 and fx == -1 else
                  sum(p["weight"] * p["assetReturn"] for p in positions)
                  + (cash * (1 / (1 + fx) - 1) if currency == "IDR" and fx > -1 else 0))
    idr_return = sum(p["contributionIdr"] for p in rows) + cash * cash_return
    if (not _finite(idr_return) or (usd_return is not None and not _finite(usd_return))
            or any(not _finite(row["returnIdr"]) or not _finite(row["contributionIdr"]) for row in rows)):
        return _result("invalid", ["The stress assumptions overflow the model."],
                       returnIdr=None, returnUsd=None, rows=[], weightTotal=weight_total)
    return _result("ok", returnIdr=idr_return,
                   returnUsd=usd_return, rows=rows, cashWeight=cash, cashCurrency=currency,
                   cashReturnIdr=cash_return, weightTotal=weight_total)


def monthly_budget(inputs=None):
    inputs = inputs or {}
    errors = []
    _number_check(inputs, "budgetIdr", errors, lambda x: x >= 0, "cannot be negative.")
    _number_check(inputs, "usdIdr", errors, lambda x: x > 0, "must be positive IDR per USD.")
    _number_check(inputs, "fxSpread", errors, lambda x: 0 <= x < 1, "must be between 0 and less than 1.")
    _number_check(inputs, "brokerFeeRate", errors, lambda x: 0 <= x < 1, "must be between 0 and less than 1.")
    fixed = inputs.get("brokerFeeUsd")
    fixed = 0 if _absent(fixed) else fixed
    _number_check(dict(brokerFeeUsd=fixed), "brokerFeeUsd", errors, lambda x: x >= 0, "cannot be negative.")
    empty = dict(investableUsd=None, convertedUsd=None, fxCostIdr=None,
                 brokerFeeUsd=None, brokerCostIdr=None, totalCostIdr=None)
    if errors:
        return _result("invalid", errors, **empty)
    converted = inputs["budgetIdr"] / (inputs["usdIdr"] * (1 + inputs["fxSpread"]))
    if not _finite(converted):
        return _result("invalid", ["The budget assumptions overflow the model."], **empty)
    if fixed > converted:
        return _result("infeasible", ["The fixed broker fee exceeds the converted budget."], **empty)
    invested = (converted - fixed) / (1 + inputs["brokerFeeRate"])
    broker_fee = invested * inputs["brokerFeeRate"] + fixed
    output = dict(investableUsd=invested, convertedUsd=converted,
                   fxCostIdr=inputs["budgetIdr"] - converted * inputs["usdIdr"],
                   brokerFeeUsd=broker_fee, brokerCostIdr=broker_fee * inputs["usdIdr"],
                   totalCostIdr=inputs["budgetIdr"] - invested * inputs["usdIdr"])
    if not all(_finite(x) for x in output.values()):
        return _result("invalid", ["The budget assumptions overflow the model."], **empty)
    return _result("ok", **output)
