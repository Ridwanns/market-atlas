import copy
import datetime as dt
import json
import math
import tempfile
import unittest
from pathlib import Path
from forecast_monitor import eligibility, completed_bars, settle, update_monitor


def stamp(day, hour=13, minute=30):
    return dt.datetime.fromisoformat(day + f'T{hour:02d}:{minute:02d}:00+00:00').timestamp()


def observation(days, prices, current='2026-10-01'):
    return {'source': 'test-source', 'sha256': 'test-hash', 'raw_file': 'test.json', 'captured_utc': 'test',
            'chart': {'meta': {'gmtoffset': -14400, 'currentTradingPeriod': {'regular': {
                'start': stamp(current), 'end': stamp(current, 20, 0)}}},
                'timestamp': [stamp(day) for day in days],
                'indicators': {'adjclose': [{'adjclose': prices}]}}}


class ProspectiveTests(unittest.TestCase):
    def test_registration_uses_first_session_not_target_close(self):
        obs = observation(['2026-09-30', '2026-10-01'], [100, 101])
        self.assertEqual(eligibility('2026-09-30', obs, stamp('2026-10-01', 12, 0))[0], 'eligible')
        self.assertEqual(eligibility('2026-09-30', obs, stamp('2026-10-01', 14, 0))[0], 'late')
        self.assertEqual(eligibility('2026-09-30', obs, stamp('2026-10-01'))[0], 'late')

    def test_unknown_is_not_assumed_eligible(self):
        obs = observation(['2026-09-30'], [100], current='2026-09-30')
        self.assertEqual(eligibility('2026-09-30', obs, stamp('2026-10-01', 12, 0))[0], 'unknown')

    def test_today_intraday_bar_is_excluded(self):
        obs = observation(['2026-09-30', '2026-10-01'], [100, 110])
        self.assertEqual(len(completed_bars(obs, stamp('2026-10-01', 19, 0))), 1)
        self.assertEqual(len(completed_bars(obs, stamp('2026-10-01', 20, 0))), 2)

    def test_horizon_counts_sessions_and_late_never_scores(self):
        obs = observation(['2026-09-30', '2026-10-01', '2026-10-02', '2026-10-05'], [100, 101, 102, 120], current='2026-10-05')
        row = {'eligibility': 'eligible', 'status': 'pending', 'origin': '2026-09-30', 'horizon': 3}
        settle(row, obs, stamp('2026-10-05', 20, 0))
        self.assertEqual(row['target_date'], '2026-10-05')
        self.assertAlmostEqual(row['actual_log_return'], math.log(1.2))
        late = {'eligibility': 'late', 'status': 'excluded', 'origin': '2026-09-30', 'horizon': 3}
        settle(late, obs, stamp('2026-10-05', 20, 0))
        self.assertEqual(late['status'], 'excluded')

    def test_predictions_frozen_and_failures_excluded(self):
        report = {'assets': {'test': {'meta': {'symbol': 'TEST'}, 'data': {'source_sha256': 'input'},
            'forecasts': [{'horizon': 1, 'current': {'origin': '2026-09-30', 'last_training_target': '2026-09-30',
                'predictions': {'mean': .01, 'zero': 0}, 'intervals90': {'mean': [-.1, .1], 'zero': [-.1, .1]}}}]}}}
        with tempfile.TemporaryDirectory() as folder:
            path, ledger = Path(folder) / 'q.json', Path(folder) / 'ledger.json'
            path.write_text(json.dumps(report))
            first = observation(['2026-09-30'], [100])
            before = stamp('2026-10-01', 12, 0)
            result = update_monitor(path, ledger, lambda _: copy.deepcopy(first), before)
            frozen = [{key: row[key] for key in ['key', 'prediction', 'registered_utc', 'eligibility']} for row in result['records']]
            last = observation(['2026-09-30', '2026-10-01'], [100, 110])
            result = update_monitor(path, ledger, lambda _: copy.deepcopy(last), stamp('2026-10-01', 20, 0), force=True)
            self.assertEqual(frozen, [{key: row[key] for key in frozen[0]} for row in result['records']])
            self.assertEqual(result['summary']['scored'], 2)
            self.assertEqual(len(result['records']), 2)
            self.assertEqual(result['summary']['metrics'][0]['matched_observations'], 1)


if __name__ == '__main__':
    unittest.main()
