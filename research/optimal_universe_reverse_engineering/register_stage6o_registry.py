from pathlib import Path
import re

p = Path(__file__).with_name('OURE_EXPERIMENT_REGISTRY_20260914.yaml')
s = p.read_text(encoding='utf-8')
entry = '''

  - stage: 6O
    status: frozen_partial_pass_predictive_fail
    decision: member_traits_exist_but_admission_not_oos_supported
    run_id: 34914650531
    design: research/optimal_universe_reverse_engineering/OURE_STAGE6O_RF_HIGH_WINNER_MEMBER_AUDIT_DESIGN_20260915.md
    findings: research/optimal_universe_reverse_engineering/OURE_STAGE6O_RF_HIGH_WINNER_MEMBER_AUDIT_FINDINGS_20260915.md
    notes: "Inside previous-block-RF top20% K30s, member-level conditional future value has repeatable past-only structure: 6/21 traits across A/B/C/D pass the frozen stability gate. Future-useful members are more often eligible, less ubiquitous in RF-high, embedded in weaker trailing126 set contexts, somewhat further below recent highs, and not necessarily strong singleton past winners. However the strict chronological member RF fails all five predictive gates: median IC +0.0713, 3/5 positive, top10 actual percentile 0.4284, median top10 conditional-marginal lift -0.0230. Member mechanism exists, but prospective admission is not established."
'''
if '\n  - stage: 6O\n' not in s:
    s = s.replace('\nnext_gate:\n', entry + '\nnext_gate:\n')
new_gate = '''next_gate:
  direction: "Stage6O is frozen. The member-level unit of analysis is more informative: future-useful members inside RF-high sets show a repeated qualified-but-underrepresented / less-historically-exhausted challenger pattern, but the frozen chronological member RF does not identify the next top admissions."
  constraints: "Do not tune Stage6O RF-high cutoff, minimum appearance count, winner/loser cutoffs, member features, RF hyperparameters, or top10 rule on this history. A continuation must be a genuinely new admission hypothesis or new forward data, not post-hoc rescue."
'''
s = re.sub(r'next_gate:\n[\s\S]*\Z', new_gate, s)
p.write_text(s, encoding='utf-8')
