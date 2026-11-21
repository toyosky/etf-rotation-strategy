// Research only. Minute timestamps represent bar END times; the fill minute is excluded.
// This deliberately conservative eligibility rule prevents pre-fill extrema leakage.
// A minute-close fill is not proven executable by this helper.
export function executableExcursion({calendar, decisionDate, executionDate, horizon,
  entryPrice, fillTime, entryMinutes, laterDailyBars, priceBasis, minuteBasis, expectedPostFillMinuteTimes}) {
  if (!Number.isInteger(horizon) || horizon < 1) throw new Error('invalid horizon');
  if (!Number.isFinite(entryPrice) || entryPrice <= 0) throw new Error('invalid entry price');
  if (!Array.isArray(calendar) || new Set(calendar).size !== calendar.length ||
      calendar.some((d,i) => i && d <= calendar[i-1])) throw new Error('invalid calendar');
  if (!/^([01][0-9]|2[0-3]):[0-5][0-9]$/.test(fillTime || '')) throw new Error('invalid fill time');
  if (!priceBasis || !minuteBasis || priceBasis !== minuteBasis)
    return {status:'price_basis_unverified'};
  const i=calendar.indexOf(decisionDate);
  if (i<0) return {status:'decision_date_absent'};
  const dates=calendar.slice(i+1,i+1+horizon);
  if (dates.length!==horizon) return {status:'right_censored',available:dates.length};
  if (dates[0]!==executionDate) return {status:'execution_date_mismatch'};
  if (!Array.isArray(entryMinutes) || !Array.isArray(laterDailyBars))
    throw new Error('arrays required');
  const minutes=entryMinutes.filter(b=>b.date===executionDate);
  if (new Set(minutes.map(b=>b.time)).size!==minutes.length)
    return {status:'duplicate_minute_times'};
  // Exclude the bar ending at fillTime: its high/low may precede the fill.
  const eligible=minutes.filter(b=>b.time>fillTime && b.time<='15:00');
  if (!eligible.length) return {status:'no_post_fill_minutes'};
  // Without an independently verified complete session clock, a partial minute
  // feed could silently understate MAE and MFE. Do not issue a usable label.
  if (!Array.isArray(expectedPostFillMinuteTimes) || !expectedPostFillMinuteTimes.length ||
      new Set(expectedPostFillMinuteTimes).size!==expectedPostFillMinuteTimes.length ||
      expectedPostFillMinuteTimes.some(t=>typeof t!=='string' || t<=fillTime || t>'15:00'))
    return {status:'minute_calendar_unverified'};
  const actualTimes=new Set(eligible.map(b=>b.time));
  if (actualTimes.size!==expectedPostFillMinuteTimes.length ||
      expectedPostFillMinuteTimes.some(t=>!actualTimes.has(t)))
    return {status:'incomplete_post_fill_minutes',expected:expectedPostFillMinuteTimes.length,observed:actualTimes.size};
  if (eligible.some(b=>!valid(b))) return {status:'invalid_minute_ohlc'};
  if (new Set(laterDailyBars.map(b=>b.date)).size!==laterDailyBars.length)
    return {status:'duplicate_daily_dates'};
  const later=dates.slice(1).map(d=>laterDailyBars.find(b=>b.date===d));
  if (later.some(b=>!b)) return {status:'missing_later_sessions'};
  if (later.some(b=>!valid(b))) return {status:'invalid_daily_ohlc'};
  const all=[...eligible,...later];
  const low=Math.min(...all.map(b=>b.low));
  const high=Math.max(...all.map(b=>b.high));
  const trough=all.find(b=>b.low===low);
  return {status:'post_fill_price_path_proxy',horizon,
    loss:Math.max(0,1-low/entryPrice),
    favorable:Math.max(0,high/entryPrice-1),
    troughDate:trough.date, entrySessionMinuteCount:eligible.length,
    // This is NOT a proven executable holding: PIT premium, route, fill and
    // subsequent exit/switch are independent mandatory validation gates.
    caveat:'requires_audited_fill_pit_premium_and_route'};
}
function valid(b) {
  return !!b && [b.open,b.high,b.low,b.close].every(Number.isFinite) &&
    b.low>0 && b.high>=b.low && b.open>=b.low && b.open<=b.high &&
    b.close>=b.low && b.close<=b.high;
}
