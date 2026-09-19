"""Small, cached public feeds. Never sends calendar/configuration data to providers."""
import hashlib
import json
import random
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

import requests
from team_sports import TEAMS, fetch_team, card

HEADERS = {'User-Agent': 'FamilyWall/2.0 (personal dashboard; https://github.com/erniediaz/FamilyWall)'}


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


class Highlights:
    """Feed state is separate from the private calendar cache and safe to discard."""
    def __init__(self, path, save):
        self.path, self.save = Path(path), save
        try:
            self.state = json.loads(self.path.read_text())
        except (OSError, ValueError):
            self.state = {}
        self.state.setdefault('daily', {})
        self.state.pop('scores', None)  # Discard the old league-wide results cache.
        self.state.setdefault('teams', {})

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
        if publish: publish(self.snapshot(now))
        teams = self.state['teams']
        jobs = [key for key in TEAMS if tick - teams.get(key, {}).get('attempt', 0) >= 1800]

        def load(key):
            try:
                data = fetch_team(key, now, fetch)
                return key, dict(attempt=tick, updated=tick, ok=True, data=data)
            except Exception:
                return key, {**teams.get(key, {'updated': 0}), 'attempt': tick, 'ok': False}

        with ThreadPoolExecutor(max_workers=3) as executor:
            for key, value in executor.map(load, jobs):
                teams[key] = value
                if publish: publish(self.snapshot(now))
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
        failed = False
        for key in TEAMS:
            group = self.state['teams'].get(key, {})
            if not group.get('ok'): failed = True
            if not group.get('data') or now.timestamp() - group.get('updated', 0) > 86400:
                continue
            row = card(key, group['data'], now, cached=not group.get('ok', False))
            if row: items.append(row)
        if failed: unavailable.append('sports')
        return dict(day=day, items=items, unavailable=unavailable, seconds=15, sports_mode='teams')
