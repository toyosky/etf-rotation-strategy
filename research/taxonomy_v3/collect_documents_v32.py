"""Small resumable official-document acquisition; preserves bytes and PDF text.

The manifest records evidence, not classification. Reviewed exact mappings live
in index_aliases.json. A failed PDF does not stop other documents.
"""
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import requests

DOCUMENTS = {
    'brazil-159100': 'https://static.cninfo.com.cn/finalpage/2026-07-21/1225433022.PDF',
    'brazil-520870': 'https://www.sse.com.cn/disclosure/fund/announcement/c/new/2026-01-08/520870_20260108_Y21A.pdf',
    'ftse-cn-hk-517180': 'https://www.sse.com.cn/disclosure/fund/announcement/c/new/2025-04-21/517180_20250421_6CTO.pdf',
    'lof-precise-medical': 'https://www.sse.com.cn/disclosure/fund/announcement/c/new/2026-03-31/501006_20260331_JB0N.pdf',
    'lof-digital-health': 'https://www.sse.com.cn/disclosure/fund/announcement/c/new/2026-10-27/501008_20261027_JG1M.pdf',
    'lof-biotech': 'https://www.sse.com.cn/disclosure/fund/announcement/c/new/2026-04-22/501009_20260422_TKQG.pdf',
    'lof-tcm-feeder': 'https://99fund.com/announcement/zx/upload/2026/20260421/4ea0b1017cc74281acec90f0667e9d3d.pdf',
    'csi-a100-dual-codes': 'https://www.sse.com.cn/disclosure/fund/announcement/c/new/2026-06-11/561200_20260611_PEHQ.pdf',
    'nasdaq-ndx-methodology': 'https://indexes.nasdaq.com/docs/Methodology_NDX.pdf',
    'nasdaq-ndx-fund': 'https://static.cninfo.com.cn/finalpage/2026-04-30/1225258085.PDF',
    'cni-factsheet-399701': 'https://www.cnindex.com.cn/html2pdf/preview/jj_399701.pdf',
    'cni-factsheet-399702': 'https://www.cnindex.com.cn/html2pdf/preview/jj_399702.pdf',
}
for code in ['980092','980028','399701','399702','921128','921130']:
    DOCUMENTS['cni-methodology-'+code] = f'https://www.cnindex.com.cn/docs/gz_{code}.pdf'
for code in ['hstech','hsbio','hssciti','hsscam','hssc50','hscei','hsi','hsiii','hshci','hsscid','hsisc',
             'hsscsoy','hscgsi','hsmchyi','hsschi','hshylv','hscaupg']:
    DOCUMENTS['hsi-methodology-'+code] = f'https://www.hsi.com.hk/content/dam/wpb/hsil/index/methodologies/zh_cn/{code}/IM_{code}.pdf'
for mandate in json.loads(Path(__file__).with_name('fund_contract_evidence_v31.json').read_text()):
    if mandate['source_url'] not in DOCUMENTS.values():
        DOCUMENTS['mandate-'+mandate['symbol']] = mandate['source_url']


def fetch(key, url, output, retry_errors=False):
    path = output / (key+'.json')
    if path.exists():
        old = json.loads(path.read_text())
        if old.get('status') == 'ok' or not retry_errors:
            return old
    obj = dict(id=key, source_url=url, observed_at=datetime.now(timezone.utc).isoformat())
    try:
        response = requests.get(url,timeout=(10,30))
        response.raise_for_status()
        raw = response.content
        if not raw.startswith(b'%PDF'):
            raise ValueError('not a PDF; no evidence promoted')
        pdf = output/(key+'.pdf')
        pdf.write_bytes(raw)
        txt = output/(key+'.txt')
        subprocess.run(['pdftotext','-layout',str(pdf),str(txt)],check=True,capture_output=True)
        obj.update(status='ok', raw_path=pdf.name, raw_sha256=hashlib.sha256(raw).hexdigest(),
                   text_path=txt.name, text_sha256=hashlib.sha256(txt.read_bytes()).hexdigest())
    except Exception as exc:
        obj.update(status='error',error=f'{type(exc).__name__}: {exc}')
    path.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n')
    return obj


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--output',type=Path,required=True)
    ap.add_argument('--retry-errors',action='store_true')
    args=ap.parse_args()
    args.output.mkdir(parents=True,exist_ok=True)
    with ThreadPoolExecutor(max_workers=4) as pool:
        jobs=[pool.submit(fetch,k,u,args.output,args.retry_errors) for k,u in DOCUMENTS.items()]
        for job in as_completed(jobs):
            row=job.result()
            print(json.dumps({k:row[k] for k in ['id','status']},ensure_ascii=False),flush=True)


if __name__=='__main__':
    main()
