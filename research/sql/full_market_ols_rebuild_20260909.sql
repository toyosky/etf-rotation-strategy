-- Full-market ETF OLS research rebuild recipe
-- Saved before removing large, fully-rebuildable intermediate tables from Supabase Free database.
-- Source table retained: public.daily_bars
-- Small retained output: research.ols_episodes

create schema if not exists research;

create or replace function research.array_median(vals double precision[])
returns double precision
language sql
immutable strict
as $$
  select percentile_cont(0.5) within group (order by v)
  from unnest(vals) as t(v)
  where v is not null
$$;

create or replace function research.calc_ols26(prices double precision[])
returns table(
  slope double precision,
  intercept double precision,
  annual double precision,
  r2 double precision,
  score double precision,
  current_resid double precision
)
language plpgsql
immutable strict
as $$
declare
  i int;
  x double precision;
  y double precision;
  q double precision;
  fw double precision;
  sw double precision := 0;
  swx double precision := 0;
  swy double precision := 0;
  swxx double precision := 0;
  swxy double precision := 0;
  ybar double precision;
  ss_res double precision := 0;
  ss_tot double precision := 0;
begin
  if array_length(prices,1) <> 26 then return; end if;
  for i in 1..26 loop
    if prices[i] is null or prices[i] <= 0 then return; end if;
    x := i - 1;
    y := ln(prices[i]);
    q := power(0.5, (25.0 - x) / 10.0);
    fw := q*q;
    sw := sw + fw;
    swx := swx + fw*x;
    swy := swy + fw*y;
    swxx := swxx + fw*x*x;
    swxy := swxy + fw*x*y;
  end loop;
  if (sw*swxx - swx*swx) = 0 then return; end if;
  slope := (sw*swxy - swx*swy) / (sw*swxx - swx*swx);
  intercept := (swy - slope*swx) / sw;
  ybar := swy / sw;
  for i in 1..26 loop
    x := i - 1;
    y := ln(prices[i]);
    q := power(0.5, (25.0 - x) / 10.0);
    fw := q*q;
    ss_res := ss_res + fw*power(y - (slope*x + intercept),2);
    ss_tot := ss_tot + fw*power(y - ybar,2);
  end loop;
  r2 := case when ss_tot = 0 then 0 else 1.0 - ss_res/ss_tot end;
  annual := exp(slope*250.0)-1.0;
  score := case
    when annual > 0 and r2 > 0 then annual*r2
    when annual < 0 and r2 < 0 then abs(annual)*abs(r2)
    else 0.0 end;
  current_resid := ln(prices[26]) - (slope*25.0 + intercept);
  return next;
end $$;

-- Rebuild trading-day sequence cache from public.daily_bars.
drop table if exists research.daily_seq;
create table research.daily_seq as
select
  symbol,
  date,
  row_number() over(partition by symbol order by date)::int as rn,
  min(date) over(partition by symbol) as first_date,
  open, high, low, close, volume, amount,
  ln(close / lag(close) over(partition by symbol order by date)) as logret1
from public.daily_bars;
alter table research.daily_seq add primary key(symbol, rn);
alter table research.daily_seq add unique(symbol, date);
create index daily_seq_date_idx on research.daily_seq(date);
create index daily_seq_symbol_date_idx on research.daily_seq(symbol,date);

-- Rebuild large daily feature cache. This is intentionally an intermediate table.
drop table if exists research.ols_daily_features;
create table research.ols_daily_features (
  date date not null,
  symbol text not null,
  close double precision,
  amount double precision,
  volume double precision,
  history_bars integer,
  listing_age_days integer,
  avg_amount60 double precision,
  median_amount60 double precision,
  nonzero_volume_ratio60 double precision,
  universe_eligible boolean,
  slope double precision,
  intercept double precision,
  annual double precision,
  r2 double precision,
  score double precision,
  current_resid double precision,
  recent_drop3 boolean,
  trend_eligible boolean,
  score_delta double precision,
  r2_delta double precision,
  slope_delta double precision,
  ret3 double precision,
  ret5 double precision,
  ret10 double precision,
  ret20 double precision,
  ret60 double precision,
  dist_high20 double precision,
  dist_high60 double precision,
  dist_high120 double precision,
  vol20 double precision,
  vol60 double precision,
  efficiency10 double precision,
  efficiency20 double precision,
  xrank integer,
  xpercentile double precision,
  primary key(date,symbol)
);
create index ols_daily_features_date_eligible_idx on research.ols_daily_features(date,trend_eligible);
create index ols_daily_features_symbol_date_idx on research.ols_daily_features(symbol,date);

