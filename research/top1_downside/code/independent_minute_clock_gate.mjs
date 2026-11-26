// Research-only provenance gate. The expected session clock MUST be supplied
// independently of observed price bars. This module cannot certify a source.
const TIME=/^([01][0-9]|2[0-3]):[0-5][0-9]$/;
export function verifyIndependentMinuteClock({clock, bars, fillTime, executionDate}) {
  if (!TIME.test(fillTime || '')) return {status:'invalid_fill_time'};
  if (!clock || clock.date!==executionDate ||
      typeof clock.source!=='string' || !clock.source.trim() ||
      typeof clock.sourceVersion!=='string' || !clock.sourceVersion.trim() ||
      typeof clock.sourceHash!=='string' || !/^[a-f0-9]{64}$/i.test(clock.sourceHash) ||
      clock.derivedFromObservedBars!==false ||
      clock.timestampSemantics!=='bar_end' ||
      !Array.isArray(clock.expectedTimes) || !clock.expectedTimes.length)
    return {status:'unverified_clock_provenance'};
  const expected=clock.expectedTimes;
  // A fill outside continuous auction cannot be validated by this clock.
  // A 15:00 fill would otherwise pass vacuously with zero post-fill bars.
  if (!Array.isArray(bars)) return {status:'invalid_bars'};
  // Only the standard mainland ETF/LOF continuous-auction session is certified here.
  // Special sessions must be handled by a separately verified exchange calendar.
  if (clock.sessionType!=='regular_cn_a_share')
    return {status:'unsupported_session_type'};
  const canonical=[];
  for (const [start,end] of [[9*60+31,11*60+30],[13*60+1,15*60]]) {
    for(let minute=start;minute<=end;minute++)
      canonical.push(`${String(Math.floor(minute/60)).padStart(2,'0')}:${String(minute%60).padStart(2,'0')}`);
  }
  if (expected.length!==canonical.length || expected.some((t,i)=>t!==canonical[i]))
    return {status:'noncanonical_regular_session_clock',expectedCount:canonical.length,observedCount:expected.length};
  if (expected.some(t=>!TIME.test(t)) ||
      expected.some((t,i)=>i>0 && t<=expected[i-1]))
    return {status:'invalid_expected_clock'};
  // The caller must provide the full session, not just post-fill bars.
  if (!expected.some(t=>t<='11:30') || !expected.some(t=>t>='13:01') ||
      expected[expected.length-1]!=='15:00')
    return {status:'incomplete_session_clock'};
  if (!canonical.includes(fillTime)) return {status:'fill_outside_verified_session'};
  const observed=bars.filter(b=>b.date===executionDate).map(b=>b.time);
  if (observed.some(t=>!TIME.test(t)) || new Set(observed).size!==observed.length)
    return {status:'invalid_observed_clock'};
  if (observed.some(t=>!canonical.includes(t)))
    return {status:'observed_outside_verified_session'};
  const post=expected.filter(t=>t>fillTime);
  if (!post.length) return {status:'no_post_fill_session'};
  const actual=new Set(observed.filter(t=>t>fillTime));
  const missing=post.filter(t=>!actual.has(t));
  const unexpected=[...actual].filter(t=>!post.includes(t));
  if (missing.length || unexpected.length)
    return {status:'clock_mismatch',expected:post.length,observed:actual.size,
      missing,unexpected};
  return {status:'clock_matched_unverified_source_authenticity',
    expectedPostFillMinuteTimes:post,
    provenance:{source:clock.source,sourceVersion:clock.sourceVersion,sourceHash:clock.sourceHash}};
}
