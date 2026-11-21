import fs from "node:fs";
// node q10_recent_minute_execution.mjs <q10_daily.csv> <formal_void_path.csv> <checkpoint_minute.csv> <live-forward.json>
const recentMinuteExecution=function recentMinuteExecution(inputs){
 const parse=s=>{const [h,...lines]=s.trim().split(/\r?\n/),k=h.split(",");return lines.map(l=>Object.fromEntries(l.split(",").map((v,i)=>[k[i],v])))};
 const hist=parse(inputs[0]),formal=new Map(parse(inputs[1]).map(r=>[r.date.replace(/-/g,""),r])),
 minute=new Map(parse(inputs[2]).map(r=>[r.date+"|"+r.symbol,r]));
 const live=JSON.parse(inputs[3]).series.baseline,liveMap=new Map(live.map(r=>[r.signal_date.replace(/-/g,""),r]));
 const records=hist.filter(d=>d.date>="20260914"&&d.date<="20261112").map(d=>{
  const f=formal.get(d.date),l=liveMap.get(d.date);
  if(!l)throw Error("missing live route "+d.date);
  const mTarget=l.target||null,archiveTarget=d.Void_target||null;
  if(mTarget!==archiveTarget&&d.date!=="20260929")throw Error("unexpected route discrepancy "+d.date);
  return {signal:d.date,execution:f.executionDate,asset:mTarget,void:d.Void_state==="DEFENSIVE_VOID",rawTop:d.Q90_raw_top,rawE:+d.Q90_E,
   matched:d.Void_state==="NON_VOID"?mTarget===d.Q90_raw_top:false,override:mTarget!==archiveTarget};
 });
 const modes=["baseline","daily5","s1_two_confirm_oneshot"],results={},streams={};
 const bank=20000,minLot=100,feeFn=amount=>Math.max(.0006*amount,5);
 const px=(date,sym)=>{const v=minute.get(date+"|"+sym);if(!v)throw Error("Missing minute "+date+" "+sym);return v;};
 const p=(r,key)=>{const v=+r[key];if(!(v>0))throw Error("bad minute price "+key);return v;};
 for(const mode of modes){
  let cash=bank,units=0,held=null,peak=bank,mdd=0,lowDate=null,confirm=0,prevVoid=false;
  let trades=0,tickets=0,fees=0,dayBlocked=0,gapBlocked=0,drawBlocked1400=0,drawBlocked1405=0,positiveQ90Days=0;
  const stream=[],audit=[];
  function sellAll(sym,at,reason){
   if(!held||!units)return;
   const price=p(px(at,held),"p1400"),notional=units*price,f=feeFn(notional);
   cash+=notional-f;fees+=f;tickets++;trades++;audit.push({date:at,signal:sig.signal,side:"SELL",asset:held,units,price,reason,fee:f});
   held=null;units=0;
  }
  function sellPartial(sym,at,targetW,reason){
   if(!held||held!==sym||units===0)return false;
   const atPrice=p(px(at,sym),"p1400"),v=cash+units*atPrice,target=targetW*v;
   let count=Math.floor(Math.max(0,units*atPrice-target)/atPrice/minLot)*minLot;count=Math.min(count,units);
   if(count<=0)return false;
   const notional=count*atPrice,f=feeFn(notional);
   units-=count;cash+=notional-f;fees+=f;tickets++;trades++;audit.push({date:at,signal:sig.signal,side:"SELL",asset:sym,units:count,price:atPrice,reason,fee:f});
   if(!units)held=null;return true;
  }
  function buyToWeight(sym,at,weight,reason){
   const data=px(at,sym),price=p(data,"p1405"),assetV=held===sym?units*price:0,nav=cash+assetV;
   const desired=weight*nav,need=Math.max(0,desired-assetV);
   let count=Math.floor(need/price/minLot)*minLot;
   while(count>0&&count*price+feeFn(count*price)>cash+1e-8)count-=minLot;
   if(count<=0)return false;
   const notional=count*price,f=feeFn(notional);
   cash-=notional+f;units+=count;held=sym;fees+=f;tickets++;trades++;
   audit.push({date:at,signal:sig.signal,side:"BUY",asset:sym,units:count,price,reason,fee:f});
   return true;
  }
  let sig=null;
  for(const r of records){
   sig=r;
   const at=r.execution,preHeld=held,preUnits=units,entry=r.void&&!prevVoid,exit=!r.void&&prevVoid;
   let action="HOLD",targetWeight=null,doTrade=false,shouldBuy=false,needsNew=held!==r.asset,reason=null;
   const fromAsset=held,oldClose=fromAsset? p(px(at,fromAsset),"p1400"):0;
   const nav1400=cash+(held?units*oldClose:0);
   if(entry||exit)confirm=0;
   if(r.void){
    if(needsNew){action="FORMAL_VOID_ROUTE";targetWeight=r.asset?1:0;doTrade=true;}
    else action="VOID_FREEZE_SHARES";
   }else if(!r.asset){
    if(held){action="FORMAL_CASH";targetWeight=0;doTrade=true;}
    confirm=0;
   }else if(mode==="baseline"||r.asset!==r.rawTop){
    if(needsNew){action="FORMAL_TARGET";targetWeight=1;doTrade=true;}else action="NO_Q90_PRESERVE";
    confirm=0;
   }else {
    const wantedE=r.rawE>=.05?r.rawE:0,preE=1-(held===r.asset?units*oldClose/nav1400:0);
    if(wantedE>.05)positiveQ90Days++;
    if(needsNew){action="Q90_NEW_ETF";targetWeight=1-wantedE;doTrade=true;confirm=0;}
    else if(mode==="daily5"){
     if(Math.abs(wantedE-preE)>=.05-1e-12){targetWeight=1-wantedE;action=wantedE>preE?"Q90_REDUCE":"Q90_RESTORE";doTrade=true;}
    }else if(mode==="s1_two_confirm_oneshot"){
     if(wantedE>=preE+.05-1e-12){targetWeight=1-wantedE;action="Q90_REDUCE";doTrade=true;confirm=0;}
     else if(wantedE<=preE-.05+1e-12){confirm++;if(confirm>=2){targetWeight=1-wantedE;action="Q90_RESTORE";doTrade=true;confirm=0;}else action="WAIT_Q90_RELIEF";}
     else confirm=0;
    }
   }
   if(doTrade){
    let targetBlocked=false,blockedAt="",blockWhy="";
    if(r.asset && (needsNew||targetWeight>(held===r.asset?units*oldClose/nav1400:0))){
     const current=px(at,r.asset),prev=px(r.signal.slice(0,4)+"-"+r.signal.slice(4,6)+"-"+r.signal.slice(6),r.asset),
       gap=p(current,"p0931")/p(prev,"lastClose");
     const precheck=1-p(current,"p1400")/p(current,"highTo1400");
     if(gap<.97-1e-12){targetBlocked=true;blockedAt="0931";blockWhy="GAP";gapBlocked++;}
     else if(needsNew&&precheck>=.02-1e-12){targetBlocked=true;blockedAt="1400";blockWhy="DRAWDOWN";drawBlocked1400++;}
    }
    if(targetBlocked&&needsNew){
     action="VETO_NEW_BUY_HOLD_PREVIOUS";dayBlocked++;doTrade=false;confirm=0;
    }else{
     if(needsNew&&held)sellAll(held,at,"FORMAL_SWITCH");
     if(!r.asset){action="FORMAL_CASH";}else {
      const w=targetWeight;
      if(held===r.asset){
       const nowV=units*p(px(at,r.asset),"p1400"),nowNAV=cash+nowV;
       if(w<nowV/nowNAV-1e-8)sellPartial(r.asset,at,w,action);
      }
      const currentValue=held===r.asset?units*p(px(at,r.asset),"p1405"):0;
      const nowNAV=cash+currentValue;
      if(w>currentValue/nowNAV+1e-7){
       const data=px(at,r.asset),gap=p(data,"p0931")/p(px(r.signal.slice(0,4)+"-"+r.signal.slice(4,6)+"-"+r.signal.slice(6),r.asset),"lastClose"),
        dd=1-p(data,"p1405")/p(data,"highTo1405");
       if(gap<.97-1e-12){action+="|NO_BUY_GAP";gapBlocked++;dayBlocked++;}
       else if(dd>=.02-1e-12){action+="|NO_BUY_DRAWDOWN";drawBlocked1405++;dayBlocked++;}
       else buyToWeight(r.asset,at,w,action);
      }
     }
    }
   }
   if(r.void&&r.asset===fromAsset&&units!==preUnits)throw Error("Void shares altered on "+r.signal+" "+mode);
   if(held && held!==r.asset&&!(action==="VETO_NEW_BUY_HOLD_PREVIOUS"))throw Error("Wrong holding "+at+" got "+held+" want "+r.asset);
   const close=held?p(px(at,held),"lastClose"):0;
   const nav=cash+units*close;
   if(nav>peak)peak=nav;
   if(nav/peak-1<mdd){mdd=nav/peak-1;lowDate=at;}
   stream.push({signal:r.signal,execution:at,asset:r.asset,held,void:r.void,override:r.override,
    action,nav,units,cash,weight:held?units*close/nav:0,cashWeight:cash/nav,feeTotal:fees,orders:tickets,
    gapBlockCount:gapBlocked,dd1400Count:drawBlocked1400,dd1405Count:drawBlocked1405});
   prevVoid=r.void;
  }
  const final=stream.at(-1).nav,ret=final/bank-1;
  results[mode]={totalReturn:ret,NAV:final,mdd,lowDate,fees,tickets,tradeActions:trades,buyVetoDays:dayBlocked,gapBlocked,drawBlocked1400,drawBlocked1405,positiveQ90Days,
    bought:audit.filter(x=>x.side==="BUY").length,sold:audit.filter(x=>x.side==="SELL").length,
    lastAsset:held,lastCashWeight:cash/final};
  streams[mode]={stream,audit};
 }
 const output={
  period:{firstSignal:records[0].signal,lastSignal:records.at(-1).signal,firstExecution:records[0].execution,lastExecution:records.at(-1).execution,
   signals:records.length,assetUniverse:[...new Set(records.map(x=>x.asset))],liveOverrideDates:records.filter(x=>x.override).map(x=>x.signal),
   model:"Initial cash ¥20,000, trade at 14:00 sell/14:05 buy checkpoint minute prices; 100-share lots, each side max(0.06%, ¥5), preflight 09:31 gap and minute 14:00/14:05 high drawdown ≥2%; only PIT-known Void/V1 routes, no historical premium PIT veto because NAV first_seen backfilled; trailing 1-minute last close MTM"},
  results};
 const csv=["signal,execution,formalTarget,void,override,baseline_NAV,daily_NAV,s1_NAV,baseline_act,daily_act,s1_act,daily_weight,daily_cash,s1_weight,s1_cash",
 ...records.map((r,i)=>[r.signal,r.execution,r.asset,+r.void,+r.override,
 streams.baseline.stream[i].nav,streams.daily5.stream[i].nav,streams.s1_two_confirm_oneshot.stream[i].nav,
 streams.baseline.stream[i].action,streams.daily5.stream[i].action,streams.s1_two_confirm_oneshot.stream[i].action,
 streams.daily5.stream[i].weight,streams.daily5.stream[i].cashWeight,streams.s1_two_confirm_oneshot.stream[i].weight,streams.s1_two_confirm_oneshot.stream[i].cashWeight
 ].join(","))].join("\n")+"\n";
 return {output,csv,streams};
};
const files=process.argv.slice(2);if(files.length!==4)throw Error("expected q10 daily, formal path, minute checkpoints, live-forward json");
const out=recentMinuteExecution(files.map(f=>fs.readFileSync(f,"utf8")));
console.log(JSON.stringify(out.output,null,2));
