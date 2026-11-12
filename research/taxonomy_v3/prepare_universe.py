"""Union of frozen metadata, official ETF/LOF lists, and actual archived symbols."""
import argparse
import json
from pathlib import Path
import pandas as pd
from .build import official_inputs, dump


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--metadata',type=Path,required=True)
    ap.add_argument('--official',type=Path,required=True)
    ap.add_argument('--bars',type=Path,required=True)
    ap.add_argument('--output',type=Path,required=True)
    args=ap.parse_args()
    sh,sz=official_inputs(args.official)
    symbols={r['symbol'] for r in json.loads(args.metadata.read_text())}
    symbols |= set(sh) | set(sz)
    symbols |= set(pd.read_parquet(args.bars,columns=['symbol']).symbol.astype(str).str.zfill(6))
    dump(args.output,[dict(symbol=s) for s in sorted(symbols)])
    print(len(symbols))


if __name__=='__main__':
    main()
