-- Canonical DDL for Asset Health Monitor V1.
-- Applied to Supabase project rmdfnksgqvewijegnqon on 2026-09-08.
-- Diagnostic only: this table never drives ETF_POOL changes automatically.

create table if not exists public.asset_health_snapshots (
    snapshot_date date not null,
    symbol text not null check (symbol ~ '^[0-9]{6}$'),
    monitor_version text not null,
    source_strategy_version text not null,
    data_cutoff date not null,
    bars_max_date date,
    signals_max_date date,
    data_status text not null check (data_status in ('FRESH','STALE')),

    top1_count integer not null default 0 check (top1_count >= 0),
    top1_fwd5_mean double precision,
    top1_fwd5_median double precision,
    top1_fwd5_win_rate double precision,
    top1_fwd10_mean double precision,
    top1_fwd10_median double precision,
    top1_fwd10_win_rate double precision,

    near_high_count integer not null default 0 check (near_high_count >= 0),
    near_high_fwd5_mean double precision,
    near_high_fwd5_median double precision,
    near_high_fwd5_win_rate double precision,
    near_high_fwd10_mean double precision,
    near_high_fwd10_median double precision,
    near_high_fwd10_win_rate double precision,

    recent_2y_near_high_count integer not null default 0 check (recent_2y_near_high_count >= 0),
    recent_2y_near_high_fwd10_mean double precision,
    recent_2y_near_high_fwd10_win_rate double precision,

    recent_1y_near_high_count integer not null default 0 check (recent_1y_near_high_count >= 0),
    recent_1y_near_high_fwd10_mean double precision,
    recent_1y_near_high_fwd10_win_rate double precision,

    avg_top1_score double precision,
    avg_top1_r2 double precision,
    status text not null check (status in ('HEALTHY','WATCH','WARNING','INSUFFICIENT_DATA')),
    reason text not null,
    metrics jsonb not null default '{}'::jsonb check (jsonb_typeof(metrics) = 'object'),
    computed_at timestamptz not null default now(),

    primary key (snapshot_date, symbol, monitor_version, source_strategy_version)
);

comment on table public.asset_health_snapshots is
'Prospective asset-health monitoring snapshots. Diagnostic only; never auto-removes assets from the trading pool.';
comment on column public.asset_health_snapshots.status is
'Health classification from frozen monitor rules. Diagnostic only and not a trading instruction.';
comment on column public.asset_health_snapshots.data_status is
'FRESH/STALE based on the latest daily_bars and source strategy signals available at computation time.';

create index if not exists asset_health_snapshots_symbol_date_idx
    on public.asset_health_snapshots (symbol, snapshot_date desc);

alter table public.asset_health_snapshots enable row level security;
revoke all on table public.asset_health_snapshots from anon, authenticated;
grant select, insert, update, delete on table public.asset_health_snapshots to service_role;