create or replace function research.populate_ols_features(p_start date, p_end date)
returns void
language plpgsql
as $$
begin
  with z as (
    select t.*,
           h.n60,h.avg_amount60,h.median_amount60,h.nz60,h.high20,h.high60,h.high120,h.vol20,h.vol60,h.absret10,h.absret20,
           h.c3,h.c5,h.c10,h.c20,h.c60,h.min_ratio3,
           o.slope,o.intercept,o.annual,o.r2,o.score,o.current_resid,
           (t.rn>=200 and (t.date-t.first_date)>=365 and h.n60=60 and h.avg_amount60>=20000000 and h.median_amount60>=10000000 and h.nz60>=0.95) universe_eligible
    from research.daily_seq t
    cross join lateral (
      select count(*) filter(where s.rn>=t.rn-59) n60,
             avg(s.amount) filter(where s.rn>=t.rn-59) avg_amount60,
             percentile_cont(0.5) within group(order by s.amount) filter(where s.rn>=t.rn-59) median_amount60,
             avg(case when s.volume>0 then 1.0 else 0.0 end) filter(where s.rn>=t.rn-59) nz60,
             max(s.close) filter(where s.rn>=t.rn-19) high20,
             max(s.close) filter(where s.rn>=t.rn-59) high60,
             max(s.close) high120,
             stddev_samp(s.logret1) filter(where s.rn>=t.rn-19) vol20,
             stddev_samp(s.logret1) filter(where s.rn>=t.rn-59) vol60,
             sum(abs(s.logret1)) filter(where s.rn>=t.rn-9) absret10,
             sum(abs(s.logret1)) filter(where s.rn>=t.rn-19) absret20,
             max(s.close) filter(where s.rn=t.rn-3) c3,
             max(s.close) filter(where s.rn=t.rn-5) c5,
             max(s.close) filter(where s.rn=t.rn-10) c10,
             max(s.close) filter(where s.rn=t.rn-20) c20,
             max(s.close) filter(where s.rn=t.rn-60) c60,
             min(exp(s.logret1)) filter(where s.rn>=t.rn-2) min_ratio3,
             array_agg(s.close order by s.rn) filter(where s.rn>=t.rn-25) prices26
      from research.daily_seq s
      where s.symbol=t.symbol and s.rn between greatest(1,t.rn-119) and t.rn
    ) h
    left join lateral research.calc_ols26(h.prices26) o on array_length(h.prices26,1)=26
    where t.date between p_start and p_end
  ), q as (
    select *, (universe_eligible and annual>0 and r2>0 and score>0 and coalesce(min_ratio3,1)>=0.97) trend_eligible
    from z
  )
  insert into research.ols_daily_features(
    date,symbol,close,amount,volume,history_bars,listing_age_days,avg_amount60,median_amount60,nonzero_volume_ratio60,
    universe_eligible,slope,intercept,annual,r2,score,current_resid,recent_drop3,trend_eligible,
    ret3,ret5,ret10,ret20,ret60,dist_high20,dist_high60,dist_high120,vol20,vol60,efficiency10,efficiency20
  )
  select date,symbol,close,amount,volume,rn,(date-first_date)::int,avg_amount60,median_amount60,nz60,universe_eligible,
         slope,intercept,annual,r2,score,current_resid,coalesce(min_ratio3,1)<0.97,trend_eligible,
         case when c3>0 then close/c3-1 end,
         case when c5>0 then close/c5-1 end,
         case when c10>0 then close/c10-1 end,
         case when c20>0 then close/c20-1 end,
         case when c60>0 then close/c60-1 end,
         close/high20-1,close/high60-1,close/high120-1,vol20,vol60,
         case when c10>0 and absret10>0 then abs(ln(close/c10))/absret10 end,
         case when c20>0 and absret20>0 then abs(ln(close/c20))/absret20 end
  from q
  on conflict(date,symbol) do nothing;
end $$;

-- Recommended future architecture:
-- 1) Build daily_seq transiently.
-- 2) Compute ols_daily_features in bounded date chunks.
-- 3) Export chunks to compressed Parquet and archive in Supabase Storage / S3.
-- 4) Persist only compact episode-level research data in Postgres.
