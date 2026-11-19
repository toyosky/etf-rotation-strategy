-- READ ONLY. Project gsyziuzezmmnvgdoazkg; captured 2026-11-12 UTC.
-- Run each SELECT separately when the MCP returns only the final result set.
select table_name,column_name,data_type,is_nullable
from information_schema.columns
where table_schema='public' and table_name in
 ('instrument_metadata','instrument_metadata_current','daily_bars','fund_premium_history')
order by table_name,ordinal_position;

select * from public.instrument_metadata order by symbol,valid_from,id;

select count(*) as rows,count(distinct symbol) as symbols,
 count(*) filter(where current_exchange_listed) as listed,
 count(*) filter(where has_daily_bars) as has_bars,
 count(*) filter(where nullif(underlying_key,'') is not null) as underlying_covered,
 count(*) filter(where nullif(risk_bucket,'') is not null) as risk_covered,
 count(*) filter(where nullif(style_sector,'') is not null) as style_covered,
 count(*) filter(where needs_review) as review,
 count(*) filter(where historical_safe) as historical_safe,
 min(valid_from) as earliest_valid_from,max(updated_at) as updated_at
from public.instrument_metadata_current;

select a.symbol,a.id as a_id,b.id as b_id,
 a.valid_from as a_from,a.valid_to as a_to,b.valid_from as b_from,b.valid_to as b_to
from public.instrument_metadata a join public.instrument_metadata b
 on a.symbol=b.symbol and a.id<b.id
 and daterange(a.valid_from,a.valid_to,'[]') && daterange(b.valid_from,b.valid_to,'[]');

select instrument_type,count(*) as rows,count(distinct symbol) as symbols,
 min(date) as min_date,max(date) as max_date
from public.daily_bars group by instrument_type;

select bucket_id,name,metadata from storage.objects order by bucket_id,name;
