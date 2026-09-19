import copy
import json
import sys
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'pi'))
from highlights import Highlights, daily_sample, history, item, observances, quotes
from server import atomic_json

NOW = datetime(2026, 9, 18, 12, tzinfo=ZoneInfo('America/Denver'))


class Daily(unittest.TestCase):
    def test_cap_deduplicate_and_stable_daily_selection(self):
        rows = [item('history', str(i), '', 'source', 'https://example.org') for i in range(30)]
        chosen = daily_sample(rows + rows, '2026-09-18', 'history')
        self.assertEqual(len(chosen), 10)
        self.assertEqual(chosen, daily_sample(rows, '2026-09-18', 'history'))
        self.assertNotEqual(chosen, daily_sample(rows, '2026-09-19', 'history'))
        self.assertEqual(len(quotes('2026-09-18')), 10)
    def test_history_uses_real_year_and_complete_short_text(self):
        with patch('highlights.fetch', return_value={'events': [{'text': 'A short historical event.', 'year': 1900}, {'text': 'X' * 300, 'year': 1901}, {'text': 'Not history yet.', 'year': 2027}]}):
            rows = history('2026-09-18')
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['detail'], '1900')
    def test_observance_wrong_date_is_rejected(self):
        with patch('highlights.fetch', return_value={'date': '09/17/2026', 'error': 'none', 'holidays': []}):
            with self.assertRaises(ValueError): observances('2026-09-18')
    def test_daily_failures_retry_without_stale_yesterday(self):
        with tempfile.TemporaryDirectory() as directory:
            feed = Highlights(Path(directory) / 'highlights.json', atomic_json)
            # Empty valid scoreboards exercise bounded cache behavior without network.
            with patch('highlights.history', side_effect=RuntimeError()), patch('highlights.observances', return_value=[]), patch('highlights.fetch_team', return_value={'name':'Test','record':'0-0','standing':'Unavailable','games':[],'url':'https://www.espn.com/'}) as get:
                today = feed.refresh(NOW)
                calls = get.call_count
                again = feed.refresh(NOW + timedelta(minutes=1))
                self.assertEqual(get.call_count, calls)
            self.assertIn('history', today['unavailable'])
            self.assertEqual(len(today['items']), 10)
            self.assertEqual(today, again)
            tomorrow = feed.snapshot(NOW + timedelta(days=1))
            self.assertFalse(any(row['category'] != 'sports' for row in tomorrow['items']))
            self.assertEqual((Path(directory) / 'highlights.json').stat().st_mode & 0o777, 0o600)
    def test_failed_team_feed_expires_and_legacy_scores_are_discarded(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'highlights.json'
            atomic_json(path, {'daily': {}, 'scores': {'old': {'items': [{'category': 'sports'}]}}})
            feed = Highlights(path, atomic_json)
            self.assertNotIn('scores', feed.state)
            feed.state['teams'] = {'broncos': {'data': {}, 'updated': NOW.timestamp() - 86401, 'ok': False}}
            self.assertEqual(feed.snapshot(NOW)['items'], [])
            self.assertIn('sports', feed.snapshot(NOW)['unavailable'])
    def test_failure_of_one_category_does_not_hide_others(self):
        with tempfile.TemporaryDirectory() as directory:
            feed = Highlights(Path(directory) / 'highlights.json', atomic_json)
            with patch('highlights.history', return_value=[item('history', 'Fact', '1900', 'Wikipedia', 'https://en.wikipedia.org/')]), patch('highlights.observances', side_effect=RuntimeError()), patch('highlights.fetch_team', side_effect=RuntimeError()):
                result = feed.refresh(NOW)
            self.assertEqual({row['category'] for row in result['items']}, {'history', 'quotes'})
            self.assertIn('observances', result['unavailable'])


if __name__ == '__main__': unittest.main()
