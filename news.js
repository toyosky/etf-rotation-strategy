const START_MONTH='2026-09';
const SUPABASE_URL='https://gsyziuzezmmnvgdoazkg.supabase.co';
const SUPABASE_KEY='sb_publishable_8jFjtjpds8Bn6dwV5bPSOg_DMX8NfcZ';

function monthRange(start){
  const out=[]; const [sy,sm]=start.split('-').map(Number); const now=new Date();
  let y=sy,m=sm;
  const ey=now.getFullYear(), em=now.getMonth()+1;
  while(y<ey || (y===ey && m<=em)){ out.push(`${y}-${String(m).padStart(2,'0')}`); m++; if(m===13){m=1;y++;} }
  return out.reverse();
}
function nextMonth(month){
  let [y,m]=month.split('-').map(Number); m++; if(m===13){m=1;y++;}
  return `${y}-${String(m).padStart(2,'0')}`;
}
async function loadMonthFromSupabase(month){
  const start=`${month}-01`, end=`${nextMonth(month)}-01`;
  const url=`${SUPABASE_URL}/rest/v1/live_news_audits?select=payload&audit_date=gte.${start}&audit_date=lt.${end}&order=audit_date.desc`;
  const r=await fetch(url,{headers:{apikey:SUPABASE_KEY},cache:'no-store'});
  if(!r.ok) throw new Error(`Supabase ${r.status}`);
  const rows=await r.json();
  return rows.map(x=>x.payload).filter(Boolean);
}
async function loadMonthFromGitHub(month){
  const r=await fetch(`./data/live-news/${month}.jsonl?ts=${Date.now()}`,{cache:'no-store'});
  if(!r.ok) return [];
  const text=await r.text();
  return text.split(/\r?\n/).map(x=>x.trim()).filter(Boolean).map(line=>{try{return JSON.parse(line)}catch{return null}}).filter(Boolean);
}
async function loadMonth(month){
  try{return await loadMonthFromSupabase(month)}
  catch(err){console.warn('Supabase live-news unavailable; falling back to repository JSONL.',err); try{return await loadMonthFromGitHub(month)}catch{return []}}
}
function riskOf(r){
  const raw=String(r.risk_direction_current||r.shock_direction||r.risk_direction||'none').toLowerCase();
  if(raw.includes('negative')) return 'negative';
  if(raw.includes('positive')) return 'positive';
  return 'none';
}
function riskLabel(r){
  const raw=String(r.risk_direction_current||r.shock_direction||r.risk_direction||'none');
  const map={negative:'负面',negative_strengthened:'负面增强',strong_negative:'强负面',positive:'正面',positive_strengthened:'正面增强',strong_positive:'强正面',mixed:'混合',none:'无明显方向'};
  return map[raw]||raw;
}
function normalize(r){
  return {
    date:r.audit_date||r.execution_date||r.signal_date||'未知日期',
    symbol:r.target_symbol||r.symbol||'—',
    name:r.target_name||r.asset_name||'—',
    phase:r.phase||'legacy_audit',
    cutoff:r.information_cutoff||r.review_timestamp||'',
    risk:riskOf(r),
    riskLabel:riskLabel(r),
    analysis:r.composite_observation||r.analysis||r.underlying_market_observation||r.underlying_intraday_summary||r.notes||'暂无分析。',
    noNew:Boolean(r.no_new_information),
    hypothesis:r.hypothesis_tag||'',
    sources:Array.isArray(r.new_information)&&r.new_information.length?r.new_information:(Array.isArray(r.sources)?r.sources:[]),
    bullets:Array.isArray(r.new_information_summary)?r.new_information_summary:[],
    raw:r
  };
}
function esc(s){return String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))}
function sourceTitle(s){return s.source_title||s.headline||s.source_name||s.source||'来源'}
function sourceSummary(s){return s.factual_summary||s.summary||s.source_excerpt||''}
function sourceTime(s){return s.source_published_at||s.published_at||''}
function renderSource(s){
  const title=esc(sourceTitle(s)), summary=esc(sourceSummary(s)), time=esc(sourceTime(s)), url=s.source_url||'';
  return `<article class="news-item"><div class="news-item-top"><b>${url?`<a href="${esc(url)}" target="_blank" rel="noopener noreferrer">${title}</a>`:title}</b><time>${time}</time></div>${summary?`<p>${summary}</p>`:''}</article>`;
}
function render(records){
  const timeline=document.getElementById('newsTimeline');
  const target=document.getElementById('targetFilter').value;
  const filtered=records.filter(r=>!target || r.symbol===target).sort((a,b)=>String(b.date).localeCompare(String(a.date)));
  if(!filtered.length){timeline.innerHTML='<div class="empty">这个筛选条件下暂无记录。</div>';return}
  timeline.innerHTML=filtered.map(r=>{
    const sources=r.sources.length?r.sources.map(renderSource).join(''):r.bullets.map((x,i)=>`<article class="news-item"><div class="news-item-top"><b>新增信息 ${i+1}</b></div><p>${esc(x)}</p></article>`).join('');
    return `<article class="day risk-${r.risk}"><div class="day-card"><div class="day-head"><div><div class="day-date">${esc(r.date)}</div><div class="day-target">${esc(r.symbol)} · ${esc(r.name)}</div></div><span class="risk-pill ${r.risk}">${esc(r.riskLabel)}</span></div><div class="day-body"><p class="analysis">${esc(r.analysis)}</p><div class="meta-row"><span>${esc(r.phase)}</span>${r.cutoff?`<span>截止 ${esc(r.cutoff)}</span>`:''}${r.noNew?'<span>无新增信息</span>':''}${r.hypothesis?`<span>${esc(r.hypothesis)}</span>`:''}</div>${sources?`<div class="news-items" style="margin-top:14px">${sources}</div>`:''}</div></div></article>`;
  }).join('');
}
async function init(){
  const months=monthRange(START_MONTH);
  const monthFilter=document.getElementById('monthFilter');
  monthFilter.innerHTML=months.map((m,i)=>`<option value="${m}" ${i===0?'selected':''}>${m}</option>`).join('');
  let records=[];
  async function loadSelected(){
    records=(await loadMonth(monthFilter.value)).map(normalize);
    const symbols=[...new Map(records.map(r=>[r.symbol,`${r.symbol} · ${r.name}`])).entries()];
    const targetFilter=document.getElementById('targetFilter');
    const prev=targetFilter.value;
    targetFilter.innerHTML='<option value="">全部目标</option>'+symbols.map(([s,n])=>`<option value="${esc(s)}">${esc(n)}</option>`).join('');
    if(symbols.some(([s])=>s===prev)) targetFilter.value=prev;
    document.getElementById('dayCount').textContent=String(new Set(records.map(r=>r.date)).size);
    const latest=[...records].sort((a,b)=>String(b.date).localeCompare(String(a.date)))[0];
    document.getElementById('latestTarget').textContent=latest?`${latest.symbol} ${latest.name}`:'—';
    document.getElementById('latestRisk').textContent=latest?latest.riskLabel:'—';
    render(records);
  }
  monthFilter.addEventListener('change',loadSelected);
  document.getElementById('targetFilter').addEventListener('change',()=>render(records));
  document.getElementById('resetFilter').addEventListener('click',()=>{document.getElementById('targetFilter').value='';render(records)});
  await loadSelected();
}
init();