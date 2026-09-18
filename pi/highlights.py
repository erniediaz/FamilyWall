"""Small, cached public feeds. Never sends calendar/configuration data to providers."""
import hashlib
import json
import random
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urlparse

import requests

HEADERS = {'User-Agent': 'FamilyWall/2.0 (personal dashboard; https://github.com/erniediaz/FamilyWall)'}
LEAGUES = {
    'nfl': ('football/nfl', 'NFL', None, None),
    'mlb': ('baseball/mlb', 'MLB', None, None),
    'nhl': ('hockey/nhl', 'NHL', None, {'Colorado Avalanche'}),
    'nba': ('basketball/nba', 'NBA', None, {'Denver Nuggets'}),
    'cfb': ('football/college-football', 'College football', '80', {'Florida Gators'}),
    'cbb': ('basketball/mens-college-basketball', 'Men’s college basketball', '50', {'Florida Gators'}),
    'wbb': ('basketball/womens-college-basketball', 'Women’s college basketball', '50', {'Florida Gators'}),
    'baseball': ('baseball/college-baseball', 'College baseball', None, {'Florida Gators'}),
}
FAVORITES = {'Colorado Rockies', 'Denver Broncos', 'Colorado Avalanche', 'Denver Nuggets', 'Florida Gators'}


def fetch(url, params=None):
    response = requests.get(url, params=params, headers=HEADERS, timeout=(5, 15))
    response.raise_for_status()
    return response.json()


def safe_url(url, domain):
    parsed = urlparse(url or '')
    return url if parsed.scheme == 'https' and (parsed.hostname == domain or (parsed.hostname or '').endswith('.' + domain)) else 'https://' + domain + '/'


def item(category, text, detail, source, url, **extra):
    identity = hashlib.sha256((category + text + detail).encode()).hexdigest()[:20]
    return dict(id=identity, category=category, text=text, detail=detail, source=source, url=url, **extra)


def daily_sample(items, day, category):
    unique = list({row['id']: row for row in items}.values())
    random.Random(day + category).shuffle(unique)
    return unique[:10]


def history(day):
    month_day = datetime.fromisoformat(day).strftime('%m/%d')
    data = fetch('https://en.wikipedia.org/api/rest_v1/feed/onthisday/events/' + month_day)
    rows = []
    for event in data['events']:
        text = ' '.join(event.get('text', '').split())
        # A complete short sentence fits the header without cutting off the fact.
        if not text or len(text) > 140 or not isinstance(event.get('year'), int):
            continue
        year = event['year']
        if year >= int(day[:4]):
            continue
        url = f'https://en.wikipedia.org/wiki/{datetime.fromisoformat(day).strftime("%B")}_{int(day[8:])}#Events'
        rows.append(item('history', text, str(year) if year > 0 else f'{1-year} BC', 'Wikipedia · CC BY-SA 4.0', url))
    return daily_sample(rows, day, 'history')


def observances(day):
    date_label = datetime.fromisoformat(day).strftime('%m/%d/%Y')
    data = fetch('https://www.checkiday.com/api/3/', {'d': date_label})
    if data.get('error') != 'none' or data.get('date') != date_label:
        raise ValueError('Observance feed date mismatch')
    rows = [item('observances', row['name'], 'Today’s observances', 'Checkiday', safe_url(row.get('url'), 'checkiday.com'))
            for row in data['holidays'] if isinstance(row.get('name'), str) and len(row['name']) <= 160]
    return daily_sample(rows, day, 'observances')


def quotes(day):
    data = json.loads(Path(__file__).with_name('quotes.json').read_text())
    return daily_sample([item('quotes', '“' + row['text'] + '”', row['author'], row['work'], row['url']) for row in data], day, 'quotes')


def final_scores(data, league, now):
    """Filter final results by age and league/favorite/rank; one row per competition."""
    _, label, _, selected = LEAGUES[league]
    college = league in ('cfb', 'cbb', 'wbb', 'baseball')
    rows = []
    for event in data.get('events', []):
        for game in event.get('competitions', []):
            status = game.get('status', event.get('status', {})).get('type', {})
            if status.get('completed') is not True or status.get('state') != 'post' or not status.get('name', '').startswith('STATUS_FINAL'):
                continue
            try:
                played = datetime.fromisoformat(game.get('date', event['date']).replace('Z', '+00:00')).astimezone(now.tzinfo)
            except (KeyError, TypeError, ValueError):
                continue
            if not now.date() - timedelta(days=7) <= played.date() <= now.date() or played > now:
                continue
            teams = sorted(game.get('competitors', []), key=lambda c: c.get('homeAway') != 'away')
            if len(teams) != 2 or any(not re.fullmatch(r'\d+', str(c.get('score', ''))) for c in teams):
                continue
            names = {c.get('team', {}).get('displayName', '') for c in teams}
            ranks = [c.get('curatedRank', {}).get('current', 99) if isinstance(c.get('curatedRank'), dict) else 99 for c in teams]
            ranked = any(type(rank) is int and 1 <= rank <= 25 for rank in ranks)
            if selected and not names.intersection(selected) and not (college and ranked):
                continue
            parts = []
            for c, rank in zip(teams, ranks):
                name = c.get('team', {}).get('shortDisplayName') or c.get('team', {}).get('displayName', 'Team')
                prefix = f'#{rank} ' if college and type(rank) is int and 1 <= rank <= 25 else ''
                parts.append(f'{prefix}{name} {c["score"]}')
            url = next((link.get('href') for link in event.get('links', []) if 'summary' in link.get('rel', [])), 'https://www.espn.com/')
            row = item('sports', ' · '.join(parts), f'{label} · {played.strftime("%b")} {played.day} · {status.get("shortDetail", "Final")}', 'ESPN', safe_url(url, 'espn.com'), played=played.isoformat(), favorite=bool(names.intersection(FAVORITES)))
            row['id'] = f'{league}-{game.get("id", event.get("id"))}'
            rows.append(row)
    return list({row['id']: row for row in rows}.values())


