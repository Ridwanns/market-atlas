"""Hand-worked regressions and Python/browser parity for the financial arithmetic.

No network, current quotes, fitted returns, or model probabilities are used here.
"""
import json
from pathlib import Path
import shutil
import subprocess
import unittest

import decision_math as dm


BASE = dict(priceUsd=100., revenueBillionsUsd=100., dilutedSharesBillions=2.,
            years=5, revenueGrowth=.10, netMargin=.20, dilution=.02,
            exitPe=15., requiredReturn=.12)
DCF = dict(cashFlowType="FCFE", currency="USD", listingBasis="quoted-share",
           fcfePerShareForecastUsd=[10., 11.], costOfEquity=.10, terminalGrowth=.02)


class ValuationArithmeticTest(unittest.TestCase):
    def test_billions_cancel_to_usd_per_share(self):
        result = dm.scenario(dict(BASE, years=1, revenueGrowth=0, dilution=0))
        self.assertTrue(result["ok"])
        self.assertEqual(result["terminalEpsUsd"], 10.)  # $20bn / 2bn shares
        self.assertEqual(result["terminalPriceUsd"], 150.)
        self.assertEqual(result["cagrUsd"], .5)
        self.assertAlmostEqual(result["maxPriceUsd"], 150 / 1.12)

    def test_dilution_compounds_and_reduces_target_entry(self):
        result = dm.scenario(BASE)
        terminal_eps = (100 * 1.1**5 * .2) / (2 * 1.02**5)
        self.assertAlmostEqual(result["terminalEpsUsd"], terminal_eps)
        self.assertAlmostEqual(result["terminalSharesBillions"], 2 * 1.02**5)
        self.assertAlmostEqual(result["maxPriceUsd"], terminal_eps * 15 / 1.12**5)
        no_dilution = dm.scenario(dict(BASE, dilution=0))
        self.assertLess(result["maxPriceUsd"], no_dilution["maxPriceUsd"])
        self.assertEqual(len(result["path"]), 5)
        self.assertEqual(result["path"][-1]["year"], 5)

    def test_buybacks_increase_per_share_earnings(self):
        result = dm.scenario(dict(BASE, years=1, revenueGrowth=0, dilution=-.10))
        self.assertAlmostEqual(result["terminalEpsUsd"], 20 / 1.8)

    def test_zero_and_negative_earnings_do_not_become_zero_target_price(self):
        for margin, expected_eps in [(0, 0), (-.2, -10)]:
            with self.subTest(margin=margin):
                result = dm.scenario(dict(BASE, years=1, revenueGrowth=0, dilution=0, netMargin=margin))
                self.assertEqual(result["status"], "loss-making")
                self.assertEqual(result["terminalEpsUsd"], expected_eps)
                self.assertIsNone(result["terminalPriceUsd"])
                self.assertIsNone(result["maxPriceUsd"])
                self.assertIsNone(result["cagrUsd"])

    def test_missing_inputs_stay_unknown(self):
        result = dm.scenario(dict(BASE, dilutedSharesBillions=None))
        self.assertEqual(result["status"], "missing")
        self.assertIsNone(result["terminalEpsUsd"])
        self.assertEqual(result["path"], [])

    def test_invalid_horizon_price_pe_dilution_currency(self):
        for changes in [{"years": 0}, {"years": -5}, {"years": 1.5}, {"priceUsd": 0},
                        {"exitPe": -10}, {"exitPe": 0}, {"dilution": -1},
                        {"currency": "TWD"}, {"listingBasis": "ordinary-share"},
                        {"requiredReturn": -1}, {"netMargin": True}]:
            with self.subTest(changes=changes):
                self.assertEqual(dm.scenario(dict(BASE, **changes))["status"], "invalid")

    def test_adr_ratio_is_not_currency_conversion(self):
        # Illustrative arithmetic: 5 ordinary shares represented by one quoted ADR.
        ordinary = dm.scenario(dict(BASE, years=1, revenueGrowth=0, dilution=0,
                                    revenueBillionsUsd=40, dilutedSharesBillions=25,
                                    netMargin=.35))
        adr = dm.scenario(dict(BASE, years=1, revenueGrowth=0, dilution=0,
                               revenueBillionsUsd=40, dilutedSharesBillions=25 / 5,
                               netMargin=.35, listingBasis="quoted-share"))
        self.assertAlmostEqual(ordinary["terminalEpsUsd"], .56)
        self.assertAlmostEqual(adr["terminalEpsUsd"], 2.8)
        self.assertAlmostEqual(adr["terminalEpsUsd"], 5 * ordinary["terminalEpsUsd"])

    def test_eps_alternative_matches_revenue_model_same_margin(self):
        direct = dm.scenario_eps(dict(priceUsd=100, baseEpsUsd=10, earningsGrowth=.10,
                                     dilution=.02, years=5, exitPe=15, requiredReturn=.12))
        result = dm.scenario(BASE)
        self.assertAlmostEqual(direct["terminalEpsUsd"], result["terminalEpsUsd"])
        self.assertAlmostEqual(direct["maxPriceUsd"], result["maxPriceUsd"])
        self.assertIsNone(direct["terminalRevenueBillionsUsd"])

    def test_dividend_timing_and_price_return_are_distinct(self):
        result = dm.scenario(dict(BASE, years=2, revenueGrowth=0, dilution=0,
                                  exitPe=10, requiredReturn=.10, dividendsPerShareUsd=[10, 10]))
        self.assertAlmostEqual(result["terminalPriceUsd"], 100)
        self.assertAlmostEqual(result["cagrUsd"], 0)
        self.assertAlmostEqual(result["totalReturnUsd"], .2)
        self.assertAlmostEqual(result["irrUsd"], .10)
        self.assertAlmostEqual(result["maxPriceUsd"], 10 / 1.1 + 110 / 1.1**2)
        self.assertAlmostEqual(result["maxPriceUsd"], 100)

    def test_annual_fx_compounds_for_horizon(self):
        result = dm.scenario(dict(BASE, years=2, revenueGrowth=0, dilution=0, exitPe=10, annualFxChange=.10))
        self.assertAlmostEqual(result["cagrIdr"], .10)
        self.assertAlmostEqual(result["totalReturnIdr"], .21)
        self.assertIsNone(dm.scenario(BASE)["cagrIdr"])

    def test_dcf_terminal_cash_is_next_year_and_discounted_at_terminal_year(self):
        result = dm.equity_dcf(DCF)
        self.assertTrue(result["ok"])
        terminal = (11 * 1.02) / (.10 - .02)
        self.assertAlmostEqual(result["terminalValueUsd"], terminal)
        self.assertAlmostEqual(result["pvTerminalUsd"], terminal / 1.1**2)
        self.assertAlmostEqual(result["pvForecastUsd"], 10 / 1.1 + 11 / 1.1**2)
        self.assertAlmostEqual(result["valuePerShareUsd"], 10 / 1.1 + (11 + terminal) / 1.1**2)
        self.assertGreater(result["terminalValueShare"], .8)

    def test_dcf_cfo_capex_wrong_currency_and_unbounded_terminal_rejected(self):
        for changes in [{"cashFlowType": "CFO-capex"}, {"currency": "TWD"},
                        {"listingBasis": "ordinary-share"}, {"terminalGrowth": .10},
                        {"terminalGrowth": .11}, {"fcfePerShareForecastUsd": []}]:
            with self.subTest(changes=changes):
                result = dm.equity_dcf(dict(DCF, **changes))
                self.assertFalse(result["ok"])
                self.assertIsNone(result["valuePerShareUsd"])

    def test_dcf_can_model_early_negative_cash_flow_but_not_negative_perpetuity(self):
        recovery = dm.equity_dcf(dict(DCF, fcfePerShareForecastUsd=[-5, 11]))
        self.assertTrue(recovery["ok"])
        self.assertAlmostEqual(recovery["pvForecastUsd"], -5 / 1.1 + 11 / 1.1**2)
        loss = dm.equity_dcf(dict(DCF, fcfePerShareForecastUsd=[10, -1]))
        self.assertEqual(loss["status"], "loss-making")
        self.assertIsNone(loss["valuePerShareUsd"])


