import fs from "node:fs";
const correctedLock5=function correctedLock5(input){
 const parse=s=>{const [h,...ls]=s.trim().split(/\r?\n/),names=h.split(",");return ls.map(line=>Object.fromEntries(line.split(",").map((v,i)=>[names[i],v])))};
 const Q=new Map(parse(input[1]).map(x=>[x.d,x]));
 const d=parse(input[0]).filter(x=>Q.has(x.date.replaceAll("-","")));
 let nav=1,peak=1,mdd=0,holding={},prevSymbol=null,until=-1,lockedSymbol=null,entryE=0,feeSum=0,turnSum=0,tickets=0,actions=0;
 const years={},path=[];
 for(let i=0;i<d.length;i++){
  const v=d[i],date=v.date.replaceAll("-",""),q=Q.get(date),sym=v.target,eligible=sym&&sym!=="511220"&&sym!=="513500"&&sym===q.s;
  const raw=q.s?Math.max(0,Math.min(1,(1-1.1*(+q.Dbase)/(+q.D))*Math.max(0,Math.min(1.8,1+2*((+q.pLoss5_full)-(+q.pLoss5_vol)))))):0;
  const ret=v.missing==="1"&&q.s===sym?+q.ret:+v.gross;
  let recheck=false;
  if(!eligible){
   until=-1;entryE=0;lockedSymbol=null;recheck=true;
  }else if(i>until||lockedSymbol!==sym){
   entryE=raw>1e-5?raw:0;
   until=entryE>1e-5?i+4:-1;lockedSymbol=sym;
   recheck=true;
  }
  // Apply active E by setting target at entry and after lock expiry only.
  // If same asset and holding still an active 5-day episode, simply keep risk/cash weights drifted.
  const target={};
  if(sym){if(recheck||sym!==prevSymbol)target[sym]=1-entryE;else for(const [k,w] of Object.entries(holding))target[k]=w;}
  let fee=0,turn=0,nTickets=0;
  for(const key of new Set([...Object.keys(holding),...Object.keys(target)])){
   const delta=Math.abs((target[key]||0)-(holding[key]||0));
   if(delta<1e-10)continue;
   fee+=.0006*delta;turn+=delta;nTickets++;
  }
  const cashWeight=Math.max(0,1-Object.values(target).reduce((a,b)=>a+b,0)),realizedE=eligible?cashWeight:0;
  const rGross=(target[sym]||0)*ret,old=nav;
  nav*=1+rGross-fee;peak=Math.max(peak,nav);mdd=Math.min(mdd,nav/peak-1);
  const year=date.slice(0,4),yr=years[year]??(years[year]={start:old,end:nav,peak:old,mdd:0,tickets:0,fees:0});
  yr.end=nav;yr.peak=Math.max(yr.peak,nav);yr.mdd=Math.min(yr.mdd,nav/yr.peak-1);yr.tickets+=nTickets;yr.fees+=fee;
  feeSum+=fee;turnSum+=turn;tickets+=nTickets;actions+=+recheck;
  path.push({date,sym,eligible,raw,E:realizedE,nav,fee,tickets:nTickets,episodeEnd:until});
  // price drift, no hidden extra rebalance
  holding=sym?(target[sym]>1e-12?{[sym]:target[sym]*(1+ret)/(1+rGross)}:{}):{};prevSymbol=sym;
 }
 return {stats:{cagr244:nav**(244/d.length)-1,cagr252:nav**(252/d.length)-1,nav,mdd,tickets,feeSum,turnSum,years:Object.fromEntries(Object.entries(years).map(([y,r])=>[y,{return:r.end/r.start-1,mdd:r.mdd,tickets:r.tickets}]))},path};
};
const args=process.argv.slice(2);if(args.length!==2)throw Error("expected Void historical route and Q90 predictions CSV");
console.log(JSON.stringify(correctedLock5(args.map(x=>fs.readFileSync(x,"utf8"))).stats,null,2));
