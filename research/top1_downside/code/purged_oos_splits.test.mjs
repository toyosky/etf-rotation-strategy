import assert from 'node:assert/strict';
import {expandingPurgedSplits} from './purged_oos_splits.mjs';
const d=['2026-01-05','2026-01-06','2026-01-07','2026-01-08','2026-01-09','2026-01-12','2026-01-13'];
const rows=d.map((date,i)=>({decisionDate:date,labelEndDate:d[Math.min(i+2,d.length-1)]}));
const w=[{start:'2026-01-12',end:'2026-01-13'}];
assert.deepEqual(expandingPurgedSplits(rows,w)[0].train,[0,1,2]);
assert.deepEqual(expandingPurgedSplits(rows,w,{embargoSessions:1})[0].train,[0,1]);
assert.equal(expandingPurgedSplits(rows,[{start:d[0],end:d[1]}])[0].status,'insufficient_train');
assert.throws(()=>expandingPurgedSplits(rows,[],{embargoSessions:-1}),/invalid embargo/);
// A sparse Top1 sample list is not a market-session calendar: the two
// approaches produce different eligibility for the same 2-session embargo.
const sparse=[{decisionDate:d[0],labelEndDate:d[0]},
 {decisionDate:d[1],labelEndDate:d[1]},
 {decisionDate:d[5],labelEndDate:d[6]}];
assert.deepEqual(expandingPurgedSplits(sparse,w,{embargoSessions:2})[0].train,[]);
assert.deepEqual(expandingPurgedSplits(sparse,w,{embargoSessions:2,marketCalendar:d})[0].train,[0,1]);
assert.throws(()=>expandingPurgedSplits(sparse,w,{marketCalendar:[d[0],d[1],d[1]]}),/invalid market calendar/);
assert.throws(()=>expandingPurgedSplits(sparse,w,{marketCalendar:d.slice(0,-1)}),/sample date missing/);
assert.equal(expandingPurgedSplits(rows,[{start:'2027-01-01',end:'2027-01-31'}])[0].status,'no_test');
// Row order is not guaranteed by upstream SQL; the cutoff must use the
// earliest test decision date rather than the first matching array index.
const unsorted=[rows[5],rows[0],rows[4],rows[1],rows[6],rows[2],rows[3]];
const chronological=expandingPurgedSplits(rows,w,{marketCalendar:d})[0];
const shuffled=expandingPurgedSplits(unsorted,w,{marketCalendar:d})[0];
assert.equal(shuffled.cutoff,chronological.cutoff);
assert.deepEqual(shuffled.train.map(i=>unsorted[i].decisionDate).sort(),chronological.train.map(i=>rows[i].decisionDate).sort());
console.log('purged expanding OOS split tests passed');
