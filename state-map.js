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
function signedPct(v){const n=Number(v);return `${n>0?'+':''}${n.toFixed(1)}pp`}
function fmtScore(v){return Number(v).toFixed(3)}
function name(code){return `${code} ${NAMES[code]||''}`.trim()}
function mean(rows,key){return rows.reduce((s,r)=>s+Number(r[key]||0),0)/Math.max(rows.length,1)}

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

function renderPathAnalysis(history){
  const rows=history;
  const box=document.getElementById('pathAnalysis');
  if(rows.length<10){
    document.getElementById('pathDirection').textContent='历史样本不足';
    document.getElementById('pathSummary').textContent='至少需要 10 个交易日数据，才能稳定比较窗口两端状态。';
    box.classList.remove('loading');
    return;
  }

  const edge=Math.min(5,Math.floor(rows.length/2));
  const startRows=rows.slice(0,edge), endRows=rows.slice(-edge);
  const b0=mean(startRows,'breadth_pct'), b1=mean(endRows,'breadth_pct');
  const g0=mean(startRows,'gap_percentile'), g1=mean(endRows,'gap_percentile');
  const db=b1-b0, dg=g1-g0;
  const threshold=5;
  const sx=db>threshold?'right':db<-threshold?'left':'flat';
  const sy=dg>threshold?'up':dg<-threshold?'down':'flat';
  const latest=rows.at(-1);

  let title='状态大体稳定', summary='', implication='';
  if(sx==='right'&&sy==='up'){
    title='向右上：机会扩散 + 领导强化';
    summary='有效机会数量与 Top1 领先清晰度同时改善，市场结构正朝更有利于趋势竞争的方向移动。';
    implication='对 OLS 而言，这通常代表候选面变宽且领先者更容易拉开差距；可作为“竞争环境改善”的参考，但仍需由原策略规则决定持仓。';
  }else if(sx==='left'&&sy==='up'){
    title='向左上：机会收缩 + 领导强化';
    summary='有效机会在减少，但剩余资产中的领先者反而更清晰，市场更接近“少数主线集中”的结构。';
    implication='这类环境未必差，关键在于是否存在持续的强 Top1；组合会更依赖少数资产，分散度下降，应更关注主线寿命而非单看 Breadth。';
  }else if(sx==='right'&&sy==='down'){
    title='向右下：机会扩散 + 领导弱化';
    summary='更多资产进入竞争区，但 Top1 与 Top2 的优势差正在缩小，机会变多的同时排名竞争也更拥挤。';
    implication='对 OLS 而言，选择空间扩大但换帅风险上升；这更像“广泛轮动”而非单一趋势强化，V1 等竞争过滤的解释价值会提高。';
  }else if(sx==='left'&&sy==='down'){
    title='向左下：机会收缩 + 领导弱化';
    summary='有效机会数量与 Top1 领先清晰度同时恶化，市场正在从“可选机会”与“领导稳定性”两个方向收缩。';
    implication='这是对 Top1 轮动相对不友好的迁移方向之一：可竞争资产变少，同时剩余资产之间也缺乏明显领先者。它不等于市场必跌，但意味着 OLS 信号的结构性支撑正在减弱。';
  }else if(sx==='left'){
    title='向左：机会明显收缩';
    summary='Breadth 明显下降，而 Leadership Gap 没有出现同等级别的方向变化。';
    implication='当前主要变化来自“能参与竞争的资产变少”。需要继续观察剩余少数资产能否形成更清晰领导，否则容易进一步滑向防守 / 空窗状态。';
  }else if(sx==='right'){
    title='向右：机会明显扩散';
    summary='Breadth 明显改善，而 Leadership Gap 暂未同步形成强方向。';
    implication='候选机会正在增多，但尚不能仅据此判断 OLS 环境已经全面改善；下一步要看 Top1 是否开始稳定拉开差距。';
  }else if(sy==='up'){
    title='向上：领导清晰度提升';
    summary='Top1 相对 Top2 的优势正在扩大，而 Breadth 整体变化有限。';
    implication='这更像竞争结构改善而非机会面扩张。若当前仍处低 Breadth，可能演化为“狭窄主线”；若 Breadth 已高，则更接近趋势扩散。';
  }else if(sy==='down'){
    title='向下：领导清晰度下降';
    summary='Top1 与 Top2 的竞争正在重新变得接近，而有效机会数量整体变化不大。';
    implication='主要风险来自排名拥挤和潜在换帅，而不是机会数量本身。需要更关注 Score 差、Top1 寿命和 V1 过滤是否同步恶化。';
  }else{
    summary='所选窗口两端的 Breadth 与 Leadership Gap 变化都不足 5 个百分点，暂未形成明确迁移方向。';
    implication='当前更适合把注意力放在所在象限本身，而不是对短期轨迹做过度解释。';
  }

  const dist=Math.hypot(db,dg);
  const strength=dist>=35?'迁移强':dist>=18?'迁移中等':dist>=8?'迁移轻微':'基本稳定';

  document.getElementById('pathDirection').textContent=title;
  document.getElementById('pathDirection').style.color=COLORS[latest.quadrant]||'#edf3ff';
  document.getElementById('pathStrength').textContent=strength;
  document.getElementById('pathBreadthDelta').textContent=signedPct(db);
  document.getElementById('pathGapDelta').textContent=signedPct(dg);
  document.getElementById('pathBreadthRange').textContent=`前5日均值 ${pct(b0)} → 后5日均值 ${pct(b1)}`;
  document.getElementById('pathGapRange').textContent=`前5日均值 ${pct(g0)} → 后5日均值 ${pct(g1)}`;
  document.getElementById('pathSummary').textContent=`当前位于「${LABELS[latest.quadrant]||latest.quadrant}」。${summary}`;
  document.getElementById('pathImplication').textContent=implication;
  box.classList.remove('loading');
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

  const recent=history;
  if(recent.length){
    const d=recent.map((p,i)=>`${i?'L':'M'} ${X(p.breadth_pct)} ${Y(p.gap_percentile)}`).join(' ');
    svg.appendChild(el('path',{d,class:'state-path'}));
    // Visible arrowheads show chronological travel, even on backtracking paths.
    // Sample longer paths to keep the mobile plot readable.
    const segments=[];
    for(let i=1;i<recent.length;i++){
      const a=recent[i-1],b=recent[i];
      const x0=X(a.breadth_pct),y0=Y(a.gap_percentile);
      const x1=X(b.breadth_pct),y1=Y(b.gap_percentile);
      if(Math.hypot(x1-x0,y1-y0)>1.5)segments.push({x0,y0,x1,y1});
    }
    const step=Math.max(1,Math.ceil(segments.length/16));
    segments.forEach((s,i)=>{
      if(i%step!==0 && i!==segments.length-1)return;
      const dx=s.x1-s.x0,dy=s.y1-s.y0,dist=Math.hypot(dx,dy);
      const ux=dx/dist,uy=dy/dist;
      const mid=.64,tipX=s.x0+dx*mid,tipY=s.y0+dy*mid;
      const len=11,half=5.5;
      const backX=tipX-ux*len,backY=tipY-uy*len;
      const poly=el('path',{d:`M ${tipX} ${tipY} L ${backX-uy*half} ${backY+ux*half} L ${backX+uy*half} ${backY-ux*half} Z`,class:'state-arrow'});
      svg.appendChild(poly);
    });
  }

  recent.forEach((p,i)=>{
    const current=i===recent.length-1;
    if(current && p.date===window.__latestStateDate){
      svg.appendChild(el('circle',{cx:X(p.breadth_pct),cy:Y(p.gap_percentile),r:17,class:'current-ring'}));
      svg.appendChild(el('circle',{cx:X(p.breadth_pct),cy:Y(p.gap_percentile),r:25,class:'current-halo'}));
    }
    const c=el('circle',{cx:X(p.breadth_pct),cy:Y(p.gap_percentile),r:current?9:6,fill:COLORS[p.quadrant]||'#4cc9f0',class:`state-point ${current?'current':'old'}`});
    c.addEventListener('mouseenter',e=>showTip(e,p));
    c.addEventListener('mousemove',e=>showTip(e,p));
    c.addEventListener('mouseleave',()=>tip.style.display='none');
    c.addEventListener('click',e=>showTip(e,p,true));
    svg.appendChild(c);
  });

  // Start and end markers are based on the selected date window, not the entire archive.
  // Draw last so they remain visible over overlapping historical points.
  const first=recent[0],last=recent[recent.length-1];
  if(first && last){
    const sx=X(first.breadth_pct),sy=Y(first.gap_percentile);
    const ex=X(last.breadth_pct),ey=Y(last.gap_percentile);
    const overlap=recent.length>1 && Math.hypot(sx-ex,sy-ey)<32;
    // Separate coincident start/end markers with a short leader line.
    const mx=overlap?sx-25:sx,my=overlap?sy+22:sy;
    if(overlap)svg.appendChild(el('line',{x1:sx,y1:sy,x2:mx,y2:my,class:'start-leader'}));
    const start=el('path',{d:`M ${mx} ${my-12} L ${mx+12} ${my} L ${mx} ${my+12} L ${mx-12} ${my} Z`,class:'start-diamond'});
    svg.appendChild(start);
    const startLabel=el('text',{
      x:Math.min(W-pad.r-66,Math.max(pad.l+66,mx)),
      y:my<pad.t+34?my+33:my-20,
      'text-anchor':'middle',class:'state-endpoint-label start-label'
    });
    startLabel.textContent=`起点 ${first.date.slice(5)}`;
    svg.appendChild(startLabel);
    if(recent.length>1){
      const endLabel=el('text',{
        x:Math.min(W-pad.r-66,Math.max(pad.l+66,ex)),
        y:ey<pad.t+34?ey+38:ey-24,
        'text-anchor':'middle',class:'state-endpoint-label end-label'
      });
      endLabel.textContent=`终点 ${last.date.slice(5)}`;
      svg.appendChild(endLabel);
    }
  }

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
  const rows=history; if(!rows.length)return;
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

// Render the selected historical window consistently across the map and both mini charts.
loadData().then(({latest,history})=>{
  window.__latestStateDate=latest.date;
  const sorted=history.slice().sort((a,b)=>a.date.localeCompare(b.date));
  const presets=document.querySelectorAll('[data-range]');
  const from=document.getElementById('rangeStart');
  const to=document.getElementById('rangeEnd');
  const caption=document.getElementById('rangeSummary');
  const latestDate=sorted.at(-1)?.date || latest.date;
  if(!sorted.length)throw new Error('No history records');
  from.min=to.min=sorted[0].date;
  from.max=to.max=latestDate;
  to.value=latestDate;
  let mode='20';

  function draw(){
    let rows;
    if(mode==='custom'){
      if(from.value && to.value && from.value>to.value){
        caption.textContent='开始日期不能晚于结束日期';return;
      }
      rows=sorted.filter(p=>(!from.value||p.date>=from.value)&&(!to.value||p.date<=to.value));
    }else{
      rows=mode==='all'?sorted:sorted.slice(-Number(mode));
    }
    if(!rows.length){
      caption.textContent='此日期范围没有可用交易日数据';return;
    }
    const selected=rows.at(-1);
    caption.textContent=`${rows[0].date} → ${selected.date} · ${rows.length} 个交易日${selected.date===latestDate?' · 末点为最新收盘':' · 末点为所选结束日'}`;
    document.getElementById('pathRangeTitle').textContent=`所选 ${rows.length} 个交易日状态解读`;
    renderMap(rows);
    renderPathAnalysis(rows);
    renderLine('breadthLine',rows,'breadth_pct');
    renderLine('gapLine',rows,'gap_percentile');
    presets.forEach(btn=>btn.setAttribute('aria-pressed',String(btn.dataset.range===mode)));
  }
  presets.forEach(btn=>btn.addEventListener('click',()=>{
    mode=btn.dataset.range;
    if(mode!=='custom'){
      const rows=mode==='all'?sorted:sorted.slice(-Number(mode));
      from.value=rows[0].date;to.value=latestDate;
    }
    draw();
  }));
  [from,to].forEach(input=>input.addEventListener('change',()=>{
    mode='custom';draw();
  }));
  renderCards(latest);
  draw();
}).catch(err=>{
  console.error(err);
  document.getElementById('latestRegime').textContent='数据读取失败';
  document.getElementById('latestDate').textContent='请检查 state JSON / Vercel 部署';
});
