// Research-only regression checks for market-calendar label integrity.
// Run: node research/top1_downside/code/calendar_forward_excursion.edge.test.mjs
import assert from 'node:assert/strict';
import {forwardExcursion} from './calendar_forward_excursion.mjs';

const calendar=['2026-01-29','2026-01-30','2026-02-02','2026-02-03','2026-02-04'];
const bars=[
  {date:'2026-01-30',open:100,low:99,high:101,close:100},
  {date:'2026-02-02',open:90,low:80,high:100,close:85},
  {date:'2026-02-03',open:100,low:85,high:120,close:110},
  {date:'2026-02-04',open:95,low:90,high:105,close:100}
];
const args={calendar,bars,decisionDate:'2026-01-29',executionDate:'2026-01-30',entryPrice:100,horizon:3};
const r=forwardExcursion(args);
assert.equal(r.status,'price_proxy_only');
assert.ok(Math.abs(r.loss-0.2)<1e-12);
assert.ok(Math.abs(r.favorable-0.2)<1e-12);
assert.equal(r.troughDate,'2026-02-02');
assert.deepEqual(forwardExcursion({...args,bars:bars.filter(b=>b.date!=='2026-02-02')}).missing,['2026-02-02']);
assert.equal(forwardExcursion({...args,decisionDate:'2026-01-28'}).status,'decision_date_absent');
assert.throws(()=>forwardExcursion({...args,calendar:['2026-01-30','2026-01-29']}),/sorted unique/);
assert.throws(()=>forwardExcursion({...args,horizon:0}),/invalid horizon/);
assert.throws(()=>forwardExcursion({...args,entryPrice:0}),/invalid entry price/);
assert.equal(forwardExcursion({...args,horizon:5}).status,'right_censored');
assert.equal(forwardExcursion({...args,bars:[...bars,bars[0]]}).status,'duplicate_bar_dates');
assert.equal(forwardExcursion({...args,bars:bars.map(b=>b.date==='2026-02-02'?{...b,open:110}:b)}).status,'invalid_ohlc');
assert.equal(forwardExcursion({...args,bars:bars.map(b=>b.date==='2026-02-02'?{...b,close:70}:b)}).status,'invalid_ohlc');
assert.equal(forwardExcursion({...args,bars:bars.map(b=>b.date==='2026-02-02'?{...b,close:NaN}:b)}).status,'invalid_ohlc');
console.log('calendar label edge tests passed');
