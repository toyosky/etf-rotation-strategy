# Stage 16 — Activity-Conditioned Sign Identifiability Findings

Date: 2026-09-13

## Result

Using only the frozen Stage-3 expanding-window OOS predictions, tightening to ETFs with higher predicted path-activity rank does **not** produce broad, monotone, cross-period improvement in signed marginal-value identification.

### Overall active sample

All actually path-active rows:

- n = 155
- sign AUC = **0.5469**
- Spearman(predicted MUV, realized delta) = **0.0486**
- false-negative positive regret = **1.4120**
- correctly identified negative value = **1.3601**
- largest positive miss = **+0.2919**

As the monthly activity percentile restriction tightens:

- above 50th percentile: n = 118, sign AUC **0.5460**, MUV Spearman **0.0654**
- above 70th percentile: n = 99, sign AUC **0.5497**, MUV Spearman **0.0672**
- above 80th percentile: n = 84, sign AUC **0.5615**, MUV Spearman **0.0510**
- above 90th percentile: n = 67, sign AUC **0.5687**, MUV Spearman **0.0633**

The small AUC rise at the extreme activity tail is not accompanied by meaningful value-rank correlation and is not stable across periods.

## Frozen-period check

### 2023–24

- all active: sign AUC **0.4985**, MUV Spearman **0.0088**
- >50th activity percentile: **0.5069**, **-0.0021**
- >70th: **0.5283**, **-0.0023**
- >80th: **0.5733**, **0.0307**
- >90th: **0.5963**, **0.0560**

### 2025–26

- all active: sign AUC **0.6003**, MUV Spearman **0.0622**
- >50th activity percentile: **0.5877**, **0.1106**
- >70th: **0.5707**, **0.1189**
- >80th: **0.5319**, **0.0355**
- >90th: **0.5491**, **0.0839**

The direction is inconsistent: restricting to high activity improves AUC in 2023–24 but generally degrades it in 2025–26. This fails the ex-ante requirement for broad, monotone, cross-period improvement.

## Tail-risk check

Even in the highest-activity slices, false-removal asymmetry remains material. Above the 90th activity percentile:

- 31 rows still have point-predicted MUV < 0;
- positive false-negative regret sum = **0.6884**;
- correctly identified negative value sum = **0.6352**;
- largest positive miss = **+0.2348**.

Thus the economic cost of hidden winners remains comparable to the benefit of correctly identified negative names even where predicted competition relevance is highest.

## Retention conclusion

Stages 11–16 now support a fairly clear retention-side conclusion:

1. First-order and conditional second-order MUV are mostly structurally stable after a removal; widespread interaction sign flipping is not the main failure mechanism.
2. Observable ETF/relative/universe state predicts **competition-path relevance** reasonably well (path-activity AUC about 0.73).
3. The same state does **not** stably identify the **direction or magnitude** of marginal portfolio value once the ETF becomes competitively relevant.
4. Rare positive misses have strongly asymmetric regret; bootstrap uncertainty and distribution-free residual stress do not create useful safe-deletion coverage.
5. Conditioning on very high predicted path activity does not repair this identification failure.

Therefore current observables are useful for **attention, prioritization and risk budgeting**, but are not sufficient for a high-confidence signed dynamic retention/deletion policy.

## Next stage

The retention branch should now be frozen rather than further threshold-tuned.

The next lowest-freedom research branch is **admission**: construct time-forward add-one counterfactual labels MUV(k | U) for outsider ETFs using an ex-ante eligible candidate universe, then test separately:

- admission path activity: does outsider k actually enter/alter the OLS competition path after being admitted?
- conditional admission value: if it matters, is its marginal value positive or negative?

No retention result should be assumed to transfer automatically to admission.
