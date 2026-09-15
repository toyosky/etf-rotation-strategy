#!/usr/bin/env python3
from __future__ import annotations
import os
from pathlib import Path
import pandas as pd
from sqlalchemy import create_engine, text
from full_market_ols_storage import _db_url

OUT = Path(os.getenv('OUTPUT_DIR','oure-stage8e-inventory'))
OUT.mkdir(parents=True, exist_ok=True)
url = os.getenv('ETF_DAILY_BARS_DATABASE_URL')
if not url:
    raise SystemExit('Missing ETF_DAILY_BARS_DATABASE_URL')
eng = create_engine(_db_url(url), pool_pre_ping=True)
q = '''
select symbol,name,product_type,asset_class,region_primary,exposure_level1,exposure_level2,
       underlying_key,risk_bucket,style_sector,is_qdii,premium_sensitive,has_daily_bars,
       leveraged_flag,inverse_flag,needs_review
from public.instrument_metadata_current
where has_daily_bars
order by asset_class,region_primary,risk_bucket,symbol
'''
df = pd.read_sql_query(text(q), eng)
df['symbol'] = df['symbol'].astype(str).str.zfill(6)
df.to_csv(OUT/'metadata_inventory.csv', index=False)
summary = (df.groupby(['asset_class','region_primary','exposure_level1','risk_bucket'], dropna=False)
             .agg(n=('symbol','size'), sample_symbols=('symbol', lambda x: ','.join(list(x)[:8])),
                  sample_names=('name', lambda x: ' | '.join([str(v) for v in list(x)[:8]])))
             .reset_index().sort_values(['asset_class','region_primary','exposure_level1','risk_bucket']))
summary.to_csv(OUT/'economic_bucket_inventory.csv', index=False)
print(summary.to_string(index=False))
