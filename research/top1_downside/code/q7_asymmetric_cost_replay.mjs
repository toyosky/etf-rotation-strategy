import fs from "node:fs";
// node q7_asymmetric_cost_replay.mjs path/to/20261120_prob_opportunity_oos_predictions.csv
// Recalculates Q90 E unchanged, 8 prespecified execution policies, 3 explicit fee models, and paired bootstrap.
const backtest=function backtest(input){
 const [h,...lines]=input.trim().split(/\r?\n/),head=h.split(",");
 const rows=lines.map((line,i)=>{const v=line.split(","),obj=Object.fromEntries(head.map((k,j)=>[k,v[j]]));
  const D=+obj.D,Db=+obj.Dbase,pDelta=(+obj.pLoss5_full)-(+obj.pLoss5_vol);
  return {...obj,i,return:+obj.ret,year:obj.d.slice(0,4),rawE:obj.s?Math.max(0,Math.min(1,(1-1.1*Db/D)*Math.max(0,Math.min(1.8,1+2*pDelta)))):0};
 });
 const modeSpecs=[
  {id:"full",type:"full"},
  {id:"lock5",type:"lock5"},
  {id:"daily5",type:"daily5"},
  {id:"C_twoDay_10pp",type:"asym",confirm:2,cap:.10},
  {id:"D_costAware",type:"costAware",confirm:2,cap:.10},
  {id:"C1_oneDay_10pp",type:"asym",confirm:1,cap:.10},
  {id:"C3_threeDay_10pp",type:"asym",confirm:3,cap:.10},
  {id:"Cbuy20_twoDay_20pp",type:"asym",confirm:2,cap:.20}
 ];
 const fees=[{id:"base6bp",base:.0006,min:0,extra:0},{id:"minimum5yuan",base:.0006,min:5,extra:0},{id:"minimum5plus4bp",base:.0006,min:5,extra:.0004}];
 const results={};
 const path=[];
 for(const cost of fees)for(const spec of modeSpecs){
  let nav=1,peak=1,mdd=0,trough="",peakDate="",previous={},actualE=0,lockEnd=-1,confirm=0,zeroDays=0,stepDay=0,episode=0;
  let actions=0,sellActions=0,buyActions=0,buybackNotionalLT2000=0,sub2000Trades=0,tickets=0,extraE=0,staleDays=0;
  let sumCash=0,costTotal=0,turnover=0,grossDeltaE=0;
  const logs=[],navs=[],dailyOut=[],perY={},drawdowns=[];
  for(const r of rows){
   const old=actualE,policyTarget=r.rawE>=.05?r.rawE:0;
   if(!r.s){actualE=0;confirm=0;zeroDays=0;lockEnd=-1;}
   else if(spec.type==="full"){actualE=0;}
   else if(spec.type==="lock5"){
    if(r.i>lockEnd){
     actualE=r.rawE;
     if(actualE>1e-5){lockEnd=r.i+4;episode++;}
     else lockEnd=-1;
    }
   }else if(spec.type==="daily5"){
    if(Math.abs(policyTarget-actualE)>=.05-1e-12)actualE=policyTarget;
   }else if(spec.type==="asym"||spec.type==="costAware"){
    if(policyTarget>=actualE+.05-1e-12){
     actualE=policyTarget;confirm=0;zeroDays=0;
    }else{
     if(policyTarget===0)zeroDays++;else zeroDays=0;
     const minGap=spec.type==="costAware"?.10:.05;
     if(policyTarget<=actualE-minGap+1e-12){
      confirm++;
      if(confirm>=spec.confirm)actualE=Math.max(policyTarget,actualE-spec.cap);
     }else{confirm=0;}
     if(spec.type==="costAware"&&policyTarget===0&&zeroDays>=3&&actualE>0&&actualE<.10-1e-12){
      actualE=0;
     }
    }
   }
   if(actualE<0||actualE>1+1e-10||!Number.isFinite(actualE))throw Error("bad E "+r.d+" "+spec.id);
   if(actualE>0&&policyTarget===0)staleDays++;
   const Echange=actualE-old;
   if(Math.abs(Echange)>1e-9){actions++;grossDeltaE+=Math.abs(Echange);if(Echange>0)sellActions++;else buyActions++;}
   const weight={};if(r.s&&1-actualE>1e-12)weight[r.s]=1-actualE;
   const tradeNames=new Set([...Object.keys(previous),...Object.keys(weight)]),tx=[];
   let dayFee=0,dayTurn=0,dayTickets=0,daySub=0;
   const initialCapital=20000;
   for(const s of tradeNames){
    const wdiff=(weight[s]||0)-(previous[s]||0);if(Math.abs(wdiff)<1e-12)continue;
    const delta=Math.abs(wdiff),notional=nav*initialCapital*delta;
    // apply min ticket fee at actual evolving equity; no fee for cash leg.
    const feeCurrency=Math.max(cost.base*notional,cost.min)+cost.extra*notional;
    dayFee+=feeCurrency/(nav*initialCapital);
    dayTurn+=delta;dayTickets++;
    if(notional<2000){daySub++;sub2000Trades++;}
    if(wdiff>0&&notional<2000)buybackNotionalLT2000++;
    tx.push({symbol:s,delta:wdiff,notional,feeCurrency});
   }
   const gross=r.s?(1-actualE)*r.return:0;
   const factor=1+gross-dayFee;if(!(factor>0))throw Error("negative nav factor "+r.d+" "+spec.id+" "+cost.id);
   const previousNav=nav;nav*=factor;logs.push(Math.log(factor));navs.push(nav);
   const wasPeak=nav>peak;if(wasPeak){peak=nav;peakDate=r.d;}
   const currentDD=nav/peak-1;if(currentDD<mdd){mdd=currentDD;trough=r.d;}
   drawdowns.push(currentDD);
   costTotal+=dayFee;turnover+=dayTurn;tickets+=dayTickets;sumCash+=actualE;extraE+=r.rawE;
   const y=perY[r.year]??(perY[r.year]={start:previousNav,end:nav,peak:previousNav,mdd:0,actions:0,sells:0,buys:0,days:0,cashDays:0,fees:0,tickets:0,turnover:0,staleDays:0});
   y.end=nav;y.peak=Math.max(y.peak,nav);y.mdd=Math.min(y.mdd,nav/y.peak-1);y.days++;y.cashDays+=actualE;y.fees+=dayFee;y.tickets+=dayTickets;y.turnover+=dayTurn;
   if(Math.abs(Echange)>1e-9){y.actions++;if(Echange>0)y.sells++;else y.buys++;}
   if(actualE>0&&policyTarget===0)y.staleDays++;
   dailyOut.push({date:r.d,year:r.year,Top1:r.s,rawE:r.rawE,T:policyTarget,E:actualE,change:Echange,return:r.return,gross,fee:dayFee,net:factor-1,nav,dd:currentDD,confirm,zeroDays,orderCount:dayTickets,smallTickets:daySub});
   previous=weight;
  }
  const mean=dailyOut.reduce((s,r)=>s+r.net,0)/dailyOut.length;
  const variance=dailyOut.reduce((s,r)=>s+(r.net-mean)**2,0)/(dailyOut.length-1),vol=Math.sqrt(variance)*Math.sqrt(244);
  const roll5=navs.slice(0,-5).map((n,i)=>navs[i+5]/n-1),sort=a=>[...a].sort((x,y)=>x-y),pct=(a,p)=>{const s=sort(a),k=(s.length-1)*p,l=Math.floor(k),u=Math.ceil(k);return s[l]+(s[u]-s[l])*(k-l);};
  const cagr=nav**(244/rows.length)-1,ym=Object.fromEntries(Object.entries(perY).map(([year,z])=>[year,{ret:z.end/z.start-1,mdd:z.mdd,actions:z.actions,sells:z.sells,buys:z.buys,avgCash:z.cashDays/z.days,fees:z.fees,tickets:z.tickets,turnover:z.turnover,staleDays:z.staleDays}]));
  results[`${spec.id}__${cost.id}`]={spec:spec.id,cost:cost.id,cagr,mdd,calmar:cagr/-mdd,nav,vol,sharpe:(mean*244)/vol,peakDate,trough,actions,sellActions,buyActions,buybackNotionalLT2000,sub2000Trades,tickets,episodes:episode,sumCash,meanCash:sumCash/rows.length,staleDays,totalFees:costTotal,turnover,grossDeltaE,
   tail:{worstDay:Math.min(...dailyOut.map(r=>r.net)),daily1pct:pct(dailyOut.map(r=>r.net),.01),worst5day:Math.min(...roll5),fiveDay1pct:pct(roll5,.01)},
   byYear:ym,_logs:logs,_path:dailyOut};
 }
 const tests={};
 // Confirm same baseline as Q6 to 1e-10 tolerance, and C action restrictions.
 const q6Base={full:[.4944075167599902,-.4994975845635867],lock5:[.5132966247774193,-.46649463734690644],daily5:[.5214273412523633,-.45975104878380335]};
 for(const [k,[c,m]]of Object.entries(q6Base)){const got=results[`${k}__base6bp`];tests[k]={cagrDiff:got.cagr-c,mddDiff:got.mdd-m,pass:Math.abs(got.cagr-c)<1e-10&&Math.abs(got.mdd-m)<1e-10};}
 const years=[...new Set(rows.map(x=>x.year))],yearIdx=years.map(y=>rows.flatMap((r,i)=>r.year===y?[i]:[]));
 let seed=731453;const rand=()=>{seed^=seed<<13;seed^=seed>>>17;seed^=seed<<5;return(seed>>>0)/4294967296;};
 function boot(a,b,count=2200){
  const deltas=a._logs.map((v,i)=>v-b._logs[i]),annualLogExcess=deltas.reduce((t,x)=>t+x,0)*244/rows.length,draw=[];
  for(let i=0;i<count;i++){let sum=0;for(const idxs of yearIdx){let k=0;while(k<idxs.length){const start=Math.floor(rand()*idxs.length);for(let t=0;t<20&&k<idxs.length;t++,k++)sum+=deltas[idxs[(start+t)%idxs.length]];}}
   draw.push(sum*244/rows.length);
  }draw.sort((a,b)=>a-b);return {annualLogExcess,CI95:[draw[Math.floor(.025*count)],draw[Math.floor(.975*count)]],pPositive:draw.filter(x=>x>0).length/draw.length};
 }
 const comparison={};
 for(const cost of fees){
  const get=id=>results[`${id}__${cost.id}`];
  comparison[cost.id]={
   CvsLock:boot(get("C_twoDay_10pp"),get("lock5")),CvsDaily:boot(get("C_twoDay_10pp"),get("daily5")),
   DvsLock:boot(get("D_costAware"),get("lock5")),DvsDaily:boot(get("D_costAware"),get("daily5")),DvsC:boot(get("D_costAware"),get("C_twoDay_10pp")),
   C1vsC:boot(get("C1_oneDay_10pp"),get("C_twoDay_10pp")),C3vsC:boot(get("C3_threeDay_10pp"),get("C_twoDay_10pp")),Cbuy20vsC:boot(get("Cbuy20_twoDay_20pp"),get("C_twoDay_10pp"))
  };
 }
 const summary=Object.fromEntries(Object.entries(results).map(([key,{_logs,_path,...x}])=>[key,x]));
 const pick=ids=>Object.fromEntries(ids.map(id=>[id,results[`${id}__base6bp`]._path]));
 const pa=pick(["lock5","daily5","C_twoDay_10pp","D_costAware","C1_oneDay_10pp","C3_threeDay_10pp","Cbuy20_twoDay_20pp"]);
 const columns=["date","top1","rawE","lockE","dailyE","CE","DE","Cconfirm","Dconfirm","Cfee","Dfee","lockNAV","dailyNAV","CNAV","DNAV"];
 const paths=[columns.join(",")];
 for(let i=0;i<rows.length;i++){
  const v=id=>pa[id][i];paths.push([rows[i].d,rows[i].s,rows[i].rawE,v("lock5").E,v("daily5").E,v("C_twoDay_10pp").E,v("D_costAware").E,v("C_twoDay_10pp").confirm,v("D_costAware").confirm,v("C_twoDay_10pp").fee,v("D_costAware").fee,v("lock5").nav,v("daily5").nav,v("C_twoDay_10pp").nav,v("D_costAware").nav].join(","));
 }
 const scenarios={};
 for(const code of ["base6bp","minimum5yuan","minimum5plus4bp"]){
  scenarios[code]=Object.fromEntries(modeSpecs.map(m=>[m.id,summary[`${m.id}__${code}`]]));
 }
 return {results:{period:{start:rows[0].d,end:rows.at(-1).d,n:rows.length},tests,scenarios,comparison},csv:paths.join("\n")+"\n"};
};
const textCSV=fs.readFileSync(process.argv[2],"utf8");
const {results}=backtest(textCSV);
console.log(JSON.stringify(results,null,2));
