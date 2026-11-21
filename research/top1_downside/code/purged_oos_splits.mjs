// Research-only, expanding-window OOS splitter. Never import from production.
// All timestamps are ISO market dates. labelEndDate must be the final market date
// used by the forward outcome, NOT the decision date plus calendar days.
// Samples with missing/invalid forward labels must be excluded upstream.
// Training rows are eligible only when their outcome is fully known before
// the embargo boundary preceding the first test decision.
export function expandingPurgedSplits(rows, testWindows, {embargoSessions=0, minTrain=1}={}) {
  if (!Number.isInteger(embargoSessions)||embargoSessions<0) throw new Error('invalid embargo');
  if (!Number.isInteger(minTrain)||minTrain<1) throw new Error('invalid minTrain');
  if (!Array.isArray(rows)||!Array.isArray(testWindows)) throw new Error('arrays required');
  if (rows.some(r=>!r||typeof r.decisionDate!=='string'||typeof r.labelEndDate!=='string'||r.labelEndDate<r.decisionDate))
    throw new Error('invalid sample dates');
  const dates=[...new Set(rows.map(r=>r.decisionDate))].sort();
  return testWindows.map(({start,end})=>{
    if(typeof start!=='string'||typeof end!=='string'||end<start) throw new Error('invalid test window');
    const first=dates.findIndex(d=>d>=start);
    if(first<0||dates[first]>end) return {start,end,status:'no_test',train:[],test:[]};
    const cutoffIndex=first-embargoSessions-1;
    const cutoff=cutoffIndex>=0?dates[cutoffIndex]:null;
    const train=rows.map((r,i)=>({r,i})).filter(({r})=>cutoff!==null&&r.labelEndDate<=cutoff).map(({i})=>i);
    const test=rows.map((r,i)=>({r,i})).filter(({r})=>r.decisionDate>=start&&r.decisionDate<=end).map(({i})=>i);
    return {start,end,status:train.length>=minTrain?'ready':'insufficient_train',cutoff,train,test};
  });
}
