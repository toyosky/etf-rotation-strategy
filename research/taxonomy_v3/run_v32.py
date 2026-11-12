"""Offline V3.2 acceptance entrypoint; no HTTP or database writes.

Combines explicitly frozen V3/V3.1 sources, validates raw document evidence,
builds twice, verifies byte equality, tests the real artifacts, and renders a
report. Acquisition is intentionally a separate, dated operation.
"""
from __future__ import annotations
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
import pandas as pd
from .build import dump
from .collect_csindex_catalog_v31 import read_catalog
from .evidence import verify_documents

ROOT=Path(__file__).parent


def prepare(work):
    official=work/'official'
    official.mkdir(parents=True,exist_ok=True)
    for src in sorted((ROOT/'snapshot/official').glob('*.json')):
        shutil.copyfile(src,official/src.name)
    delta=ROOT/'snapshot/official_v31'
    for src in sorted(delta.glob('cnindex-*.json')):
        shutil.copyfile(src,official/src.name)
    shutil.copyfile(delta/'csindex-catalog.json',official/'csindex-catalog.json')
    csi=json.loads((delta/'csindex-catalog.json').read_text())
    raw=(delta/'csindex-catalog.xlsx').read_bytes()
    assert hashlib.sha256(raw).hexdigest()==csi['raw_sha256']
    assert read_catalog(raw)==csi['payload']['indices'], 'normalized CSI catalog differs from raw workbook'
    for row in json.loads((ROOT/'output/profiles.json').read_text()):
        dump(work/'profiles'/(row['symbol']+'.json'),row)
    docs=[]; failed=[]
    for path in sorted((ROOT/'snapshot/supplement_v32').glob('*.json')):
        obj=json.loads(path.read_text())
        if obj['status']=='ok':
            verify_documents([dict(manifest=str(path.relative_to(ROOT)))],'2026-11-12')
            docs.append(obj)
        else:
            failed.append(dict(id=obj['id'],error=obj['error']))
    return dict(official_csi_raw_hash_and_parsed_rows_verified=len(csi['payload']['indices']),
        official_pdf_hashes_verified=len(docs), failed_document_requests=failed,
        source_observation_date='2026-11-12', database_writes=0)


