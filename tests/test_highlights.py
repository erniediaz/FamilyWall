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
from highlights import Highlights, daily_sample, final_scores, history, item, observances, quotes
from server import atomic_json

NOW = datetime(2026, 9, 18, 12, tzinfo=ZoneInfo('America/Denver'))


def game(name='Florida Gators', rank=99, status='STATUS_FINAL', completed=True, stamp='2026-09-18T01:00Z'):
    return {'events': [{'id': '123', 'date': stamp, 'status': {'type': {'name': status, 'completed': completed, 'state': 'post' if completed else 'in', 'shortDetail': 'Final'}},
        'competitions': [{'id': '123', 'competitors': [
            {'team': {'displayName': name, 'shortDisplayName': name}, 'homeAway': 'home', 'score': '24', 'curatedRank': {'current': rank}},
            {'team': {'displayName': 'Opponent', 'shortDisplayName': 'Opponent'}, 'homeAway': 'away', 'score': '21'}]}]}]}


class Finals(unittest.TestCase):
    def test_excludes_live_scheduled_cancelled_and_postponed(self):
        for name, completed in [('STATUS_IN_PROGRESS', False), ('STATUS_SCHEDULED', False), ('STATUS_CANCELED', True), ('STATUS_POSTPONED', True)]:
            self.assertEqual(final_scores(game(status=name, completed=completed), 'cfb', NOW), [])
    def test_ranked_or_florida_only_for_every_college_sport(self):
        for league in ('cfb', 'cbb', 'wbb', 'baseball'):
            self.assertEqual(len(final_scores(game(), league, NOW)), 1)
            self.assertEqual(final_scores(game(name='Other', rank=99), league, NOW), [])
            self.assertEqual(len(final_scores(game(name='Other', rank=25), league, NOW)), 1)
            self.assertEqual(final_scores(game(name='Other', rank=26), league, NOW), [])
    def test_all_nfl_mlb_and_favorite_nba_nhl(self):
        for league in ('nfl', 'mlb'): self.assertEqual(len(final_scores(game(name='Other'), league, NOW)), 1)
        for league, favorite in [('nba', 'Denver Nuggets'), ('nhl', 'Colorado Avalanche')]:
            self.assertEqual(final_scores(game(name='Other'), league, NOW), [])
            self.assertEqual(len(final_scores(game(name=favorite), league, NOW)), 1)
    def test_invalid_scores_dates_duplicates_and_rank_display(self):
        for stamp in ['2026-09-10T01:00Z', '2026-09-19T23:00Z', 'bad-date']:
            self.assertEqual(final_scores(game(stamp=stamp), 'cfb', NOW), [])
        data = game(rank=3)
        data['events'] *= 2
        rows = final_scores(data, 'cfb', NOW)
        self.assertEqual(len(rows), 1)
        self.assertIn('#3 Florida Gators 24', rows[0]['text'])
        self.assertIn('Sep 17', rows[0]['detail'])
        data['events'][0]['competitions'][0]['competitors'][0]['score'] = ''
        self.assertEqual(final_scores(data, 'cfb', NOW), [])
    def test_competition_status_takes_precedence(self):
        data = game()
        data['events'][0]['competitions'][0]['status'] = {'type': {'completed': False}}
        self.assertEqual(final_scores(data, 'cfb', NOW), [])


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
            with patch('highlights.history', side_effect=RuntimeError()), patch('highlights.observances', return_value=[]), patch('highlights.fetch', return_value={'events': []}) as get:
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
    def test_failed_feed_keeps_recent_finals_but_ages_out(self):
        with tempfile.TemporaryDirectory() as directory:
            feed = Highlights(Path(directory) / 'highlights.json', atomic_json)
            rows = final_scores(game(), 'cfb', NOW)
            feed.state['scores'] = {'cfb:2026-09-17': {'items': rows, 'updated': NOW.timestamp(), 'ok': False}}
            self.assertTrue(feed.snapshot(NOW)['items'][0]['cached'])
            self.assertIn('sports', feed.snapshot(NOW)['unavailable'])
            self.assertEqual(feed.snapshot(NOW + timedelta(days=8))['items'], [])
    def test_failure_of_one_category_does_not_hide_others(self):
        with tempfile.TemporaryDirectory() as directory:
            feed = Highlights(Path(directory) / 'highlights.json', atomic_json)
            with patch('highlights.history', return_value=[item('history', 'Fact', '1900', 'Wikipedia', 'https://en.wikipedia.org/')]), patch('highlights.observances', side_effect=RuntimeError()), patch('highlights.fetch', side_effect=RuntimeError()):
                result = feed.refresh(NOW)
            self.assertEqual({row['category'] for row in result['items']}, {'history', 'quotes'})
            self.assertIn('observances', result['unavailable'])


if __name__ == '__main__': unittest.main()
