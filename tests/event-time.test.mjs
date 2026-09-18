import { test } from 'node:test';
import assert from 'node:assert/strict';
import { eventTimeRange } from '../lib/event-time.ts';
const range = (a,b) => eventTimeRange(a,b,'America/Denver').replace(/\s+/g,' ');
test('compact same-period range and explicit noon crossing',()=>{
  assert.equal(range('2026-09-17T15:30:00-06:00','2026-09-17T16:30:00-06:00'),'3:30–4:30 PM');
  assert.equal(range('2026-09-17T11:30:00-06:00','2026-09-17T13:00:00-06:00'),'11:30 AM–1:00 PM');
});
test('overnight range includes dates in display timezone',()=>{
  assert.equal(range('2026-09-18T04:00:00Z','2026-09-18T07:00:00Z'),'Sep 17, 10:00 PM – Sep 18, 1:00 AM');
});
test('absent or zero duration falls back to start',()=>{
  assert.equal(range('2026-09-17T15:30:00-06:00','invalid'),'3:30 PM');
  assert.equal(range('2026-09-17T15:30:00-06:00','2026-09-17T15:30:00-06:00'),'3:30 PM');
});