class Highlights:
    """Feed state is separate from the private calendar cache and safe to discard."""
    def __init__(self, path, save):
        self.path, self.save = Path(path), save
        try:
            self.state = json.loads(self.path.read_text())
        except (OSError, ValueError):
            self.state = {}
        self.state.setdefault('daily', {})
        self.state.setdefault('scores', {})

    def refresh(self, now, publish=None):
        day = now.date().isoformat()
        tick = now.timestamp()
        daily = self.state['daily']
        for category, loader in [('history', history), ('observances', observances), ('quotes', quotes)]:
            old = daily.get(category, {})
            if old.get('day') == day and old.get('ok'):
                continue
            if old.get('day') == day and tick - old.get('attempt', 0) < 1800:
                continue
            try:
                daily[category] = dict(day=day, attempt=tick, updated=tick, ok=True, items=loader(day))
            except Exception:
                daily[category] = dict(day=day, attempt=tick, updated=0, ok=False, items=[])
        # Daily requests avoid ESPN's unsupported date-range query. Yesterday and
        # today refresh twice an hour; older results refresh daily for corrections.
        if publish: publish(self.snapshot(now))
        scores = self.state['scores']
        jobs = []
        for offset in range(-1, 8):
            date = now.date() - timedelta(days=offset)
            for league in LEAGUES:
                key = league + ':' + date.isoformat()
                old = scores.get(key, {})
                interval = 1800 if offset < 2 or not old.get('ok') else 86400
                if tick - old.get('attempt', 0) >= interval:
                    jobs.append((key, league, date))

        def load(job):
            key, league, date = job
            path, _, group, _ = LEAGUES[league]
            params = {'dates': date.strftime('%Y%m%d'), 'limit': 500}
            if group: params['groups'] = group
            try:
                data = fetch('https://site.api.espn.com/apis/site/v2/sports/' + path + '/scoreboard', params)
                if not isinstance(data.get('events'), list): raise ValueError('Missing events')
                return key, dict(attempt=tick, updated=tick, ok=True, items=final_scores(data, league, now))
            except Exception:
                return key, {**scores.get(key, {'items': [], 'updated': 0}), 'attempt': tick, 'ok': False}

        with ThreadPoolExecutor(max_workers=4) as executor:
            for key, value in executor.map(load, jobs):
                scores[key] = value
                if publish: publish(self.snapshot(now))
        cutoff = (now.date() - timedelta(days=7)).isoformat()
        self.state['scores'] = {k: v for k, v in scores.items() if k.split(':')[1] >= cutoff}
        self.save(self.path, self.state)
        return self.snapshot(now)

    def snapshot(self, now):
        day = now.date().isoformat()
        items, unavailable = [], []
        for category in ('history', 'observances', 'quotes'):
            group = self.state['daily'].get(category, {})
            if group.get('day') == day and group.get('ok'):
                items.extend(group['items'][:10])
            else:
                unavailable.append(category)
        cutoff = (now.date() - timedelta(days=7)).isoformat()
        rows = {}
        failed = False
        for key, group in self.state['scores'].items():
            if not cutoff <= key.split(':')[1] <= day: continue
            failed |= not group.get('ok', False)
            for row in group['items']:
                if cutoff <= row.get('played', '')[:10] <= day:
                    rows[row['id']] = {**row, 'cached': not group.get('ok', False)}
        # Favorite results are placed first in the server list; the UI mixes all
        # results fairly with the other categories without multiplying duplicates.
        items.extend(sorted(rows.values(), key=lambda r: (r.get('favorite', False), r['played']), reverse=True))
        if failed or not self.state['scores']: unavailable.append('sports')
        return dict(day=day, items=items, unavailable=unavailable, seconds=15, sports_days=7)
