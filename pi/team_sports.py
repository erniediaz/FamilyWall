"""Season-aware cards for the seven requested teams; no live-score display."""
from datetime import datetime, timedelta

TEAMS = {
    'gators-football': ('football/college-football', '57', 'Florida Gators Football'),
    'gators-basketball': ('basketball/mens-college-basketball', '57', 'Florida Gators Men’s Basketball'),
    # ESPN college baseball uses a different identity from football/basketball.
    'gators-baseball': ('baseball/college-baseball', '75', 'Florida Gators Baseball'),
    'rockies': ('baseball/mlb', '27', 'Colorado Rockies'),
    'broncos': ('football/nfl', '7', 'Denver Broncos'),
    'nuggets': ('basketball/nba', '7', 'Denver Nuggets'),
    'avalanche': ('hockey/nhl', '17', 'Colorado Avalanche'),
}
API = 'https://site.api.espn.com/apis/site/v2/sports/'
SEASON_GRACE_DAYS = 7


def stamp(value):
    try:
        result = datetime.fromisoformat(value.replace('Z', '+00:00'))
        return result if result.tzinfo else None
    except (AttributeError, TypeError, ValueError):
        return None


def normalize_games(events, team_id, year):
    games = {}
    for event in events:
        if event.get('season', {}).get('year') != year:
            continue
        season_type = str(event.get('seasonType', {}).get('type', event.get('seasonType', {}).get('id', '')))
        if season_type not in ('2', '3'):  # Exclude exhibitions/preseason.
            continue
        for game in event.get('competitions', []):
            date = stamp(game.get('date', event.get('date')))
            if not date: continue
            sides = game.get('competitors', [])
            own = next((c for c in sides if str(c.get('team', {}).get('id')) == team_id), None)
            opponent = next((c for c in sides if str(c.get('team', {}).get('id')) != team_id), None)
            if not own or not opponent or len(sides) != 2: continue
            status = game.get('status', event.get('status', {})).get('type', {})
            status_name = status.get('name', '')
            if status_name in ('STATUS_CANCELED', 'STATUS_CANCELLED', 'STATUS_POSTPONED'): continue
            final = status.get('completed') is True and status.get('state') == 'post' and status_name.startswith('STATUS_FINAL')
            score = []
            for side in (own, opponent):
                value = side.get('score')
                value = value.get('displayValue', value.get('value')) if isinstance(value, dict) else value
                try:
                    number = float(value)
                    score.append(int(number) if number.is_integer() and number >= 0 else None)
                except (TypeError, ValueError, OverflowError): score.append(None)
            final = final and all(value is not None for value in score)
            curated = own.get('curatedRank') or {}
            row = dict(id=str(game.get('id', event.get('id'))), date=date.isoformat(), final=final,
                       scheduled=status.get('state') == 'pre', live=status.get('state') == 'in',
                       time_valid=game.get('timeValid', event.get('timeValid', True)),
                       date_valid=game.get('dateValid', event.get('dateValid', True)) and not game.get('status', {}).get('isTBDFlex', False),
                       opponent=opponent['team'].get('abbreviation') or opponent['team'].get('shortDisplayName', 'TBD'),
                       opponent_name=opponent['team'].get('displayName', 'Opponent TBD'),
                       venue='vs' if game.get('neutralSite') or own.get('homeAway') == 'home' else 'at',
                       score=score if final else None, rank=curated.get('current'), postseason=season_type == '3',
                       final_label=status.get('shortDetail', 'Final'))
            games[row['id']] = row
    return sorted(games.values(), key=lambda game: game['date'])


def in_season(games, now):
    dates = [stamp(game['date']).astimezone(now.tzinfo).date() for game in games]
    # Schedules drive season boundaries, including playoff dates and bye weeks.
    # Keep the final result for one week while postseason pairings may be pending.
    return bool(dates and min(dates) <= now.date() <= max(dates) + timedelta(days=SEASON_GRACE_DAYS))


def poll_label(payload, team_id, year, now):
    if payload.get('latestSeason', {}).get('year') != year: return None
    poll = next((p for p in payload.get('rankings', []) if p.get('type') == 'ap'), None)
    if not poll or not poll.get('ranks'): return None
    published = stamp(poll.get('date'))
    if not published or not 0 <= (now - published).total_seconds() <= 45 * 86400: return None
    rank = next((r.get('current') for r in poll['ranks'] if str(r.get('team', {}).get('id')) == team_id), None)
    return f'AP #{rank}' if type(rank) is int and 1 <= rank <= 25 else 'Unranked (AP)'


