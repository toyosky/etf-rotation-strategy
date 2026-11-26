// Research-only calendar-aligned forward excursion labels. No production imports.
// Input: sorted unique ISO market dates and raw, same-basis OHLC bars for one instrument.
// Entry price is supplied by an independently audited execution router; daily open is NOT assumed executable.
export function forwardExcursion({calendar, bars, decisionDate, horizon, entryPrice, executionDate}) {
  if (!Number.isInteger(horizon) || horizon < 1) throw new Error('invalid horizon');
  if (!Number.isFinite(entryPrice) || entryPrice <= 0) throw new Error('invalid entry price');
  if (new Set(calendar).size !== calendar.length || calendar.some((d,i)=>i>0 && d<=calendar[i-1]))
    throw new Error('calendar must be sorted unique');
  const idx = calendar.indexOf(decisionDate);
  if (idx < 0) return {status:'decision_date_absent'};
  const future = calendar.slice(idx+1,idx+1+horizon);
  if (future.length !== horizon) return {status:'right_censored',available:future.length};
  if (executionDate !== future[0]) return {status:'execution_date_mismatch'};
  const source = bars instanceof Map ? [...bars.entries()].map(([date, bar]) => ({...bar, date})) : bars;
  if (!Array.isArray(source) || source.some(b=>!b || typeof b.date !== 'string'))
    throw new Error('bars must be dated records');
  if (new Set(source.map(b=>b.date)).size !== source.length)
    return {status:'duplicate_bar_dates'};
  const map = new Map(source.map(b=>[b.date,b]));
  const missing = future.filter(d=>!map.has(d));
  if (missing.length) return {status:'missing_market_sessions',missing};
  const selected = future.map(d=>map.get(d));
  if (selected.some(b=>!Number.isFinite(b.low)||!Number.isFinite(b.high)||!Number.isFinite(b.open)||!Number.isFinite(b.close)||b.low<=0||b.high<b.low||b.open<b.low||b.open>b.high||b.close<b.low||b.close>b.high))
    return {status:'invalid_ohlc'};
  // Additional validity gates (halt, PIT premium, adjustment, execution) remain external and mandatory.
  const minLow = Math.min(...selected.map(b=>b.low));
  const maxHigh = Math.max(...selected.map(b=>b.high));
  return {status:'price_proxy_only',horizon,loss:Math.max(0,1-minLow/entryPrice),
    favorable:Math.max(0,maxHigh/entryPrice-1),troughDate:future[selected.findIndex(b=>b.low===minLow)]};
}
