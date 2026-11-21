import fs from "node:fs";
// Usage: node q6_daily5_replay.mjs path/to/20261120_prob_opportunity_oos_predictions.csv
// Reproduces every portfolio and deterministic annual-stratified block-bootstrap in the Q6 report.
const backtest=function backtest(input){
 const [h,...ls]=input.trim().split(/\r?\n/),names=h.split(",");
 const rows=ls.map((line,i)=>{const vs=line.split(","),o=Object.fromEntries(names.map((k,j)=>[k,vs[j]]));
  const D=+o.D,Db=+o.Dbase,p=(+o.pLoss5_full)-(+o.pLoss5_vol);
  const E=o.s?Math.max(0,Math.min(1,(1-1.1*Db/D)*Math.max(0,Math.min(1.8,1+2*p)))):0;
  return {...o,idx:i,ret:+o.ret,E,ratio:D/Db,yr:o.d.slice(0,4)};
 });
 const modes=["full","lock5","lock5floor5","dailyRaw","dailyFloor5","dailyStep5","dailyMin5"];
 const stats={};
 for(const mode of modes){
  let nav=1,peak=1,mdd=0,peakDate=null,troughDate=null,prev={},actualE=0,lockEnd=-1,episode=0;
  let cost=0,grossTurn=0,riskTrades=0,top1Switches=0,actions=0,sellActions=0,buyActions=0,minAction=Infinity;
  let cashWeighted=0,nonzeroDays=0,grossSignalDays=0,maskedSignalDays=0,cashOnlyDays=0,maxE=0;
  const series=[],perY={},startECounts={};
  let prevS="";
  for(const r of rows){
   const prevE=actualE,hadSymbol=!!r.s;
   if(r.E>1e-5)grossSignalDays++;
   if(!r.s){actualE=0;lockEnd=-1;}
   else if(mode==="full"){actualE=0;}
   else if(mode==="lock5"||mode==="lock5floor5"){
    if(r.idx>lockEnd){
     const target=mode==="lock5"?r.E:r.E>=.05?r.E:0;
     actualE=target;
     if(target>1e-5){lockEnd=r.idx+4;episode++;startECounts[r.d]=actualE;}
     else lockEnd=-1;
    }
   }
   else{
    const target=mode==="dailyRaw"||mode==="dailyStep5"?r.E:(r.E>=.05?r.E:0);
    const threshold=(mode==="dailyMin5"||mode==="dailyStep5")?.05:0;
    if(Math.abs(target-actualE) >=threshold-1e-12)actualE=target;
   }
   if(!Number.isFinite(actualE))throw Error("Nonfinite allocation on "+r.d);
   if(actualE>0)nonzeroDays++;
   maxE=Math.max(maxE,actualE);
   const capital={};if(hadSymbol)capital[r.s]=1-actualE;
   const wEntries=Object.entries(capital).filter(([s,w])=>w>1e-12);
   let turn=0;const symbols=new Set([...Object.keys(prev),...wEntries.map(x=>x[0])]);
   for(const s of symbols)turn+=Math.abs((capital[s]||0)-(prev[s]||0));
   const fee=turn*.0006;
   const grossRet=hadSymbol?(1-actualE)*r.ret:0;
   const factor=1+grossRet-fee;
   if(!(factor>0))throw Error("Invalid factor "+r.d+" "+mode);
   const oldNav=nav;nav*=factor;
   if(nav>peak){peak=nav;peakDate=r.d;}
   if(nav/peak-1 < mdd){mdd=nav/peak-1;troughDate=r.d;}
   const deltaE=actualE-prevE;
   if(Math.abs(deltaE)>1e-8){actions++;minAction=Math.min(minAction,Math.abs(deltaE));if(deltaE>0)sellActions++;else buyActions++;}
   if(prevS&&r.s&&prevS!==r.s)top1Switches++;
   cost+=fee;grossTurn+=turn;riskTrades+=turn>1e-12?1:0;cashWeighted+=actualE;cashOnlyDays+=!r.s?1:0;
   const date=r.yr; if(!perY[date])perY[date]={start:oldNav,end:nav,top:oldNav,mdd:0,actions:0,sells:0,buybacks:0,days:0,weightedCash:0,turn:0,fees:0,maxE:0,positiveSignals:0};const y=perY[date];
   y.end=nav;y.top=Math.max(y.top,nav);y.mdd=Math.min(y.mdd,nav/y.top-1);y.days++;y.weightedCash+=actualE;y.turn+=turn;y.fees+=fee;y.maxE=Math.max(y.maxE,actualE);
   if(Math.abs(deltaE)>1e-8){y.actions++;if(deltaE>0)y.sells++;else y.buybacks++;}
   if(r.E>1e-5)y.positiveSignals++;
   series.push({d:r.d,ret:factor-1,logret:Math.log(factor),Eraw:r.E,E:actualE,nav,fee,grossRet,deltaE,top1:r.s});
   prev=Object.fromEntries(wEntries);prevS=r.s;
  }
  const mean=series.reduce((a,x)=>a+x.ret,0)/series.length,sd=Math.sqrt(series.reduce((a,x)=>a+(x.ret-mean)**2,0)/(series.length-1));
  const cagr=nav**(244/series.length)-1,vol=sd*Math.sqrt(244);
  stats[mode]={nav,cagr,mdd,calmar:cagr/-mdd,annualVol:vol,sharpe:mean*244/vol,peakDate,troughDate,
   cost,turnover:grossTurn,riskTradingDays:riskTrades,top1Switches,actions,sellActions,buyActions,minAction:Number.isFinite(minAction)?minAction:null,
   episodes:episode,nonzeroDays,cashWeighted,averageE:cashWeighted/rows.length,maxE,grossSignalDays,cashOnlyDays,
   byYear:Object.fromEntries(Object.entries(perY).map(([year,y])=>[year,{return:y.end/y.start-1,mdd:y.mdd,actions:y.actions,sells:y.sells,buybacks:y.buybacks,avgE:y.weightedCash/y.days,maxE:y.maxE,turnover:y.turn,fees:y.fees,days:y.days,positiveSignals:y.positiveSignals}])),
   series};
 }
 const years=[...new Set(rows.map(x=>x.yr))], yearIndexes=years.map(y=>rows.map((r,i)=>r.yr===y?i:-1).filter(i=>i>=0));
 let seed=7261237;const rng=()=>{seed^=seed<<13;seed^=seed>>>17;seed^=seed<<5;return(seed>>>0)/4294967296};
 function boot(a,b,count=2500){
  const delta=a.series.map((z,i)=>z.logret-b.series[i].logret),excess=delta.reduce((s,x)=>s+x,0)*244/delta.length,arr=[];
  for(let z=0;z<count;z++){let acc=0;
   for(const ids of yearIndexes){let k=0;while(k<ids.length){let st=Math.floor(rng()*ids.length);for(let t=0;t<20&&k<ids.length;t++,k++)acc+=delta[ids[(st+t)%ids.length]];}}
   arr.push(acc*244/delta.length);
  }
  arr.sort((a,b)=>a-b);return {annualLogExcess:excess,CI95:[arr[Math.floor(.025*count)],arr[Math.floor(.975*count)]],bootstrapPPositive:arr.filter(x=>x>0).length/count};
 }
 const compare={};for(const key of modes.filter(s=>s!=="lock5"&&s!=="full"))compare[key]={vsLock5:boot(stats[key],stats.lock5),vsFull:boot(stats[key],stats.full)};
 compare.dailyMin5.vsDailyRaw=boot(stats.dailyMin5,stats.dailyRaw);
 compare.dailyMin5.vsDailyFloor5=boot(stats.dailyMin5,stats.dailyFloor5);
 compare.dailyMin5.vsDailyStep5=boot(stats.dailyMin5,stats.dailyStep5);
 compare.lock5floor5.vsLock5=boot(stats.lock5floor5,stats.lock5);
 const period={start:rows[0].d,end:rows[rows.length-1].d,days:rows.length,rawSignalDays:rows.filter(x=>x.E>1e-5).length};
 const result={period,summary:Object.fromEntries(Object.entries(stats).map(([k,{series,...s}])=>[k,s])),compare};
 const csv=["date,top1,forward_top1_return,raw_E,lock5_E,lock5floor5_E,dailyRaw_E,dailyFloor5_E,dailyStep5_E,dailyMin5_E,lock5_nav,dailyMin5_nav,dailyRaw_nav,dailyMin5_fee",
 ...rows.map((r,i)=>[r.d,r.s,r.ret,r.E,stats.lock5.series[i].E,stats.lock5floor5.series[i].E,stats.dailyRaw.series[i].E,stats.dailyFloor5.series[i].E,stats.dailyStep5.series[i].E,stats.dailyMin5.series[i].E,stats.lock5.series[i].nav,stats.dailyMin5.series[i].nav,stats.dailyRaw.series[i].nav,stats.dailyMin5.series[i].fee].join(","))].join("\n")+"\n";
 return {result,csv};
};
const input=fs.readFileSync(process.argv[2],"utf8");
const {result}=backtest(input);
console.log(JSON.stringify(result,null,2));
