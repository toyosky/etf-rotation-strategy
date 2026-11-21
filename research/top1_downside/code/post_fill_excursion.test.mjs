import assert from 'node:assert/strict';
import {executableExcursion} from './post_fill_excursion.mjs';
const bar=(date,time,low,high)=>({date,time,open:100,close:100,low,high});
const input={
 calendar:['2026-11-16','2026-11-17','2026-11-18'],
 decisionDate:'2026-11-16',executionDate:'2026-11-17',
 horizon:2,entryPrice:100,fillTime:'09:35',
 priceBasis:'raw',minuteBasis:'raw',
 entryMinutes:[bar('2026-11-17','09:34',70,130),
   bar('2026-11-17','09:35',80,120),
   bar('2026-11-17','09:36',95,104)],
 laterDailyBars:[bar('2026-11-18',undefined,90,110)]
};
const result=executableExcursion(input);
assert.equal(result.status,'post_fill_price_path_proxy');
assert.ok(Math.abs(result.loss-0.10)<1e-12);
assert.ok(Math.abs(result.favorable-0.10)<1e-12);
assert.equal(result.entrySessionMinuteCount,1);
assert.equal(executableExcursion({...input,priceBasis:'adjusted'}).status,'price_basis_unverified');
assert.equal(executableExcursion({...input,fillTime:'15:00'}).status,'no_post_fill_minutes');
assert.equal(executableExcursion({...input,laterDailyBars:[]}).status,'missing_later_sessions');
assert.equal(executableExcursion({...input,entryMinutes:[...input.entryMinutes,input.entryMinutes[0]]}).status,'duplicate_minute_times');
assert.equal(executableExcursion({...input,calendar:input.calendar.slice(0,2)}).status,'right_censored');
console.log('post-fill excursion tests passed');
