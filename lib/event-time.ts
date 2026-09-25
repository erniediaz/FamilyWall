// Bound the cache even if callers supply many different time zones.
const formatters = new Map<string, {clock:Intl.DateTimeFormat; day:Intl.DateTimeFormat; date:Intl.DateTimeFormat}>();
function forZone(timeZone:string) {
  let value = formatters.get(timeZone);
  if (!value) {
    value = {
      clock:new Intl.DateTimeFormat('en-US', {timeZone, hour:'numeric', minute:'2-digit'}),
      day:new Intl.DateTimeFormat('en-CA', {timeZone, year:'numeric', month:'2-digit', day:'2-digit'}),
      date:new Intl.DateTimeFormat('en-US', {timeZone, month:'short', day:'numeric'})
    };
    if (formatters.size >= 8) formatters.delete(formatters.keys().next().value!);
    formatters.set(timeZone, value);
  }
  return value;
}

export function eventTimeRange(start: string, end: string, timeZone: string): string {
  const first = new Date(start), last = new Date(end);
  const {clock, day, date} = forZone(timeZone);
  if (!Number.isFinite(first.getTime())) return '';
  if (!Number.isFinite(last.getTime()) || last <= first) return clock.format(first);
  if (day.format(first) !== day.format(last)) {
    return `${date.format(first)}, ${clock.format(first)} – ${date.format(last)}, ${clock.format(last)}`;
  }
  const a = clock.formatToParts(first), b = clock.formatToParts(last);
  const samePeriod = a.find(p=>p.type==='dayPeriod')?.value === b.find(p=>p.type==='dayPeriod')?.value;
  const begin = (samePeriod ? a.filter(p=>p.type!=='dayPeriod') : a).map(p=>p.value).join('').trim();
  return `${begin}–${clock.format(last)}`;
}