def render(output,checks):
    old=json.loads((ROOT/'output_v31/summary.json').read_text())
    new=json.loads((output/'summary.json').read_text())
    rows=json.loads((output/'classifications.json').read_text())
    history=json.loads((output/'strategy_history_review.json').read_text())
    index_history=json.loads((output/'index_history_review.json').read_text())
    d=new['dedup_comparison']
    lines=['# ETF/LOF 经济暴露 V3.2 实际补证与回归报告','',
        '本轮修复同指数别名拆分、跨市场区域和民企标签错误，并继续补证。生产数据库、正式 OLS、持仓与现有交易定时任务未改动。','',
        '| 口径 | V3.1 | V3.2 |','|---|---:|---:|',
        f"| 总基金数 | {old['total_funds']} | {new['total_funds']} |",
        f"| 当前被动指数分类通过 | {old['fully_classified_current']} | {new['fully_classified_current']} |",
        f"| 通过率 | {old['fully_classified_current']/old['total_funds']:.2%} | {new['fully_classified_current']/new['total_funds']:.2%} |",
        f"| 兼容旧口径的待复核/池外队列 | {old['needs_review']} | {new['needs_review']} |",
        f"| 代码—全称桥接待核实原因数 | {old['review_reasons']['OFFICIAL_CODE_NAME_LINK_NOT_VERIFIED']} | {new['review_reasons']['OFFICIAL_CODE_NAME_LINK_NOT_VERIFIED']} |",
        f"| 当前通过集合的精确指数/保守暴露组 | {old['exact_index_groups']} | {new['exact_index_groups']} |",'',
        f"当前通过集合含 {len({r['sector_level1'] for r in rows if not r['needs_review']})} 种一级标签、{len({r['sector_level2'] for r in rows if not r['needs_review']})} 种二级标签；三级标签未核实的保持空值。",'',
        f"新口径区分：经济身份已核实 {new['economically_classified_count']} 只；真正尚有未解决分类问题 {new['unresolved_classification_count']} 只；已核实但排除于默认被动指数池 {new['verified_excluded_strategy_count']} 只。原因可重叠，不能相加当基金数。",'',
        '## 已修复与补证','',
        '- 159100、520870 的官方文件均明确写出 IBOVESPA，现共享精确键和暴露 ID；不同目标 ETF 留在产品复制方式层，不制造两个独立趋势机会。',
        '- 富时中国国企开放共赢指数按官方 80只A股、20只香港上市公司范围标为 CN_HK；159973 的民企指数改为 PRIVATE_ENTERPRISE。宽泛的“富时中国/MSCI中国”不再自动填为纯CN。',
        '- 恒生17组官方编制方案的价格代码已逐行核对；股息累计、净累计代码没有混入价格指数别名。恒生A股电网设备按实际A股范围处理，编制机构品牌不代替经济区域。',
        '- 国证现金流/家电/信用债/科创债、中证A100双市场代码及纳斯达克100桥接均有冻结原文件；同指数不同写法统一到经过证实的身份。',
        '- 医药LOF四组A/C份额以官方被动投资目标和份额代码表补证；中药LOF的当前ETF联接方式单独保留，不把业绩比较基准独自作为被动跟踪证据。',
        '- 501018、159934、161226 属于已核实的池外策略/非指数参考，不再被统计成“身份尚未查清”；needs_review保留旧池口径，classification_status与unresolved_reasons说明实际状态。','',
        '## 当前同口径去重','',
        f"实际行情 {new['archive_symbols']} 只、{new['archive_rows']:,} 行。当前分类通过且有行情 {d['approved_archive_symbols']} 只 → 精确指数 {d['exact_index_groups']} 组 → 保守细分暴露 {d['fine_exposure_groups']} 组；区域×资产类型×一级标签 {d['broad_sector_groups']} 组。其他基金是证据/策略排除，不能当成去重节省。没有未经核实的跨指数合并。",'',
        '## 真实样例','', '| 代码 | 官方指数/法定策略 | 精确键 | 状态 |', '|---|---|---|---|']
    for s in ['159100','520870','517090','517180','159973','159320','159102','159166','159501','159923','501005','501006','501007','501009','501011','501012','501018','159934','161226']:
        r=next(x for x in rows if x['symbol']==s)
        lines.append(f"| {s} | {r['index_name'] or r['exposure_name'] or '待核实'} | {r['exact_index_key'] or '无（非指数）'} | {r['classification_status']} |")
    lines += ['', '## 时间与执行边界','',
        '当前资料最早从2026-11-13进入日期接口。2017/2021/2025等早期日期不会因当前补证而获得标签。执行属性批准数仍为0；未运行策略收益回测，也未批准实际交易池。',
        f"发现 {len(history)} 条当前报告记载的合同有效日期早于抓取日、晚于首根行情的记录，见 strategy_history_review.json。501011/501012 的当前合同生效日为2022-12-02，而上市/行情更早；需取得转型时点原公告，才能建立历史策略区间。当前记录没有据此回填。",'',
        f"另保存 {len(index_history)} 条恒生生物科技指数历史变更线索（2024-12-09更名及指数值缩放、2025-09-08选样范围变化、2025-09-15代码变化）。资料来自当前编制方案的修改记录，未核实当年的原始公告公布时间，所以不自动生成历史可用区间。",'',
        '## 实际验证','',
        f"- {checks['unit_tests_passed']} 项测试通过，失败/错误/跳过均为0。包含真实巴西双产品只能贡献一个代表、跨市场区域、民企、LOF A/C与非指数状态回归。",
        f"- 官方CSI原始工作簿与 {checks['official_csi_raw_hash_and_parsed_rows_verified']} 条解析记录一致；{checks['official_pdf_hashes_verified']} 份成功采集PDF及文本哈希已核对。失败链接保留请求记录，没有据此批准分类。",
        f"- {checks['byte_identical_outputs']} 个生成文件及完整manifest重复构建逐字节一致；Parquet实际以PAR1开头并可读，非LFS指针。",
        '- 冻结输入均在仓库与既有归档中，run_v32.py离线完成验收；只修改独立研究工作流，无定时触发。','',
        '## 剩余复核原因','', '| 原因 | 条目数（重叠） |','|---|---:|']
    lines += [f'| {k} | {v} |' for k,v in sorted(new['review_reasons'].items())]
    lines += ['', '后续仍需逐份核实剩余LOF/增强策略、解决其余指数身份桥接、补历史变更公告及执行证据。当前比例不是全市场分类或无前视回测已经完成的声明。','']
    (output/'REPORT_V32.md').write_text('\n'.join(lines))


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--work',type=Path,required=True)
    ap.add_argument('--bars',type=Path)
    ap.add_argument('--prepare-only',action='store_true')
    args=ap.parse_args()
    checks=prepare(args.work)
    if args.prepare_only:
        print(json.dumps(checks,ensure_ascii=False,indent=2)); return
    bars=args.bars or args.work/'refreshed_daily_bars.parquet'
    output=ROOT/'output_v32'
    def command(module,*extra):
        subprocess.run([sys.executable,'-m',module,*map(str,extra)],check=True)
    for dest in [output,args.work/'repeat']:
        command('research.taxonomy_v3.build','--metadata',ROOT/'snapshot/metadata.json',
            '--profiles',args.work/'profiles','--official',args.work/'official',
            '--bars',bars,'--snapshot-date','2026-11-12','--output',dest)
    manifest=json.loads((output/'manifest.json').read_text())
    assert manifest==json.loads((args.work/'repeat/manifest.json').read_text())
    for name in manifest['outputs']:
        assert (output/name).read_bytes()==(args.work/'repeat'/name).read_bytes(),name
    parquet=output/'classifications.parquet'
    assert parquet.read_bytes().startswith(b'PAR1'), 'not an actual readable Parquet'
    assert len(pd.read_parquet(parquet))==2147
    command('research.taxonomy_v3.validate','--output',output,'--bars',bars)
    junit=args.work/'tests.xml'
    tested=subprocess.run([sys.executable,'-m','pytest',str(ROOT/'test_taxonomy.py'),'-q',
                           '--junitxml',str(junit)],capture_output=True,text=True)
    print(tested.stdout)
    if tested.returncode:
        print(tested.stderr,file=sys.stderr);raise SystemExit(tested.returncode)
    suites=ET.parse(junit).getroot().findall('testsuite')
    counts={field:sum(int(s.get(field,'0')) for s in suites) for field in ['tests','failures','errors','skipped']}
    assert counts['tests'] and not counts['failures'] and not counts['errors'] and not counts['skipped']
    checks.update(status='PASS',unit_tests_passed=counts['tests'],test_failures=0,
        test_errors=0,test_skipped=0,byte_identical_outputs=len(manifest['outputs']),
        full_manifest_identical=True,parquet_read_verified=True,production_logic_changes=0,
        historical_strategy_backtest_run=False)
    dump(output/'execution_checks.json',checks)
    render(output,checks)
    print('V32_ACCEPTANCE_PASS',json.dumps({k:v for k,v in checks.items() if k!='failed_document_requests'}))


if __name__=='__main__':
    main()
