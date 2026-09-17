const assets=[
{code:'159934',name:'黄金ETF易方达',role:'GOLD',desc:'黄金现货暴露 · Stage8L 替换 518880'},
{code:'159985',name:'豆粕ETF',role:'SOYMEAL',desc:'农产品商品暴露'},
{code:'161226',name:'白银LOF',role:'SILVER',desc:'贵金属高弹性暴露'},
{code:'513100',name:'纳指ETF',role:'NASDAQ100',desc:'美国大型科技成长'},
{code:'159957',name:'创业板ETF华夏',role:'CHINEXT',desc:'A股成长 · Stage8L 替换 159915'},
{code:'159509',name:'纳指科技ETF',role:'NASDAQ TECH',desc:'美国科技强化暴露'},
{code:'513290',name:'纳指生物科技ETF',role:'US BIOTECH',desc:'美国生物科技'},
{code:'159529',name:'标普消费ETF景顺',role:'US CONSUMER',desc:'美国消费行业'},
{code:'159981',name:'能源化工ETF',role:'ENERGY-CHEM',desc:'国内商品周期 · 保留休眠机会'},
{code:'501018',name:'原油LOF',role:'CRUDE OIL',desc:'原油周期暴露'},
{code:'513530',name:'港股通红利ETF华泰柏瑞',role:'HK DIVIDEND',desc:'港股高股息 · 替换 513920'},
{code:'511380',name:'可转债ETF',role:'CONVERTIBLE',desc:'可转债混合风险暴露'},
{code:'164824',name:'印度基金LOF',role:'INDIA',desc:'印度权益 · 当前保留观察'},
{code:'511220',name:'城投债ETF',role:'CASH',desc:'现金比较器 / 风险关闭状态',cash:true}
];
const grid=document.getElementById('assetGrid');
grid.innerHTML=assets.map(a=>`<article class="asset ${a.cash?'cash':''}"><div class="top"><code>${a.code}</code><span class="role">${a.role}</span></div><h3>${a.name}</h3><p>${a.desc}</p></article>`).join('');

const annual=[
['2015',2.99],['2016',10.68],['2017',2.10],['2018',11.23],['2019',27.54],['2020',60.05],['2021',34.93],['2022',23.87],['2023',21.31],['2024',65.57],['2025',115.42],['2026*',134.99]
];
const maxAnnual=Math.max(...annual.map(x=>x[1]));
document.getElementById('annualChart').innerHTML=annual.map(([y,v])=>`<div class="bar-col"><div class="bar" data-value="${v.toFixed(2)}%" style="height:${Math.max(4,v/maxAnnual*220)}px"></div><label>${y}</label></div>`).join('');

const contrib=[
['白银',29.4],['纳指100',17.8],['原油',15.7],['创业板',10.8],['纳指科技',10.7],['能源化工',5.2],['港股红利',4.0],['豆粕',3.8],['黄金',3.1],['标普消费',2.5],['生物科技',1.5],['可转债',-0.4],['印度',-3.6]
];
const maxAbs=Math.max(...contrib.map(x=>Math.abs(x[1])));
document.getElementById('contribChart').innerHTML=contrib.map(([n,v])=>`<div class="hrow"><label>${n}</label><div class="htrack"><div class="hfill ${v<0?'neg':''}" style="width:${Math.abs(v)/maxAbs*100}%"></div></div><span>${v>0?'+':''}${v.toFixed(1)}%</span></div>`).join('');

// Keep navigation consistent across static pages.
document.querySelectorAll('nav span').forEach(node=>{
  if(node.textContent.trim()==='Strategy'){
    const a=document.createElement('a');
    a.href='./strategy.html';
    a.textContent='Strategy';
    node.replaceWith(a);
  }
});
const nav=document.querySelector('.topbar nav');
if(nav && !nav.querySelector('a[href="./live.html"]')){
  const a=document.createElement('a');a.href='./live.html';a.textContent='Live';nav.appendChild(a);
}