def fetch_team(key, now, fetch):
    league, team_id, name = TEAMS[key]
    base = API + league + '/teams/' + team_id
    team = fetch(base)['team']
    expected_name = 'Florida Gators' if key.startswith('gators-') else name
    if team.get('displayName') != expected_name or str(team.get('id')) != team_id:
        raise ValueError('Team identity mismatch')
    regular = fetch(base + '/schedule', {'seasontype': 2})
    year = regular['season']['year']
    postseason = fetch(base + '/schedule', {'season': year, 'seasontype': 3})
    for schedule in (regular, postseason):
        if str(schedule.get('team', {}).get('id')) != team_id or not isinstance(schedule.get('events'), list):
            raise ValueError('Schedule identity mismatch')
    games = normalize_games(regular['events'] + postseason['events'] + team.get('nextEvent', []), team_id, year)
    record = next((r.get('summary') for r in team.get('record', {}).get('items', []) if r.get('type') == 'total'), None)
    standing = team.get('standingSummary') or regular.get('team', {}).get('standingSummary')
    ranking = None
    if in_season(games, now) and key in ('gators-football', 'gators-basketball'):
        try: ranking = poll_label(fetch(API + league + '/rankings'), team_id, year, now)
        except Exception: pass  # Record and schedule can still be shown.
    if key == 'gators-baseball':
        # This feed sometimes returns retired SEC East/West division standings.
        # Prefer its recent game ranking over presenting those obsolete divisions.
        if standing and ('East' in standing or 'West' in standing): standing = None
        recent = [g for g in games if abs((stamp(g['date']) - now).total_seconds()) <= 7 * 86400 and type(g.get('rank')) is int]
        recent.sort(key=lambda g: abs((stamp(g['date']) - now).total_seconds()))
        if recent and 1 <= recent[0]['rank'] <= 25: ranking = f'ESPN rank #{recent[0]["rank"]}'
    if standing: standing = standing.replace(' in ', ' ').replace(' Division', '')
    return dict(name=name, record=record or regular.get('team', {}).get('recordSummary') or 'Not available',
                standing=' · '.join(x for x in (ranking, standing) if x) or 'Standing unavailable',
                games=games, year=year, url=f'https://www.espn.com/{league.split("/")[-1]}/team/_/id/{team_id}')


def card(key, data, now, cached=False):
    games = data['games']
    if not in_season(games, now): return None
    completed = [g for g in games if g['final'] and stamp(g['date']) <= now]
    upcoming = [g for g in games if g['scheduled'] and stamp(g['date']) > now]
    last = max(completed, key=lambda g: g['date']) if completed else None
    next_game = min(upcoming, key=lambda g: g['date']) if upcoming else None
    last_text = 'No completed game this season'
    last_title = last_text
    if last:
        own, other = last['score']
        outcome = 'W' if own > other else 'L' if own < other else 'T'
        played = stamp(last['date']).astimezone(now.tzinfo)
        last_text = f'{outcome} {own}–{other} {last["venue"]} {last["opponent"]} · {played.strftime("%b")} {played.day}'
        last_title = f'{last["opponent_name"]} · {last["final_label"]}'
    next_text = 'Not yet scheduled'
    next_title = next_text
    if next_game:
        starts = stamp(next_game['date']).astimezone(now.tzinfo)
        day = f'{starts.strftime("%b")} {starts.day}' if next_game['date_valid'] else 'Date TBD'
        clock = starts.strftime('%I:%M %p').lstrip('0') + ' MT' if next_game['time_valid'] and next_game['date_valid'] else 'Time TBD'
        next_text = f'{next_game["venue"]} {next_game["opponent"]} · {day}, {clock}'
        next_title = next_game['opponent_name']
    return dict(id='team-' + key, category='sports', text=data['name'], detail='Season snapshot', source='ESPN', url=data['url'], cached=cached,
                team=dict(name=data['name'], record=data['record'], standing=data['standing'], last=last_text, next=next_text,
                          last_title=last_title, next_title=next_title))
