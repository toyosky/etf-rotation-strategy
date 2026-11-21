// Research-only chronological OOS splitter. No production imports.
// marketCalendar is the authoritative exchange-session sequence. A sparse
// ETF/Top1 sample-date list must never define an embargo of N sessions.
// labelEndDate is the final exchange date touched by the forward label.
export function expandingPurgedSplits(rows, testWindows, {embargoSessions=0, minTrain=1, marketCalendar}={}) {
  if (!Number.isInteger(embargoSessions)||embargoSessions<0) throw new Error('invalid embargo');
  if (!Number.isInteger(minTrain)||minTrain<1) throw new Error('invalid minTrain');
  if (!Array.isArray(rows)||!Array.isArray(testWindows)) throw new Error('arrays required');
  const validDate = s => typeof s==='string' && /^\d{4}-\d{2}-\d{2}$/.test(s) && !Number.isNaN(Date.parse(s)) && new Date(s).toISOString().slice(0,10)===s;
  if (rows.some(r=>!r||!validDate(r.decisionDate)||!validDate(r.labelEndDate)||r.labelEndDate<r.decisionDate))
    throw new Error('invalid sample dates');
  const dates = marketCalendar ?? [...new Set(rows.map(r=>r.decisionDate))].sort();
  if (!Array.isArray(dates)||dates.some(d=>!validDate(d))||dates.some((d,i)=>i>0&&d<=dates[i-1]))
    throw new Error('invalid market calendar');
  if (marketCalendar && rows.some(r=>!dates.includes(r.decisionDate)||!dates.includes(r.labelEndDate)))
    throw new Error('sample date missing from market calendar');
  return testWindows.map(({start,end})=>{
    if(!validDate(start)||!validDate(end)||end<start) throw new Error('invalid test window');
    const test=rows.map((r,i)=>({r,i})).filter(({r})=>r.decisionDate>=start&&r.decisionDate<=end).map(({i})=>i);
    if (!test.length) return {start,end,status:'no_test',train:[],test:[]};
    const firstDate=rows[test[0]].decisionDate;
    const first=dates.indexOf(firstDate);
    const cutoffIndex=first-embargoSessions-1;
    const cutoff=cutoffIndex>=0?dates[cutoffIndex]:null;
    const train=rows.map((r,i)=>({r,i})).filter(({r})=>cutoff!==null&&r.labelEndDate<=cutoff).map(({i})=>i);
    return {start,end,status:train.length>=minTrain?'ready':'insufficient_train',cutoff,train,test};
  });
}
