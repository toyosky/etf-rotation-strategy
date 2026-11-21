import assert from 'node:assert/strict';
import {verifyIndependentMinuteClock} from './independent_minute_clock_gate.mjs';
const expectedTimes=[];
for(const [start,end] of [[571,690],[781,900]])
  for(let m=start;m<=end;m++) expectedTimes.push(`${String(Math.floor(m/60)).padStart(2,'0')}:${String(m%60).padStart(2,'0')}`);
assert.equal(expectedTimes.length,240);
const clock={date:'2026-11-20',source:'fixture-independent-calendar',sourceVersion:'test-v2',
 sourceHash:'a'.repeat(64),derivedFromObservedBars:false,timestampSemantics:'bar_end',
 sessionType:'regular_cn_a_share',expectedTimes};
const bars=clock.expectedTimes.map(time=>({date:clock.date,time}));
const args={clock,bars,fillTime:'09:35',executionDate:clock.date};
assert.equal(verifyIndependentMinuteClock(args).status,'clock_matched_unverified_source_authenticity');
assert.equal(verifyIndependentMinuteClock(args).expectedPostFillMinuteTimes.length,235);
assert.equal(verifyIndependentMinuteClock({...args,clock:{...clock,derivedFromObservedBars:true}}).status,'unverified_clock_provenance');
assert.equal(verifyIndependentMinuteClock({...args,clock:{...clock,expectedTimes:['09:31','09:36','11:30','13:01','15:00']}}).status,'noncanonical_regular_session_clock');
assert.equal(verifyIndependentMinuteClock({...args,clock:{...clock,sessionType:'special'}}).status,'unsupported_session_type');
assert.equal(verifyIndependentMinuteClock({...args,bars:bars.filter(x=>x.time!=='13:01')}).status,'clock_mismatch');
assert.equal(verifyIndependentMinuteClock({...args,bars:[...bars,bars[1]]}).status,'invalid_observed_clock');
console.log('independent minute clock gate synthetic tests passed');
