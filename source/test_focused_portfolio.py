"""Independent source/alignment checks for the requested four-asset risk study."""
import csv
import hashlib
import json
import math
import unittest
from pathlib import Path
import numpy as np

ROOT=Path(__file__).resolve().parent

class FocusStudyTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.q=json.loads((ROOT/'results/2026-10-09/focused-portfolio.json').read_text())

    def test_target_universe_and_original_vintage(self):
        q=self.q
        self.assertEqual(list(q['assets']),['nvda','tsm','mu','spy','sp500','nasdaq','ihsg'])
        self.assertEqual(q['portfolios']['styles']['focus']['weights'],{'nvda':.4,'tsm':.25,'mu':.2,'spy':.15})
        original=(ROOT/'results/2026-09-30/quant-refresh.json').read_bytes()
        self.assertEqual(hashlib.sha256(original).hexdigest(),q['focus']['original_report_sha256'])

    def test_covariance_uses_actual_spy_prices_and_aligned_dates(self):
        ids=['nvda','tsm','mu','spy'];series={}
        for ident in ids:
            file=ROOT/'data/2026-09-30/quant-refresh'/f'{ident}.csv'
            with file.open(newline='') as stream:rows=list(csv.DictReader(stream))
            series[ident]={r['date']:float(r['adjusted_close']) for r in rows}
        dates=sorted(set.intersection(*(set(s) for s in series.values())))[-253:]
        prices=np.array([[series[i][d] for i in ids] for d in dates])
        returns=prices[1:]/prices[:-1]-1
        raw=np.cov(returns.T);cov=.9*raw+.1*np.diag(np.diag(raw));w=np.array([.4,.25,.2,.15])
        p=self.q['portfolios'];st=p['styles']['focus']
        self.assertEqual(p['first'],dates[1]);self.assertEqual(p['last'],dates[-1])
        self.assertAlmostEqual(st['annual_volatility'],math.sqrt(w@cov@w*252),12)
        self.assertAlmostEqual(sum(st['risk_contributions'].values()),1,12)
        self.assertEqual(list(st['risk_contributions']),ids)
        for ident,expected in zip(ids,w*(cov@w)/(w@cov@w)):
            self.assertAlmostEqual(st['risk_contributions'][ident],expected,12)

    def test_spy_is_fitted_from_its_own_adjusted_series(self):
        spy=self.q['assets']['spy'];frozen=self.q['focus']
        self.assertEqual(spy['meta']['symbol'],'SPY')
        self.assertEqual(spy['data']['source_sha256'],frozen['spy_source_sha256'])
        self.assertEqual(spy['data']['price_field'],'adjusted_close')
        for f in spy['forecasts']:
            self.assertGreater(f['observations'],50)
            for row in f['records']:
                self.assertLessEqual(row['last_training_target'],row['origin'])
                self.assertLess(row['origin'],row['target'])
                self.assertLessEqual(row['target'],'2026-09-30')
        for m in spy['visual_scenarios']['models'].values():
            self.assertTrue(all(sum(h['counts'])==5000 for h in m['histograms'].values()))

if __name__=='__main__':unittest.main()
