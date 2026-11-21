import fs from "node:fs";
// Usage: node q9_min_ticket_stress.mjs <q9_paths.csv> <Void_history.csv> <Q90_predictions.csv> <q9_primary_results.json>
const costStress=function costStress(inputs){
 const parse=s=>{const [h,...ls]=s.trim().split(/\r?\n/),kk=h.split(",");return ls.map(line=>Object.fromEntries(line.split(",").map((v,i)=>[kk[i],v])))};
 const P=parse(inputs[0]),V=new Map(parse(inputs[1]).map(z=>[z.date.replaceAll("-",""),z])),Q=new Map(parse(inputs[2]).map(x=>[x.d,x])),ref=JSON.parse(inputs[3]).primary;
 const strategies=[{name:"void",E:""},{name:"daily5",E:"daily_E"},{name:"s1",E:"s1_E"},{name:"lock5",E:"lock_E"}],costs=[{id:"base6bp",min:0,extra:0},{id:"min5yuan",min:5,extra:0},{id:"min5plus4bp",min:5,extra:.0004}],summaries={},validations={};
 for(const cost of costs)for(const spec of strategies){
  let nav=1,peak=1,dd=0,tickets=0,minTickets=0,turn=0,fees=0,nRebalances=0;let priorW={},prevRiskTarget=null;const annual={},rets=[];
  for(const r of P){
   const row=V.get(r.date),source=Q.get(r.date);if(!row||!source)throw Error("date alignment failed");
   const target=row.target;
   const repair=row.missing==="1"&&target===source.s;
   const gross=repair?+source.ret:+row.gross;
   const E=spec.E?+r[spec.E]:0;
   const want={},targetWeight=target?1-E:0;if(target&&targetWeight>1e-12)want[target]=targetWeight;
   let tradeDiff=0,fee=0,dayTicket=0;
   for(const sym of new Set([...Object.keys(priorW),...Object.keys(want)])){
    const delta=Math.abs((want[sym]||0)-(priorW[sym]||0));if(delta<1e-10)continue;
    const side=nav*20000*delta,base=.0006*side,tc=Math.max(base,cost.min)+cost.extra*side;
    fee+=tc/(nav*20000);tradeDiff+=delta;dayTicket++;if(base<cost.min)minTickets++;
   }
   if(dayTicket)nRebalances++;
   const preNav=nav;
   const rGross=target?gross*(1-E):0,fac=1+rGross-fee;if(fac<=0)throw Error("negative");
   nav*=fac;peak=Math.max(peak,nav);dd=Math.min(dd,nav/peak-1);
   tickets+=dayTicket;fees+=fee;turn+=tradeDiff;rets.push(Math.log(fac));
   const year=r.date.slice(0,4),y=annual[year]??(annual[year]={start:preNav,end:nav,peak:preNav,dd:0});
   y.end=nav;y.peak=Math.max(y.peak,nav);y.dd=Math.min(y.dd,nav/y.peak-1);
   // Drift to next signal opening; cash stays uninvested, weight error from fees second order.
   const next={};if(target&&1-E>1e-12)next[target]=(1-E)*(1+gross)/(1+rGross);
   priorW=next;prevRiskTarget=target;
  }
  const cagr=nav**(244/P.length)-1;
  summaries[`${spec.name}__${cost.id}`]={nav,cagr,mdd:dd,tickets,minTickets,daysWithETFOrders:nRebalances,turnover:turn,fees,annual:Object.fromEntries(Object.entries(annual).map(([y,v])=>[y,{ret:v.end/v.start-1,mdd:v.dd}]))};
  if(cost.id==="base6bp"){const x=ref.scenario[spec.name];validations[spec.name]={cagrDiff:cagr-x.cagr,mddDiff:dd-x.mdd,navDiff:nav-x.nav};}
 }
 return {period:{from:P[0].date,to:P[P.length-1].date,n:P.length},summaries,validations};
};
const inputs=process.argv.slice(2);if(inputs.length!==4)throw Error("Expected 4 local input files");
console.log(JSON.stringify(costStress(inputs.map(path=>fs.readFileSync(path,"utf8"))),null,2));