class IdrCostArithmeticTest(unittest.TestCase):
    def test_fx_up_and_down_are_multiplicative(self):
        self.assertAlmostEqual(dm.compound_idr(dict(usdReturn=-.50, fxReturn=.20))["returnIdr"], -.4)
        self.assertAlmostEqual(dm.compound_idr(dict(usdReturn=-.50, fxReturn=-.20))["returnIdr"], -.6)
        self.assertAlmostEqual(dm.compound_idr(dict(usdReturn=.20, fxReturn=-.20))["returnIdr"], -.04)

    def test_portfolio_weighted_loss_and_cash_currency(self):
        positions = [dict(symbol="A", weight=.6, assetReturn=-.5), dict(symbol="B", weight=.4, assetReturn=-.2)]
        result = dm.portfolio_stress(dict(positions=positions, fxReturn=.2))
        self.assertAlmostEqual(result["returnUsd"], -.38)
        self.assertAlmostEqual(result["returnIdr"], -.256)
        self.assertAlmostEqual(sum(row["contributionIdr"] for row in result["rows"]), -.256)
        assets = [dict(symbol="A", weight=.5, assetReturn=-.5)]
        idr_cash = dm.portfolio_stress(dict(positions=assets, fxReturn=.2, cashWeight=.5, cashCurrency="IDR"))
        usd_cash = dm.portfolio_stress(dict(positions=assets, fxReturn=.2, cashWeight=.5, cashCurrency="USD"))
        self.assertAlmostEqual(idr_cash["returnIdr"], -.2)
        self.assertAlmostEqual(usd_cash["returnIdr"], -.1)

    def test_unallocated_and_negative_weights_are_rejected(self):
        for positions in [[dict(weight=.7, assetReturn=-.5)],
                          [dict(weight=-.1, assetReturn=0), dict(weight=1.1, assetReturn=0)]]:
            self.assertFalse(dm.portfolio_stress(dict(positions=positions, fxReturn=0))["ok"])

    def test_overflow_is_unavailable_rather_than_infinite_wealth(self):
        stress = dm.portfolio_stress(dict(positions=[dict(weight=1, assetReturn=1e300)], fxReturn=1e300))
        self.assertEqual(stress["status"], "invalid")
        self.assertIsNone(stress["returnIdr"])
        budget = dm.monthly_budget(dict(budgetIdr=1e300, usdIdr=1e-300, fxSpread=0, brokerFeeRate=0))
        self.assertEqual(budget["status"], "invalid")
        self.assertIsNone(budget["investableUsd"])

    def test_budget_costs_reconcile_without_double_charging(self):
        inputs = dict(budgetIdr=16_320_000., usdIdr=16_000., fxSpread=.02, brokerFeeRate=.01, brokerFeeUsd=10.)
        result = dm.monthly_budget(inputs)
        self.assertAlmostEqual(result["convertedUsd"], 1000.)
        self.assertAlmostEqual(result["investableUsd"], 990 / 1.01)
        self.assertAlmostEqual(result["fxCostIdr"], 320_000.)
        self.assertAlmostEqual(result["fxCostIdr"] + result["brokerCostIdr"], result["totalCostIdr"])
        self.assertAlmostEqual(result["investableUsd"] * 16_000 + result["totalCostIdr"], 16_320_000.)

    def test_zero_cost_budget_and_fee_cannot_exceed_budget(self):
        result = dm.monthly_budget(dict(budgetIdr=16_000_000, usdIdr=16_000, fxSpread=0, brokerFeeRate=0))
        self.assertEqual(result["investableUsd"], 1000)
        self.assertEqual(result["totalCostIdr"], 0)
        zero = dm.monthly_budget(dict(budgetIdr=0, usdIdr=16_000, fxSpread=0, brokerFeeRate=0))
        self.assertEqual(zero["investableUsd"], 0)
        impossible = dm.monthly_budget(dict(budgetIdr=16_000, usdIdr=16_000, fxSpread=0, brokerFeeRate=0, brokerFeeUsd=2))
        self.assertEqual(impossible["status"], "infeasible")
        self.assertIsNone(impossible["investableUsd"])


