'use client';
import { useEffect, useRef, useState } from 'react';
import { BookOpen, Sparkles, Quote, Trophy, Pause, Play } from 'lucide-react';
import { Highlight, highlightOrder, HIGHLIGHT_INTERVAL } from '@/lib/highlight-order';

export type HighlightsData = {day: string; items: Highlight[]; unavailable: string[]};
const EMPTY: Highlight[] = [];
const labels = {history: 'On this day', observances: 'Fun observances', quotes: 'A little perspective', sports: 'Your teams'};
const icons = {history: BookOpen, observances: Sparkles, quotes: Quote, sports: Trophy};

export function DailyHighlights({data, today, sleeping=false}: {data?: HighlightsData; today: string; sleeping?: boolean}) {
  const items = data?.day === today ? data.items : EMPTY;
  const latest = useRef(items);
  latest.current = items;
  const [active, setActive] = useState('');
  const [paused, setPaused] = useState(false);
  const queue = useRef<string[]>([]);
  const day = useRef('');
  const previous = useRef('');
  const next = useRef(() => {});
  next.current = () => {
    const available = new Set(latest.current.map(item => item.id));
    queue.current = queue.current.filter(id => available.has(id));
    if (!queue.current.length) {
      queue.current = highlightOrder(latest.current);
      if (queue.current.length > 1 && queue.current[0] === previous.current) queue.current.push(queue.current.shift()!);
    }
    const id = queue.current.shift() || '';
    previous.current = id;
    setActive(id);
  };
  useEffect(() => {
    if (day.current !== today) {
      day.current = today;
      queue.current = [];
      previous.current = '';
      next.current();
    } else if (!items.some(item => item.id === active)) next.current();
  }, [items, active, today]);
  // Polling the API never resets this timer or the current card.
  useEffect(() => {
    if (paused || sleeping) return;
    const timer = setInterval(() => next.current(), HIGHLIGHT_INTERVAL);
    return () => clearInterval(timer);
  }, [paused, sleeping]);
  const row = items.find(item => item.id === active);
  const Icon = row ? icons[row.category] : Sparkles;
  return <section className={'daily-highlights ' + (row?.category || '')} aria-label="Daily highlights">
    <div className="highlight-heading"><Icon aria-hidden="true"/><span>{row ? labels[row.category] : 'Daily highlights'}</span>
      <button type="button" onClick={() => setPaused(value => !value)} aria-label={paused ? 'Resume highlights' : 'Pause highlights'} title={paused ? 'Resume highlights' : 'Pause highlights'}>{paused ? <Play/> : <Pause/>}</button>
    </div>
    <div key={row?.id || 'waiting'} className="highlight-card">
      {row?.team ? <div className="team-snapshot">
        <h3>{row.team.name}</h3>
        <p className="team-record">Record {row.team.record} <span>· {row.team.standing}</span></p>
        <p title={row.team.last_title}><b>Last</b> {row.team.last}</p>
        <p title={row.team.next_title}><b>Next</b> {row.team.next}</p>
      </div> : <p className="highlight-text">{row?.text || 'A little history, a little inspiration, and your favorite teams.'}</p>}
      <div className="highlight-detail"><span title={row?.detail}>{row?.team ? 'Game times · Mountain' : row?.detail || 'Gathering today’s highlights…'}{row?.cached ? ' · saved data' : ''}</span>
        {row && <a href={row.url} target="_blank" rel="noreferrer" title={row.source}>{row.source}</a>}
      </div>
    </div>
  </section>;
}
