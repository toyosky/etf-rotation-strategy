// Exploratory robustness: exact ticker with continuous prior vol20 tolerance.
// Not preregistered; supports sensitivity diagnosis only.
import fs from "node:fs";
const f=process.argv[2];if(!f)throw Error("CSV path required");
const [h,...lines]=fs.readFileSync(f,"utf8").trim().split("\n"),cs=h.split(","),I=Object.fromEntries(cs.map((k,i)=>[k,i]));
const data=lines.map(s=>s.split(",")).filter(r=>r[I.s]&&r[I.loss]!=="");
const pre=data.filter(r=>r[I.d]<"20260101"),post=data.filter(r=>r[I.d]>="20260101");
const v=r=>+r[I.vol],p=r=>+r[I.pLoss5_full],hit=r=>+r[I.loss]>=.05?1:0;
const exact=[];
for(const tol of [.002,.003,.005]){
 let n=0,evt=0,pr=0,cf=0,nRef=0;const missing={};
 for(const r of post){
   const rr=pre.filter(q=>q[I.s]===r[I.s]&&Math.abs(v(q)-v(r))<=tol);
   if(rr.length<10){missing[r[I.s]]=(missing[r[I.s]]||0)+1;continue;}
   n++;evt+=hit(r);pr+=p(r);cf+=rr.reduce((a,q)=>a+hit(q),0)/rr.length;nRef+=rr.length;
 }
 exact.push({volTolerance:tol,n,postShare:n/post.length,realizedEventRate:evt/n,forecastProbability:pr/n,
  historicalSameTickerSameVolRate:cf/n,residualDifference:evt/n-cf/n,meanPastMatches:nRef/n,unmatched:missing});
}
const quarters={};
for(const q of ["2026Q1","2026Q2","2026Q3","2026Q4"]){
 const r=post.filter(x=>x[I.fold]===q);const nr=r.filter(x=>x[I.s]!=="501018");
 const stats=a=>({n:a.length,actual:a.reduce((s,x)=>s+hit(x),0)/a.length,pred:a.reduce((s,x)=>s+p(x),0)/a.length});
 quarters[q]={all:stats(r),excludingOil:stats(nr)};
}
process.stdout.write(JSON.stringify({status:"exploratory_not_preregistered",exactTickerContinuousVol:exact,quarters},null,2)+"\n");
