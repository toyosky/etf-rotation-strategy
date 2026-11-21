import fs from "node:fs";
// node q7b_oneshot_reentry_replay.mjs <Q90 archived prediction daily CSV>
const simulateOneshot=function simulateOneshot(input){
 const [h,...lines]=input.trim().split(/\r?\n/),fields=h.split(",");
 const rows=lines.map((line,i)=>{const z=line.split(","),obj=Object.fromEntries(fields.map((k,j)=>[k,z[j]])),rat=(+obj.Dbase)/(+obj.D),p=(+obj.pLoss5_full)-(+obj.pLoss5_vol);
  const E=obj.s?Math.max(0,Math.min(1,(1-1.1*rat)*Math.max(0,Math.min(1.8,1+2*p)))):0;
  return {d:obj.d,s:obj.s,year:obj.d.slice(0,4),i,ret:+obj.ret,E,T:E>=.05?E:0};
 });
 const variants=[{name:"S1_2day_oneshot",confirm:2,gap:.05,dust:false},
 {name:"S2_2day_10pp_oneshot",confirm:2,gap:.10,dust:true},
 {name:"S3_3day_oneshot",confirm:3,gap:.05,dust:false},
 {name:"fixedCash8_67pct",constant:true}];
 const costs=[{name:"base6bp",minimum:0,extra:0},{name:"minimum5yuan",minimum:5,extra:0},{name:"minimum5plus4bp",minimum:5,extra:.0004}];
 const result={},paths={};
 for(const cost of costs)for(const variant of variants){
  const key=variant.name+"__"+cost.name;let nav=1,high=1,mdd=0,positivePeakDate="",trough="",actualE=0,confirm=0,zeroDays=0,prior={},actions=0,sells=0,buys=0,staleDays=0,smallActions=0,totalFees=0,tickets=0,turnover=0,sumE=0;
  const byYear={},logs=[],stream=[];
  for(const r of rows){
   const before=actualE,oldRisk=!!r.s;
   if(!oldRisk){actualE=0;confirm=0;zeroDays=0;}
   else if(variant.constant){actualE=.08673607020216331;}
   else if(r.T>=actualE+.05-1e-12){actualE=r.T;confirm=0;zeroDays=0;}
   else {
    if(r.T===0)zeroDays++;else zeroDays=0;
    if(r.T<=actualE-variant.gap+1e-12){confirm++;if(confirm>=variant.confirm){actualE=r.T;confirm=0;}}
    else{confirm=0;}
    if(variant.dust&&r.T===0&&zeroDays>=3&&actualE>0&&actualE<.10-1e-12){actualE=0;confirm=0;}
   }
   const change=actualE-before;if(Math.abs(change)>1e-9){actions++;if(change>0)sells++;else buys++;if(Math.abs(change)<.10)smallActions++;}
   if(actualE>0&&r.T===0)staleDays++;
   const w=r.s&&1-actualE>1e-12?{[r.s]:1-actualE}:{};
   let dayFee=0,dayTickets=0,dayTurn=0;for(const sym of new Set([...Object.keys(prior),...Object.keys(w)])){
    const diff=Math.abs((prior[sym]||0)-(w[sym]||0));if(diff<1e-12)continue;
    const ticket=20000*nav*diff,charge=Math.max(.0006*ticket,cost.minimum)+ticket*cost.extra;
    dayFee+=charge/(20000*nav);dayTickets++;dayTurn+=diff;
   }
   const factor=1+(r.s?(1-actualE)*r.ret:0)-dayFee;
   if(!Number.isFinite(factor)||factor<=0)throw Error("bad factor "+r.d+" "+key);
   const old=nav;nav*=factor;high=Math.max(high,nav);if(nav===high)positivePeakDate=r.d;
   const dd=nav/high-1;if(dd<mdd){mdd=dd;trough=r.d;}
   sumE+=actualE;totalFees+=dayFee;tickets+=dayTickets;turnover+=dayTurn;logs.push(Math.log(factor));
   const y=byYear[r.year]??(byYear[r.year]={start:old,end:nav,peak:old,mdd:0,actions:0,buys:0,sells:0,tickets:0,fees:0,avgE:0,days:0});
   y.end=nav;y.peak=Math.max(y.peak,nav);y.mdd=Math.min(y.mdd,nav/y.peak-1);y.days++;y.avgE+=actualE;y.tickets+=dayTickets;y.fees+=dayFee;
   if(Math.abs(change)>1e-9){y.actions++;if(change>0)y.sells++;else y.buys++;}
   stream.push({d:r.d,Top1:r.s,Eraw:r.E,E:actualE,ret:r.ret,deltaE:change,nav,fee:dayFee,dd,confirm,zeroDays});
   prior=w;
  }
  const cagr=nav**(244/rows.length)-1;
  result[key]={cagr,mdd,calmar:cagr/-mdd,nav,actions,sells,buys,staleDays,smallActions,totalFees,tickets,turnover,meanE:sumE/rows.length,peakDate:positivePeakDate,trough,byYear:Object.fromEntries(Object.entries(byYear).map(([y,o])=>[y,{ret:o.end/o.start-1,mdd:o.mdd,actions:o.actions,sells:o.sells,buys:o.buys,tickets:o.tickets,fees:o.fees,meanE:o.avgE/o.days}])),_logs:logs};
  if(cost.name==="base6bp")paths[variant.name]=stream;
 }
 const boot={};const yr=[...new Set(rows.map(x=>x.year))],byY=yr.map(y=>rows.flatMap((r,i)=>r.year===y?[i]:[]));
 let seed=229103,rand=()=>{seed^=seed<<13;seed^=seed>>>17;seed^=seed<<5;return(seed>>>0)/4294967296};
 const comp=(a,b,n=2200)=>{const x=a.map((v,i)=>v-b[i]),point=x.reduce((s,z)=>s+z,0)*244/x.length,draw=[];
  for(let j=0;j<n;j++){let s=0;for(const ids of byY){let i=0;while(i<ids.length){const start=Math.floor(rand()*ids.length);for(let k=0;k<20&&i<ids.length;k++,i++)s+=x[ids[(start+k)%ids.length]];}}draw.push(s*244/x.length);}
  draw.sort((a,b)=>a-b);return {annualLogExcess:point,CI95:[draw[Math.floor(.025*n)],draw[Math.floor(.975*n)]],pPositive:draw.filter(x=>x>0).length/n};
 };
 for(const cost of costs){const get=id=>result[id+"__"+cost.name]._logs;
  boot[cost.name]={S2vsS1:comp(get("S2_2day_10pp_oneshot"),get("S1_2day_oneshot")),S3vsS1:comp(get("S3_3day_oneshot"),get("S1_2day_oneshot")),S1vsConstant:comp(get("S1_2day_oneshot"),get("fixedCash8_67pct"))};
 }
 const csvHead=["date","Top1","rawE",...variants.map(x=>x.name+"_E"),...variants.map(x=>x.name+"_NAV")],csv=[csvHead.join(",")];
 for(let i=0;i<rows.length;i++)csv.push([rows[i].d,rows[i].s,rows[i].E,...variants.map(x=>paths[x.name][i].E),...variants.map(x=>paths[x.name][i].nav)].join(","));
 const summary=Object.fromEntries(Object.entries(result).map(([key,{_logs,...rec}])=>[key,rec]));
 return {summary,boot,csv:csv.join("\n")+"\n"};
};
const result=simulateOneshot(fs.readFileSync(process.argv[2],"utf8"));
console.log(JSON.stringify({summary:result.summary,boot:result.boot},null,2));
