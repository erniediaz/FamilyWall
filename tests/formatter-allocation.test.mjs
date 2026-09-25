import {test} from 'node:test';
import assert from 'node:assert/strict';

test('repeated event formatting reuses formatters instead of allocating per call', async()=>{
  const Original=Intl.DateTimeFormat;
  let created=0;
  Intl.DateTimeFormat=new Proxy(Original,{construct(target,args){created++;return Reflect.construct(target,args)}});
  try {
    const {eventTimeRange}=await import('../lib/event-time.ts');
    for(let i=0;i<20000;i++) {
      const label=eventTimeRange('2026-09-17T11:30:00-06:00','2026-09-17T13:00:00-06:00','America/Denver');
      assert.equal(label.replace(/\s+/g,' '),'11:30 AM–1:00 PM');
    }
    assert.equal(created,3);
  } finally {Intl.DateTimeFormat=Original;}
});
