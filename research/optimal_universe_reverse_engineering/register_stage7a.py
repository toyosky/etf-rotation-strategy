from pathlib import Path

p = Path('research/optimal_universe_reverse_engineering/OURE_EXPERIMENT_REGISTRY_20260914.yaml')
s = p.read_text(encoding='utf-8')
entry = '''

  - stage: 7A
    status: frozen_pass
    decision: robust_selection_supported
    run_id: 34916978106
    design: research/optimal_universe_reverse_engineering/OURE_STAGE7A_ROBUST_K30_OOS_DESIGN_20260915.md
    findings: research/optimal_universe_reverse_engineering/OURE_STAGE7A_ROBUST_K30_OOS_FINDINGS_20260915.md
    notes: "Strict B04..B09 OOS with a frozen 3-block robust score. Robust K30 median IC +0.2028, 5/6 positive, median Top50 actual percentile 0.6239, median selected-Top1 actual percentile 0.7443. Selected path +118.38% versus +25.91% latest126 and -37.32% previous-block RF; worst block -15.28% also beats both. All 5 preregistered gates pass. Result supports robust opportunity-set design over exact next-regime prediction, conditional on the frozen 2496-set family library and mature common-pool rule."
'''
head, sep, _tail = s.partition('\nnext_gate:\n')
if not sep:
    raise SystemExit('next_gate marker not found')
if '\n  - stage: 7A\n' not in head:
    head = head.rstrip() + entry
new_gate = '''
next_gate:
  direction: "Stage7A is frozen PASS. The main research objective shifts from forecasting the exact next winner to constructing a mature K30 opportunity set that remains useful across several completed regimes, then letting the frozen OLS react to the realized next regime."
  constraints: "Do not tune the 3-block window, 50/50 median-Q25 formula, K=30, maturity/common-pool rule, family generator, or gate thresholds on this history. Next work should explain and replicate why robust winners work (coverage, productive relay, harmful competition, challenger structure) before any parameter optimization."
'''
p.write_text(head + new_gate, encoding='utf-8')
