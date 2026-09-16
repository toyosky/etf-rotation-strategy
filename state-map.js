const LABELS={
  TREND_EXPANSION:'趋势扩散',
  ROTATION_CROWDING:'拥挤轮动',
  NARROW_LEADERSHIP:'狭窄主线',
  DEFENSIVE_VOID:'防守 / 空窗'
};
const COLORS={
  TREND_EXPANSION:'#54d6a5',
  ROTATION_CROWDING:'#4cc9f0',
  NARROW_LEADERSHIP:'#e9bf67',
  DEFENSIVE_VOID:'#ff7a8a'
};
const NAMES={
  '159934':'黄金','159985':'豆粕','161226':'白银','513100':'纳指100','159957':'创业板',
  '159509':'纳指科技','513290':'纳指生物','159529':'标普消费','159981':'能源化工',
  '501018':'原油','513530':'港股红利','511380':'可转债','164824':'印度','511220':'现金'
};

const svgNS='http://www.w3.org/2000/svg';
function el(tag,attrs={}){const x=document.createElementNS(svgNS,tag);Object.entries(attrs).forEach(([k,v])=>x.setAttribute(k,v));return x}
function pct(v){return `${Number(v).toFixed(1)}%`}
function fmtScore(v){return Number(v).toFixed(3)}
function name(code){return `${code} ${NAMES[code]||''}`.trim()}

async function loadData(){
  const stamp=Date.now();
  const [latest,history]=await Promise.all([
    fetch(`./data/state-map-latest.json?v=${stamp}`).then(r=>{if(!r.ok)throw new Error('latest');return r.json()}),
    fetch(`./data/state-map-history.json?v=${stamp}`).then(r=>{if(!r.ok)throw new Error('history');return r.json()})
  ]);
  return {latest,history};
}

function renderCards(s){
  document.getElementById('latestRegime').textContent=LABELS[s.quadrant]||s.quadrant;
  document.getElementById('latestRegime').style.color=COLORS[s.quadrant]||'#edf3ff';
  document.getElementById('latestDate').textContent=`${s.date} · 收盘状态`;
  document.getElementById('latestBreadth').textContent=pct(s.breadth_pct);
  document.getElementById('latestBreadthCount').textContent=`${s.breadth_count} / ${s.breadth_total} 个风险资产高于现金`;
  document.getElementById('latestGapPct').textContent=`${pct(s.gap_percentile)} 分位`;
  document.getElementById('latestGapRaw').textContent=`Raw gap ${fmtScore(s.gap_raw)}`;
  document.getElementById('latestTop1').textContent=name(s.top1);
  document.getElementById('latestTop2').textContent=`Top2 ${name(s.top2)} · 差 ${fmtScore(s.gap_raw)}`;
  document.getElementById('latestCards').classList.remove('loading');
}

