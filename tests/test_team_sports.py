import sys
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock
from zoneinfo import ZoneInfo
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'pi'))
from team_sports import TEAMS, normalize_games, in_season, card, poll_label, fetch_team

NOW = datetime(2026, 9, 18, 12, tzinfo=ZoneInfo('America/Denver'))


def event(identity, date, status='STATUS_FINAL', season_type=2, year=2026, time_valid=True):
    final = status.startswith('STATUS_FINAL')
    state = 'post' if final else 'pre' if status == 'STATUS_SCHEDULED' else 'in'
    return {'id': identity, 'date': date, 'season': {'year': year}, 'seasonType': {'type': season_type},
            'competitions': [{'id': identity, 'date': date, 'timeValid': time_valid,
              'status': {'type': {'name': status, 'completed': final, 'state': state, 'shortDetail': 'Final'}},
              'competitors': [
                {'homeAway': 'home', 'team': {'id': '7', 'displayName': 'Denver Broncos', 'abbreviation': 'DEN'}, 'score': {'displayValue': '10'}},
                {'homeAway': 'away', 'team': {'id': '99', 'displayName': 'Test Opponent', 'abbreviation': 'TST'}, 'score': {'displayValue': '31'}}]}]}


def payload(events):
    return dict(name='Denver Broncos', record='0-1', standing='3rd AFC West', url='https://www.espn.com/', games=normalize_games(events, '7', 2026))


class TeamCards(unittest.TestCase):
    def test_exact_seven_teams_and_baseball_identity(self):
        self.assertEqual(len(TEAMS), 7)
        self.assertEqual(TEAMS['gators-baseball'][1], '75')
        self.assertEqual(TEAMS['gators-basketball'][0], 'basketball/mens-college-basketball')
        self.assertNotIn('wbb', TEAMS)

    def test_season_boundaries_bye_week_and_final_grace(self):
        data = payload([event('1', '2026-09-01T20:00Z'), event('2', '2026-10-01T20:00Z', 'STATUS_SCHEDULED')])
        self.assertTrue(in_season(data['games'], NOW))
        self.assertFalse(in_season(data['games'], datetime(2026, 8, 31, tzinfo=NOW.tzinfo)))
        self.assertTrue(in_season(data['games'], datetime(2026, 10, 8, tzinfo=NOW.tzinfo)))
        self.assertFalse(in_season(data['games'], datetime(2026, 10, 9, tzinfo=NOW.tzinfo)))

    def test_preseason_and_old_season_never_activate_team(self):
        events = [event('pre', '2026-09-10T20:00Z', season_type=1), event('old', '2025-09-10T20:00Z', year=2025), event('future', '2026-11-01T20:00Z', 'STATUS_SCHEDULED')]
        data = payload(events)
        self.assertEqual(len(data['games']), 1)
        self.assertIsNone(card('broncos', data, NOW))

    def test_last_final_next_future_record_and_standing(self):
        data = payload([event('old', '2026-09-01T20:00Z'), event('last', '2026-09-17T20:00Z'), event('next', '2026-09-20T20:05Z', 'STATUS_SCHEDULED')])
        row = card('broncos', data, NOW)
        self.assertEqual(row['team']['record'], '0-1')
        self.assertEqual(row['team']['standing'], '3rd AFC West')
        self.assertEqual(row['team']['last'], 'L 10–31 vs TST · Sep 17')
        self.assertEqual(row['team']['next'], 'vs TST · Sep 20, 2:05 PM MT')

    def test_live_postponed_cancelled_not_last_or_next(self):
        events = [event('last', '2026-09-17T20:00Z'), event('live', '2026-09-18T17:00Z', 'STATUS_IN_PROGRESS'),
                  event('postponed', '2026-09-19T20:00Z', 'STATUS_POSTPONED'), event('cancelled', '2026-09-20T20:00Z', 'STATUS_CANCELED'),
                  event('next', '2026-09-21T20:00Z', 'STATUS_SCHEDULED')]
        data = payload(events)
        self.assertEqual(len(data['games']), 3)
        self.assertIsNone(next(g for g in data['games'] if g['live'])['score'])
        self.assertIn('Sep 17', card('broncos', data, NOW)['team']['last'])
        self.assertIn('Sep 21', card('broncos', data, NOW)['team']['next'])

    def test_postseason_extends_season_and_games_deduplicate(self):
        regular = event('reg', '2026-09-01T20:00Z')
        post = event('post', '2026-09-25T20:00Z', 'STATUS_SCHEDULED', season_type=3)
        data = payload([regular, regular, post])
        self.assertEqual(len(data['games']), 2)
        self.assertIsNotNone(card('broncos', data, NOW))

    def test_unknown_time_and_unannounced_schedule(self):
        data = payload([event('last', '2026-09-17T20:00Z'), event('next', '2026-09-20T20:00Z', 'STATUS_SCHEDULED', time_valid=False)])
        self.assertIn('Time TBD', card('broncos', data, NOW)['team']['next'])
        flex = event('next', '2026-09-20T05:00Z', 'STATUS_SCHEDULED', time_valid=False)
        flex['competitions'][0]['status']['isTBDFlex'] = True
        self.assertIn('Date TBD', card('broncos', payload([event('last', '2026-09-17T20:00Z'), flex]), NOW)['team']['next'])
        data = payload([event('last', '2026-09-17T20:00Z')])
        self.assertEqual(card('broncos', data, NOW)['team']['next'], 'Not yet scheduled')

    def test_invalid_score_is_not_a_final_result(self):
        broken = event('1', '2026-09-17T20:00Z')
        broken['competitions'][0]['competitors'][0]['score'] = {'displayValue': 'TBD'}
        self.assertFalse(payload([broken])['games'][0]['final'])

    def test_ap_poll_requires_current_year_and_recent_publication(self):
        data = {'latestSeason': {'year': 2026}, 'rankings': [{'type': 'ap', 'date': '2026-09-13T07:00Z', 'ranks': [{'current': 9, 'team': {'id': '57'}}]}]}
        self.assertEqual(poll_label(data, '57', 2026, NOW), 'AP #9')
        self.assertEqual(poll_label(data, '999', 2026, NOW), 'Unranked (AP)')
        self.assertIsNone(poll_label(data, '57', 2027, NOW))
        self.assertIsNone(poll_label(data, '57', 2026, NOW + timedelta(days=60)))

    def test_wrong_team_identity_rejected(self):
        fetch = Mock(return_value={'team': {'id': '75', 'displayName': 'Wrong Team'}})
        with self.assertRaises(ValueError): fetch_team('gators-baseball', NOW, fetch)


if __name__ == '__main__': unittest.main()
