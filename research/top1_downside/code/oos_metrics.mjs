// Research-only OOS evaluation metrics. No fitting or production imports.
// y is nonnegative future adverse excursion, q is a forecast of its tau quantile.
export function quantileDiagnostics(observations, tau=0.9) {
  if (!Number.isFinite(tau)||tau<=0||tau>=1) throw new Error('invalid quantile');
  if (!Array.isArray(observations)||!observations.length) throw new Error('empty observations');
  let loss=0, covered=0, under=0;
  for (const o of observations) {
    if (!o || !Number.isFinite(o.y) || o.y<0 || !Number.isFinite(o.q) || o.q<0)
      throw new Error('invalid observation');
    const residual=o.y-o.q;
    loss+=residual>=0?tau*residual:(tau-1)*residual;
    if (o.y<=o.q) covered++;
    if (o.y>o.q) under++;
  }
  return {n:observations.length,tau,pinball:loss/observations.length,
    coverage:covered/observations.length,exceedance:under/observations.length,
    coverageError:covered/observations.length-tau};
}
export function binaryDiagnostics(observations) {
  if (!Array.isArray(observations)||!observations.length) throw new Error('empty observations');
  let brier=0, logloss=0, positives=0;
  for (const o of observations) {
    if (!o || (o.y!==0&&o.y!==1) || !Number.isFinite(o.p)||o.p<0||o.p>1)
      throw new Error('invalid observation');
    positives+=o.y;
    brier+=(o.p-o.y)**2;
    const p=Math.max(1e-15,Math.min(1-1e-15,o.p));
    logloss-=o.y*Math.log(p)+(1-o.y)*Math.log1p(-p);
  }
  return {n:observations.length,positives,prevalence:positives/observations.length,
    brier:brier/observations.length,logloss:logloss/observations.length};
}