function renderMap(history){
  const svg=document.getElementById('stateMap');
  const tip=document.getElementById('mapTooltip');
  svg.innerHTML='';
  const W=1000,H=620,pad={l:74,r:48,t:58,b:64};
  const iw=W-pad.l-pad.r, ih=H-pad.t-pad.b;
  const X=v=>pad.l+(Number(v)/100)*iw;
  const Y=v=>pad.t+(1-Number(v)/100)*ih;

  [0,25,50,75,100].forEach(v=>{
    const vx=X(v),vy=Y(v);
    svg.appendChild(el('line',{x1:vx,y1:pad.t,x2:vx,y2:H-pad.b,class:v===50?'svg-mid':'svg-grid'}));
    svg.appendChild(el('line',{x1:pad.l,y1:vy,x2:W-pad.r,y2:vy,class:v===50?'svg-mid':'svg-grid'}));
    const tx=el('text',{x:vx,y:H-28,'text-anchor':'middle',class:'svg-axis-label'});tx.textContent=v;svg.appendChild(tx);
    const ty=el('text',{x:38,y:vy+6,'text-anchor':'middle',class:'svg-axis-label'});ty.textContent=v;svg.appendChild(ty);
  });
  const ylabel=el('text',{x:22,y:H/2,transform:`rotate(-90 22 ${H/2})`,'text-anchor':'middle',class:'svg-axis-label'});ylabel.textContent='Leadership Gap percentile';svg.appendChild(ylabel);

  const recent=history.slice(-20);
  if(recent.length){
    const d=recent.map((p,i)=>`${i?'L':'M'} ${X(p.breadth_pct)} ${Y(p.gap_percentile)}`).join(' ');
    svg.appendChild(el('path',{d,class:'state-path'}));
  }

  recent.forEach((p,i)=>{
    const current=i===recent.length-1;
    if(current)svg.appendChild(el('circle',{cx:X(p.breadth_pct),cy:Y(p.gap_percentile),r:17,class:'current-ring'}));
    const c=el('circle',{cx:X(p.breadth_pct),cy:Y(p.gap_percentile),r:current?9:6,fill:COLORS[p.quadrant]||'#4cc9f0',class:`state-point ${current?'current':'old'}`});
    c.addEventListener('mouseenter',e=>showTip(e,p));
    c.addEventListener('mousemove',e=>showTip(e,p));
    c.addEventListener('mouseleave',()=>tip.style.display='none');
    c.addEventListener('click',e=>showTip(e,p,true));
    svg.appendChild(c);
  });

  function showTip(e,p,persist=false){
    tip.innerHTML=`<b>${p.date} · ${LABELS[p.quadrant]||p.quadrant}</b><span>Breadth ${pct(p.breadth_pct)} (${p.breadth_count}/${p.breadth_total})</span><span>Gap ${pct(p.gap_percentile)} 分位 · raw ${fmtScore(p.gap_raw)}</span><span>Top1 ${name(p.top1)}</span><span>Top2 ${name(p.top2)}</span>`;
    tip.style.display='block';
    const rect=document.querySelector('.map-card').getBoundingClientRect();
    const clientX=e.clientX||rect.left+X(p.breadth_pct)/1000*rect.width;
    const clientY=e.clientY||rect.top+Y(p.gap_percentile)/620*rect.height;
    tip.style.left=`${Math.min(rect.width-190,Math.max(8,clientX-rect.left+12))}px`;
    tip.style.top=`${Math.min(rect.height-130,Math.max(8,clientY-rect.top-20))}px`;
    if(persist)setTimeout(()=>tip.style.display='none',3500);
  }
}

function renderLine(svgId,history,key,threshold=50,valueLabel=v=>pct(v)){
  const svg=document.getElementById(svgId);svg.innerHTML='';
  const rows=history.slice(-60); if(!rows.length)return;
  const W=760,H=260,p={l:42,r:20,t:24,b:34},iw=W-p.l-p.r,ih=H-p.t-p.b;
  const X=i=>p.l+(rows.length===1?0:i/(rows.length-1))*iw;
  const Y=v=>p.t+(1-Number(v)/100)*ih;
  [0,50,100].forEach(v=>{
    svg.appendChild(el('line',{x1:p.l,y1:Y(v),x2:W-p.r,y2:Y(v),class:v===threshold?'line-threshold':'line-grid'}));
    const t=el('text',{x:10,y:Y(v)+5,class:'mini-label'});t.textContent=v;svg.appendChild(t);
  });
  const pts=rows.map((r,i)=>[X(i),Y(r[key])]);
  const line=pts.map(([x,y],i)=>`${i?'L':'M'} ${x} ${y}`).join(' ');
  const area=`M ${pts[0][0]} ${H-p.b} `+pts.map(([x,y])=>`L ${x} ${y}`).join(' ')+` L ${pts.at(-1)[0]} ${H-p.b} Z`;
  svg.appendChild(el('path',{d:area,class:'mini-area'}));
  svg.appendChild(el('path',{d:line,class:'mini-line'}));
  const last=pts.at(-1);svg.appendChild(el('circle',{cx:last[0],cy:last[1],r:6,class:'mini-last'}));
  const val=el('text',{x:W-p.r,y:18,'text-anchor':'end',class:'mini-value'});val.textContent=valueLabel(rows.at(-1)[key]);svg.appendChild(val);
  const l=el('text',{x:p.l,y:H-8,class:'mini-label'});l.textContent=rows[0].date.slice(5);svg.appendChild(l);
  const r=el('text',{x:W-p.r,y:H-8,'text-anchor':'end',class:'mini-label'});r.textContent=rows.at(-1).date.slice(5);svg.appendChild(r);
}

loadData().then(({latest,history})=>{
  renderCards(latest);
  renderMap(history);
  renderLine('breadthLine',history,'breadth_pct');
  renderLine('gapLine',history,'gap_percentile');
}).catch(err=>{
  console.error(err);
  document.getElementById('latestRegime').textContent='数据读取失败';
  document.getElementById('latestDate').textContent='请检查 state JSON / Vercel 部署';
});
