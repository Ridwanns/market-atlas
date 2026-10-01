/* Transparent USD-equity scenarios and IDR stress arithmetic. See DECISION_MATH.md. */
(function (root) {
  'use strict';
  const finite = x => typeof x === 'number' && Number.isFinite(x);
  const absent = x => x === null || x === undefined || x === '';
  const result = (status, errors, extra) => Object.assign({ok: status === 'ok', status, errors: errors || []}, extra || {});
  const emptyScenario = () => ({terminalRevenueBillionsUsd: null, terminalSharesBillions: null,
    terminalNetIncomeBillionsUsd: null, terminalEpsUsd: null, terminalPriceUsd: null,
    cagrUsd: null, cagrIdr: null, totalReturnUsd: null, totalReturnIdr: null, maxPriceUsd: null,
    dividendsTotalUsd: null, irrUsd: null, path: []});

  function numberCheck(input, key, errors, predicate, message, optional) {
    if (optional && absent(input[key])) return;
    if (!finite(input[key])) errors.push(key + (absent(input[key]) ? ' is missing.' : ' must be a finite number.'));
    else if (predicate && !predicate(input[key])) errors.push(key + ' ' + message);
  }

  function scenarioChecks(input, epsMode) {
    const errors = [];
    numberCheck(input, 'priceUsd', errors, x => x > 0, 'must be positive.');
    numberCheck(input, 'years', errors, x => Number.isInteger(x) && x > 0 && x <= 100, 'must be an integer from 1 to 100.');
    numberCheck(input, epsMode ? 'earningsGrowth' : 'revenueGrowth', errors, x => x >= -1, 'must be at least -100%.');
    numberCheck(input, 'dilution', errors, x => x > -1, 'must be greater than -100%.');
    numberCheck(input, 'exitPe', errors, x => x > 0, 'must be positive.');
    numberCheck(input, 'requiredReturn', errors, x => x > -1, 'must be greater than -100%.', true);
    numberCheck(input, 'annualFxChange', errors, x => x > -1, 'must be greater than -100%.', true);
    if (epsMode) numberCheck(input, 'baseEpsUsd', errors);
    else {
      numberCheck(input, 'revenueBillionsUsd', errors, x => x >= 0, 'cannot be negative.');
      numberCheck(input, 'dilutedSharesBillions', errors, x => x > 0, 'must be positive.');
      numberCheck(input, 'netMargin', errors);
    }
    if (!absent(input.currency) && input.currency !== 'USD') errors.push('currency must be USD; convert the base first.');
    if (!absent(input.listingBasis) && input.listingBasis !== 'quoted-share') errors.push('listingBasis must be quoted-share, including ADR conversion.');
    if (!absent(input.dividendsPerShareUsd)) {
      const dividends = Array.isArray(input.dividendsPerShareUsd) ? input.dividendsPerShareUsd : [input.dividendsPerShareUsd];
      if (dividends.some(x => !finite(x) || x < 0)) errors.push('dividendsPerShareUsd must contain nonnegative finite USD amounts.');
      if (Array.isArray(input.dividendsPerShareUsd) && input.dividendsPerShareUsd.length !== input.years)
        errors.push('dividendsPerShareUsd must have one amount for each year.');
    }
    return errors;
  }

  // There is one initial outflow and nonnegative annual receipts, so the IRR is unique.
  function receiptIrr(price, annualReceipts) {
    if (annualReceipts.every(x => x === 0)) return -1;
    const npv = rate => annualReceipts.reduce((sum, value, i) => sum + value / Math.pow(1 + rate, i + 1), 0) - price;
    let lo = -0.999999999, hi = 1;
    while (npv(hi) > 0 && hi < 1e12) hi = hi * 2 + 1;
    if (npv(hi) > 0) return null;
    for (let i = 0; i < 180; i++) {
      const mid = (lo + hi) / 2;
      if (npv(mid) > 0) lo = mid; else hi = mid;
    }
    return (lo + hi) / 2;
  }

  function finishScenario(input, path, extra) {
    const base = Object.assign(emptyScenario(), extra, {path});
    const terminal = path[path.length - 1];
    base.terminalEpsUsd = terminal.epsUsd;
    if (path.some(row => Object.values(row).some(value => typeof value === 'number' && !Number.isFinite(value))))
      return result('invalid', ['The assumptions overflow the model; use smaller rates or horizon.'], emptyScenario());
    if (terminal.epsUsd <= 0)
      return result('loss-making', ['P/E valuation is unavailable when terminal earnings are zero or negative.'], base);
    const terminalPrice = terminal.epsUsd * input.exitPe;
    const dividends = absent(input.dividendsPerShareUsd) ? Array(input.years).fill(0) :
      Array.isArray(input.dividendsPerShareUsd) ? input.dividendsPerShareUsd : Array(input.years).fill(input.dividendsPerShareUsd);
    const dividendsTotal = dividends.reduce((sum, x) => sum + x, 0);
    const receipts = dividends.slice();
    receipts[receipts.length - 1] += terminalPrice;
    const maxPrice = absent(input.requiredReturn) ? null : receipts.reduce((sum, value, i) =>
      sum + value / Math.pow(1 + input.requiredReturn, i + 1), 0);
    const calculated = {terminalPriceUsd: terminalPrice, cagrUsd: Math.pow(terminalPrice / input.priceUsd, 1 / input.years) - 1,
      totalReturnUsd: (terminalPrice + dividendsTotal) / input.priceUsd - 1, maxPriceUsd: maxPrice,
      dividendsTotalUsd: dividendsTotal, irrUsd: receiptIrr(input.priceUsd, receipts)};
    if (!absent(input.annualFxChange)) {
      calculated.cagrIdr = (1 + calculated.cagrUsd) * (1 + input.annualFxChange) - 1;
      calculated.totalReturnIdr = receipts.reduce((sum, value, i) => sum + value * Math.pow(1 + input.annualFxChange, i + 1), 0) / input.priceUsd - 1;
    }
    if (Object.values(calculated).some(x => x !== null && !finite(x)))
      return result('invalid', ['The valuation overflowed; use smaller rates or horizon.'], base);
    return result('ok', [], Object.assign(base, calculated));
  }

  function scenario(input) {
    input = input || {};
    const errors = scenarioChecks(input, false);
    if (errors.length) return result(errors.some(x => x.includes(' is missing.')) ? 'missing' : 'invalid', errors, emptyScenario());
    const path = [];
    for (let year = 1; year <= input.years; year++) {
      const revenue = input.revenueBillionsUsd * Math.pow(1 + input.revenueGrowth, year);
      const shares = input.dilutedSharesBillions * Math.pow(1 + input.dilution, year);
      const earnings = revenue * input.netMargin;
      const eps = earnings / shares;
      path.push({year, revenueBillionsUsd: revenue, sharesBillions: shares, netIncomeBillionsUsd: earnings,
        epsUsd: eps, priceUsd: eps > 0 ? eps * input.exitPe : null});
    }
    const terminal = path[path.length - 1];
    return finishScenario(input, path, {terminalRevenueBillionsUsd: terminal.revenueBillionsUsd,
      terminalSharesBillions: terminal.sharesBillions, terminalNetIncomeBillionsUsd: terminal.netIncomeBillionsUsd});
  }

  function scenarioEps(input) {
    input = input || {};
    const errors = scenarioChecks(input, true);
    if (errors.length) return result(errors.some(x => x.includes(' is missing.')) ? 'missing' : 'invalid', errors, emptyScenario());
    const path = [];
    for (let year = 1; year <= input.years; year++) {
      const eps = input.baseEpsUsd * Math.pow((1 + input.earningsGrowth) / (1 + input.dilution), year);
      path.push({year, revenueBillionsUsd: null, sharesBillions: null, netIncomeBillionsUsd: null,
        epsUsd: eps, priceUsd: eps > 0 ? eps * input.exitPe : null});
    }
    return finishScenario(input, path, {});
  }

  function equityDcf(input) {
    input = input || {};
    const errors = [];
    const empty = {valuePerShareUsd: null, pvForecastUsd: null, terminalValueUsd: null, pvTerminalUsd: null,
      terminalValueShare: null, path: []};
    if (input.cashFlowType !== 'FCFE') errors.push('cashFlowType must explicitly be FCFE; CFO minus capex alone is not sufficient.');
    if (input.currency !== 'USD') errors.push('currency must explicitly be USD.');
    if (input.listingBasis !== 'quoted-share') errors.push('listingBasis must explicitly be quoted-share.');
    numberCheck(input, 'costOfEquity', errors, x => x > -1, 'must be greater than -100%.');
    numberCheck(input, 'terminalGrowth', errors, x => x > -1, 'must be greater than -100%.');
    if (finite(input.costOfEquity) && finite(input.terminalGrowth) && input.costOfEquity <= input.terminalGrowth)
      errors.push('costOfEquity must exceed terminalGrowth.');
    let forecast = input.fcfePerShareForecastUsd;
    if (Array.isArray(forecast)) {
      if (!forecast.length || forecast.length > 100 || forecast.some(x => !finite(x)))
        errors.push('fcfePerShareForecastUsd must have 1 to 100 finite annual USD values.');
    } else {
      numberCheck(input, 'fcfePerShareUsd', errors);
      numberCheck(input, 'fcfeGrowth', errors, x => x >= -1, 'must be at least -100%.');
      numberCheck(input, 'years', errors, x => Number.isInteger(x) && x > 0 && x <= 100, 'must be an integer from 1 to 100.');
      if (!errors.length) forecast = Array.from({length: input.years}, (_, i) => input.fcfePerShareUsd * Math.pow(1 + input.fcfeGrowth, i + 1));
    }
    if (errors.length) return result(errors.some(x => x.includes(' is missing.')) ? 'missing' : 'invalid', errors, empty);
    if (forecast[forecast.length - 1] <= 0) return result('loss-making', ['Positive sustainable terminal FCFE is required for this perpetuity model.'], empty);
    const path = forecast.map((cashFlow, i) => ({year: i + 1, fcfePerShareUsd: cashFlow,
      presentValueUsd: cashFlow / Math.pow(1 + input.costOfEquity, i + 1)}));
    const pvForecast = path.reduce((sum, row) => sum + row.presentValueUsd, 0);
    const terminalValue = forecast[forecast.length - 1] * (1 + input.terminalGrowth) / (input.costOfEquity - input.terminalGrowth);
    const pvTerminal = terminalValue / Math.pow(1 + input.costOfEquity, forecast.length);
    const value = pvForecast + pvTerminal;
    if (![pvForecast, terminalValue, pvTerminal, value].every(finite)) return result('invalid', ['The DCF assumptions overflow the model.'], empty);
    if (value <= 0) return result('unavailable', ['The modeled equity cash flows do not produce a positive value.'], Object.assign(empty, {path}));
    return result('ok', [], {valuePerShareUsd: value, pvForecastUsd: pvForecast, terminalValueUsd: terminalValue,
      pvTerminalUsd: pvTerminal, terminalValueShare: pvTerminal / value, path});
  }

  function combinedReturn(input) {
    input = input || {};
    const errors = [];
    numberCheck(input, 'assetReturn', errors, x => x >= -1, 'must be at least -100%.');
    numberCheck(input, 'fxReturn', errors, x => x >= -1, 'must be at least -100%.');
    if (errors.length) return result('invalid', errors, {returnIdr: null});
    const value = (1 + input.assetReturn) * (1 + input.fxReturn) - 1;
    if (!finite(value)) return result('invalid', ['The returns overflow the model.'], {returnIdr: null});
    return result('ok', [], {returnIdr: value});
  }

  function compoundIdr(input) {
    input = input || {};
    return combinedReturn({assetReturn: input.usdReturn, fxReturn: input.fxReturn});
  }

  function portfolioStress(input) {
    input = input || {};
    const errors = [];
    numberCheck(input, 'fxReturn', errors, x => x >= -1, 'must be at least -100%.');
    const positions = input.positions;
    if (!Array.isArray(positions)) errors.push('positions must be an array.');
    const cash = absent(input.cashWeight) ? 0 : input.cashWeight;
    numberCheck({cashWeight: cash}, 'cashWeight', errors, x => x >= 0 && x <= 1, 'must be between 0 and 1.');
    const cashCurrency = input.cashCurrency || 'IDR';
    if (!['IDR', 'USD'].includes(cashCurrency)) errors.push('cashCurrency must be IDR or USD.');
    if (Array.isArray(positions)) positions.forEach((position, i) => {
      if (!position || typeof position !== 'object') {errors.push('position ' + i + ' must be an object.'); return;}
      const rowErrors = [];
      numberCheck(position, 'weight', rowErrors, x => x >= 0 && x <= 1, 'must be between 0 and 1.');
      numberCheck(position, 'assetReturn', rowErrors, x => x >= -1, 'must be at least -100%.');
      errors.push(...rowErrors.map(message => 'position ' + i + ': ' + message));
    });
    const weightTotal = Array.isArray(positions) && positions.every(p => p && finite(p.weight)) && finite(cash) ?
      positions.reduce((sum, p) => sum + p.weight, cash) : null;
    if (weightTotal !== null && Math.abs(weightTotal - 1) > 1e-8) errors.push('Position weights plus cashWeight must total 1.');
    if (errors.length) return result('invalid', errors, {returnIdr: null, returnUsd: null, rows: [], weightTotal});
    const rows = positions.map(p => ({symbol: p.symbol || '', weight: p.weight, returnUsd: p.assetReturn,
      returnIdr: (1 + p.assetReturn) * (1 + input.fxReturn) - 1,
      contributionIdr: p.weight * ((1 + p.assetReturn) * (1 + input.fxReturn) - 1)}));
    const cashReturnIdr = cashCurrency === 'USD' ? input.fxReturn : 0;
    const output = {returnIdr: rows.reduce((sum, row) => sum + row.contributionIdr, cash * cashReturnIdr),
      returnUsd: cashCurrency === 'IDR' && cash > 0 && input.fxReturn === -1 ? null : positions.reduce((sum, p) => sum + p.weight * p.assetReturn, cashCurrency === 'IDR' && input.fxReturn > -1 ? cash * (1 / (1 + input.fxReturn) - 1) : 0),
      rows, cashWeight: cash, cashCurrency, cashReturnIdr, weightTotal};
    if (!finite(output.returnIdr) || (output.returnUsd !== null && !finite(output.returnUsd)) ||
        rows.some(row => !finite(row.returnIdr) || !finite(row.contributionIdr)))
      return result('invalid', ['The stress assumptions overflow the model.'], {returnIdr: null, returnUsd: null, rows: [], weightTotal});
    return result('ok', [], output);
  }

  function monthlyBudget(input) {
    input = input || {};
    const errors = [];
    numberCheck(input, 'budgetIdr', errors, x => x >= 0, 'cannot be negative.');
    numberCheck(input, 'usdIdr', errors, x => x > 0, 'must be positive IDR per USD.');
    numberCheck(input, 'fxSpread', errors, x => x >= 0 && x < 1, 'must be between 0 and less than 1.');
    numberCheck(input, 'brokerFeeRate', errors, x => x >= 0 && x < 1, 'must be between 0 and less than 1.');
    const fixed = absent(input.brokerFeeUsd) ? 0 : input.brokerFeeUsd;
    numberCheck({brokerFeeUsd: fixed}, 'brokerFeeUsd', errors, x => x >= 0, 'cannot be negative.');
    const empty = {investableUsd: null, convertedUsd: null, fxCostIdr: null, brokerFeeUsd: null, brokerCostIdr: null, totalCostIdr: null};
    if (errors.length) return result('invalid', errors, empty);
    const converted = input.budgetIdr / (input.usdIdr * (1 + input.fxSpread));
    if (!finite(converted)) return result('invalid', ['The budget assumptions overflow the model.'], empty);
    if (fixed > converted) return result('infeasible', ['The fixed broker fee exceeds the converted budget.'], empty);
    const investable = (converted - fixed) / (1 + input.brokerFeeRate);
    const brokerFee = investable * input.brokerFeeRate + fixed;
    const fxCost = input.budgetIdr - converted * input.usdIdr;
    const output = {investableUsd: investable, convertedUsd: converted, fxCostIdr: fxCost,
      brokerFeeUsd: brokerFee, brokerCostIdr: brokerFee * input.usdIdr, totalCostIdr: input.budgetIdr - investable * input.usdIdr};
    if (!Object.values(output).every(finite)) return result('invalid', ['The budget assumptions overflow the model.'], empty);
    return result('ok', [], output);
  }

  const api = Object.freeze({scenario, scenarioEps, equityDcf, combinedReturn, compoundIdr, portfolioStress, monthlyBudget, version: '1.0.0'});
  root.DecisionMath = api;
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
})(typeof window !== 'undefined' ? window : globalThis);