class BrowserParityTest(unittest.TestCase):
    def test_browser_uses_same_units_and_results(self):
        node = shutil.which("node")
        self.assertIsNotNone(node, "Node is needed to verify the actual browser math, not just its Python reproduction.")
        cases = [("scenario", dm.scenario, BASE),
                 ("scenario", dm.scenario, dict(BASE, annualFxChange=-.03, dividendsPerShareUsd=[1, 2, 3, 4, 5])),
                 ("scenario", dm.scenario, dict(BASE, netMargin=-.1)),
                 ("scenario", dm.scenario, dict(BASE, dilutedSharesBillions=None)),
                 ("scenarioEps", dm.scenario_eps, dict(priceUsd=100, baseEpsUsd=5, years=10,
                                                     earningsGrowth=.1, dilution=.03, exitPe=20, requiredReturn=.12)),
                 ("equityDcf", dm.equity_dcf, DCF),
                 ("equityDcf", dm.equity_dcf, dict(DCF, fcfePerShareForecastUsd=[-5, 10])),
                 ("combinedReturn", dm.combined_return, dict(assetReturn=-.5, fxReturn=.2)),
                 ("compoundIdr", dm.compound_idr, dict(usdReturn=.2, fxReturn=-.2)),
                 ("portfolioStress", dm.portfolio_stress, dict(positions=[dict(weight=.8, assetReturn=-.4)], fxReturn=-.1,
                                                               cashWeight=.2, cashCurrency="IDR")),
                 ("monthlyBudget", dm.monthly_budget, dict(budgetIdr=16_320_000, usdIdr=16_000, fxSpread=.02,
                                                           brokerFeeRate=.01, brokerFeeUsd=10))]
        js_path = Path(__file__).with_name("decision-math.js")
        script = "const fs=require('fs');const m=require(process.argv[1]);const c=JSON.parse(fs.readFileSync(0,'utf8'));process.stdout.write(JSON.stringify(c.map(x=>m[x.name](x.input))));"
        process = subprocess.run([node, "-e", script, str(js_path)],
                                 input=json.dumps([dict(name=name, input=value) for name, _, value in cases]),
                                 capture_output=True, text=True, timeout=20, check=True)
        actual = json.loads(process.stdout)

        def compare(expected, observed):
            if isinstance(expected, dict):
                self.assertEqual(set(expected), set(observed))
                for key in expected:
                    compare(expected[key], observed[key])
            elif isinstance(expected, list):
                self.assertEqual(len(expected), len(observed))
                for left, right in zip(expected, observed):
                    compare(left, right)
            elif isinstance(expected, (int, float)) and not isinstance(expected, bool):
                self.assertAlmostEqual(expected, observed, delta=max(1e-10, abs(expected) * 1e-10))
            else:
                self.assertEqual(expected, observed)

        for (_, function, value), observed in zip(cases, actual):
            compare(function(value), observed)


if __name__ == "__main__":
    unittest.main()
