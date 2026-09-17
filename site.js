const assets=[
{code:'159934',name:'黄金ETF易方达',role:'GOLD',group:'商品',desc:'黄金现货暴露 · Stage8L 替换 518880',status:'正式'},
{code:'159985',name:'豆粕ETF',role:'SOYMEAL',group:'商品',desc:'农产品商品暴露',status:'正式'},
{code:'161226',name:'白银LOF',role:'SILVER',group:'商品',desc:'贵金属高弹性暴露',status:'正式'},
{code:'513100',name:'纳指ETF',role:'NASDAQ100',group:'海外',desc:'美国大型科技成长',status:'正式'},
{code:'159957',name:'创业板ETF华夏',role:'CHINEXT',group:'A股',desc:'A股成长 · Stage8L 替换 159915',status:'正式'},
{code:'159509',name:'纳指科技ETF',role:'NASDAQ TECH',group:'海外',desc:'美国科技强化暴露',status:'正式'},
{code:'513290',name:'纳指生物科技ETF',role:'US BIOTECH',group:'海外',desc:'美国生物科技',status:'正式'},
{code:'159529',name:'标普消费ETF景顺',role:'US CONSUMER',group:'海外',desc:'美国消费行业',status:'正式'},
{code:'159981',name:'能源化工ETF',role:'ENERGY-CHEM',group:'商品',desc:'国内商品周期 · 保留休眠机会',status:'观察'},
{code:'501018',name:'原油LOF',role:'CRUDE OIL',group:'商品',desc:'原油周期暴露',status:'正式'},
{code:'513530',name:'港股通红利ETF华泰柏瑞',role:'HK DIVIDEND',group:'港股',desc:'港股高股息 · 替换 513920',status:'正式'},
{code:'511380',name:'可转债ETF',role:'CONVERTIBLE',group:'A股',desc:'可转债混合风险暴露',status:'正式'},
{code:'164824',name:'印度基金LOF',role:'INDIA',group:'海外',desc:'印度权益 · 当前保留观察',status:'观察'},
{code:'511220',name:'城投债ETF',role:'CASH',group:'现金',desc:'现金比较器 / 风险关闭状态',status:'基准',cash:true}
];

const annual=[
['2015',2.99],['2016',10.68],['2017',2.10],['2018',11.23],['2019',27.54],['2020',60.05],['2021',34.93],['2022',23.87],['2023',21.31],['2024',65.57],['2025',115.42],['2026*',134.99]
];
const contrib=[
['白银',29.4],['纳指100',17.8],['原油',15.7],['创业板',10.8],['纳指科技',10.7],['能源化工',5.2],['港股红利',4.0],['豆粕',3.8],['黄金',3.1],['标普消费',2.5],['生物科技',1.5],['可转债',-0.4],['印度',-3.6]
];

function setupNavigation(){
  document.querySelectorAll('nav span').forEach(node=>{
    if(node.textContent.trim()==='Strategy'){
      const a=document.createElement('a');a.href='./strategy.html';a.textContent='Strategy';node.replaceWith(a);
    }
  });
  const nav=document.querySelector('.topbar nav');
  if(nav && !nav.querySelector('a[href="./live.html"]')){
    const a=document.createElement('a');a.href='./live.html';a.textContent='Live';nav.appendChild(a);
  }
}

function setupSnapshotBadge(){
  const hero=document.querySelector('.hero');
  if(!hero || hero.querySelector('.snapshot-badge')) return;
  const badge=document.createElement('div');
  badge.className='snapshot-badge';
  badge.innerHTML='<span class="pulse-dot"></span><span>STATIC SNAPSHOT</span><small>浏览器端交互 · 无实时计算</small>';
  const anchor=hero.querySelector('.eyebrow');
  if(anchor) anchor.insertAdjacentElement('afterend',badge);
}

function renderAssets(filter='全部'){
  const grid=document.getElementById('assetGrid');
  if(!grid) return;
  const list=filter==='全部'?assets:assets.filter(a=>a.group===filter);
  grid.innerHTML=list.map((a,i)=>`<button type="button" class="asset ${a.cash?'cash':''}" data-code="${a.code}" style="--delay:${i*28}ms" aria-label="查看 ${a.code} ${a.name} 详情"><div class="top"><code>${a.code}</code><span class="role">${a.role}</span></div><div class="asset-meta"><span>${a.group}</span><span>${a.status}</span></div><h3>${a.name}</h3><p>${a.desc}</p><span class="asset-open">查看角色 →</span></button>`).join('');
  grid.querySelectorAll('.asset').forEach(card=>card.addEventListener('click',()=>selectAsset(card.dataset.code)));
}

