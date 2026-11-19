"""Offline acceptance checks over real frozen inputs and generated artifacts."""
from __future__ import annotations
import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import pandas as pd
from .model import classifications_at, normalize_name, validate_intervals
from .representatives import select_representatives
from .build import dump


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--output', type=Path, required=True)
    ap.add_argument('--bars', type=Path, required=True)
    args=ap.parse_args()
    rows=json.loads((args.output/'classifications.json').read_text())
    validate_intervals(rows)
    assert len(rows)==len({r['symbol'] for r in rows})
    assert all(r['known_from']>r['observed_on'] for r in rows)
    accepted=[r for r in rows if not r['needs_review']]
    names=defaultdict(set)
    groups=defaultdict(set)
    for r in accepted:
        assert r['exact_index_verified'] and r['source_url'] and r['exposure_id']
        names[normalize_name(r['index_name'])].add(r['exact_index_key'])
        groups[r['exposure_id']].add((r['exact_index_key'],r['tracking_mode'],r['region_primary'],r['exposure_type']))
    assert all(len(s)==1 for s in names.values()), 'approved identical names split across keys'
    assert all(len(s)==1 for s in groups.values()), 'different indices/modes/regions/assets merged'
    b=pd.read_parquet(args.bars)
    assert not b.duplicated(['symbol','date']).any(), 'duplicate market source grain'
    assert hashlib.sha256(args.bars.read_bytes()).hexdigest()==json.loads((args.output/'summary.json').read_text())['archive_sha256']
    # Observed calendar is sufficient to demonstrate that currently captured
    # classifications must all be excluded on prior dates. It is not promoted
    # to an official future exchange calendar for investable backtests.
    calendar=sorted(b.date.astype(str).str[:10].unique())
    probes=[]
    for d in ['2021-01-04', '2025-01-02', calendar[-1]]:
        if d not in calendar:
            continue
        result=select_representatives(rows,b,calendar,d)
        assert not result['representatives']
        assert len(result['excluded'])==len(rows)
        probes.append(dict(date=d, representatives=0, eligible=0,
                           excluded=len(result['excluded']), reasons=dict(Counter(x['reason'] for x in result['excluded']))))
    result=dict(status='PASS', input_rows=len(b), input_symbols=int(b.symbol.nunique()),
                accepted_classification_rows=len(accepted), no_overlaps=True,
                no_approved_cross_index_region_asset_merges=True,
                no_approved_identical_name_splits=True,
                historical_probes=probes,
                warning='Empty historical pools are intended evidence gating; no historical strategy backtest was run')
    dump(args.output/'validation.json',result)
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=='__main__':
    main()
