-- Current asset-universe registry used by GitHub Actions / Asset Health.
-- Market data presence in daily_bars is intentionally independent of trading-pool status.

create table if not exists public.asset_universe (
    symbol text primary key check (symbol ~ '^[0-9]{6}$'),
    name text not null,
    universe_status text not null check (
        universe_status in ('ACTIVE', 'CASH_PROXY', 'RETIRED', 'CANDIDATE')
    ),
    active_from date,
    active_to date,
    replacement_for text,
    reason text,
    updated_at timestamptz not null default now()
);

comment on table public.asset_universe is
'Current research/trading-universe registry. Market data may exist for ACTIVE, RETIRED, CANDIDATE, and CASH_PROXY assets; status is independent from daily_bars presence.';

alter table public.asset_universe enable row level security;
revoke all on table public.asset_universe from anon, authenticated;
grant select, insert, update, delete on table public.asset_universe to service_role;

-- Current registry snapshot (2026-09-08).
-- Historical strategy_runs rows remain immutable; this table controls current monitoring membership.
insert into public.asset_universe
(symbol, name, universe_status, active_from, active_to, replacement_for, reason)
values
('159509','纳指科技ETF','ACTIVE',null,null,null,'原Premium15正式池'),
('159529','标普消费ETF','ACTIVE',null,null,null,'原Premium15正式池'),
('159915','创业板ETF','ACTIVE',null,null,null,'原Premium15正式池'),
('159981','能源化工期货ETF','ACTIVE',null,null,null,'原Premium15正式池'),
('159985','豆粕ETF','ACTIVE',null,null,null,'原Premium15正式池；Asset Health当前WATCH，继续监控'),
('161226','白银LOF','ACTIVE',null,null,null,'原Premium15正式池'),
('164824','印度基金LOF','ACTIVE',null,null,null,'原Premium15正式池'),
('501018','南方原油LOF','ACTIVE',null,null,null,'原Premium15正式池'),
('511380','转债ETF','ACTIVE',null,null,null,'原Premium15正式池'),
('513100','纳指ETF','ACTIVE',null,null,null,'原Premium15正式池'),
('513290','纳指生物ETF','ACTIVE',null,null,null,'原Premium15正式池'),
('513920','央企40ETF（历史命名）','ACTIVE',null,null,null,'原Premium15正式池；名称沿用历史研究口径'),
('518880','黄金ETF','ACTIVE',null,null,null,'原Premium15正式池'),
('511220','城投债ETF（现金信号）','CASH_PROXY',null,null,null,'Top1时映射为现金信号，不作为风险资产健康度判断对象'),
('159825','农业ETF富国','RETIRED','2021-01-04','2026-09-08',null,'Asset Health复核：Top1近高点后的5/10日延续性持续偏弱；退出正式池，保留历史数据'),
('512660','军工ETF','CANDIDATE',null,null,'159825','159825替换候选，尚未进入正式池'),
('513030','德国DAX ETF','CANDIDATE',null,null,'159825','159825优先替换测试候选，尚未进入正式池'),
('513520','日经225 ETF','CANDIDATE',null,null,'159825','159825替换候选，尚未进入正式池')
on conflict (symbol) do update set
    name = excluded.name,
    universe_status = excluded.universe_status,
    active_from = excluded.active_from,
    active_to = excluded.active_to,
    replacement_for = excluded.replacement_for,
    reason = excluded.reason,
    updated_at = now();