function setupAssetExplorer(){
  const grid=document.getElementById('assetGrid');
  if(!grid) return;
  const groups=['全部','海外','商品','A股','港股','现金'];
  const controls=document.createElement('div');
  controls.className='asset-controls';
  controls.innerHTML=`<div class="filter-pills" role="group" aria-label="按资产类别筛选">${groups.map((g,i)=>`<button type="button" class="filter-pill ${i===0?'active':''}" data-filter="${g}">${g}</button>`).join('')}</div><span class="asset-count">${assets.length} 个角色</span>`;
  grid.before(controls);
  const detail=document.createElement('aside');
  detail.className='asset-detail';detail.id='assetDetail';detail.setAttribute('aria-live','polite');detail.hidden=true;
  grid.after(detail);
  controls.querySelectorAll('.filter-pill').forEach(btn=>btn.addEventListener('click',()=>{
    controls.querySelectorAll('.filter-pill').forEach(b=>b.classList.toggle('active',b===btn));
    renderAssets(btn.dataset.filter);
    controls.querySelector('.asset-count').textContent=`${btn.dataset.filter==='全部'?assets.length:assets.filter(a=>a.group===btn.dataset.filter).length} 个角色`;
    detail.hidden=true;
  }));
  renderAssets();
}

function selectAsset(code){
  const a=assets.find(x=>x.code===code);const detail=document.getElementById('assetDetail');if(!a||!detail)return;
  document.querySelectorAll('.asset').forEach(card=>card.classList.toggle('selected',card.dataset.code===code));
  detail.hidden=false;
  detail.innerHTML=`<div><small>${a.group} · ${a.status}</small><strong>${a.code} · ${a.name}</strong><p>${a.desc}</p></div><div class="detail-role"><span>经济角色</span><b>${a.role}</b></div><button type="button" class="detail-close" aria-label="关闭详情">×</button>`;
  detail.querySelector('.detail-close').addEventListener('click',()=>{detail.hidden=true;document.querySelectorAll('.asset').forEach(card=>card.classList.remove('selected'));});
}

function renderAnnual(){
  const el=document.getElementById('annualChart');if(!el)return;
  const maxAnnual=Math.max(...annual.map(x=>x[1]));
  el.innerHTML=annual.map(([y,v],i)=>`<button type="button" class="bar-col" data-year="${y}" data-value="${v.toFixed(2)}%" aria-label="${y} 年收益 ${v.toFixed(2)}%"><div class="bar" style="height:${Math.max(4,v/maxAnnual*220)}px;--delay:${i*35}ms"><span>${v.toFixed(1)}%</span></div><label>${y}</label></button>`).join('');
  const readout=document.createElement('div');readout.className='chart-readout';readout.innerHTML='<span>点击柱子查看</span><b>年度收益</b>';el.after(readout);
  el.querySelectorAll('.bar-col').forEach(btn=>btn.addEventListener('click',()=>{
    el.querySelectorAll('.bar-col').forEach(x=>x.classList.toggle('selected',x===btn));
    readout.innerHTML=`<span>${btn.dataset.year}</span><b>${btn.dataset.value}</b>`;
  }));
}

function renderContrib(){
  const el=document.getElementById('contribChart');if(!el)return;
  const maxAbs=Math.max(...contrib.map(x=>Math.abs(x[1])));
  el.innerHTML=contrib.map(([n,v],i)=>`<button type="button" class="hrow" data-name="${n}" data-value="${v>0?'+':''}${v.toFixed(1)}%"><label>${n}</label><div class="htrack"><div class="hfill ${v<0?'neg':''}" style="width:${Math.abs(v)/maxAbs*100}%;--delay:${i*28}ms"></div></div><span>${v>0?'+':''}${v.toFixed(1)}%</span></button>`).join('');
  el.querySelectorAll('.hrow').forEach(btn=>btn.addEventListener('click',()=>{
    el.querySelectorAll('.hrow').forEach(x=>x.classList.toggle('selected',x===btn));
  }));
}

function setupReveal(){
  const nodes=[...document.querySelectorAll('.section > *:not(.section-head), .hero-metrics > div')];
  if(!('IntersectionObserver' in window)){nodes.forEach(n=>n.classList.add('revealed'));return;}
  nodes.forEach(n=>n.classList.add('reveal-item'));
  const observer=new IntersectionObserver(entries=>entries.forEach(e=>{if(e.isIntersecting){e.target.classList.add('revealed');observer.unobserve(e.target);}}),{threshold:.08,rootMargin:'0px 0px -24px'});
  nodes.forEach(n=>observer.observe(n));
}

function setupMetricTilt(){
  if(!matchMedia('(hover:hover) and (pointer:fine)').matches)return;
  document.querySelectorAll('.hero-metrics>div,.stats-row>div,.evidence-card').forEach(card=>{
    card.addEventListener('pointermove',e=>{const r=card.getBoundingClientRect();card.style.setProperty('--mx',`${e.clientX-r.left}px`);card.style.setProperty('--my',`${e.clientY-r.top}px`);});
  });
}

setupNavigation();
setupSnapshotBadge();
setupAssetExplorer();
renderAnnual();
renderContrib();
setupReveal();
setupMetricTilt();
