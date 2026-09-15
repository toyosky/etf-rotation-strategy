# OURE Stage8L — Within-Exposure ETF Carrier Audit Findings

Date: 2026-09-16
Authoritative run: `34995809847`
Artifact: `oure-stage8l-within-exposure-carrier-audit-34995809847`
Artifact digest: `sha256:d75405253bcddf894700a0add1ada183937fb3cb1e4d35bc24a9acb226e9d9ac`
Status: frozen historical carrier audit

## Method
Two frozen base compositions were used so carrier conclusions would not depend on the unresolved 159981 energy-chemical decision:
- Base A `BASE_FIX13_HKDIV`: Fix15 minus 159825/159981/513920 plus 513530.
- Base B `BASE_FIX14_HKDIV_ENCHEM`: Base A plus 159981.

Primary evidence is matched-availability: incumbent base and candidate replacement both restart on the candidate's 26th actual trading session. No pre-listing proxy is used. Frozen robust-dominance rule requires positive cumulative delta in both bases, block wins >= losses in both bases, and MDD not worse by more than 2pp in either base.

Candidate counts: CHINEXT_STANDARD 12, GOLD_SPOT 14, HK_DIVIDEND_ROLE 11, NASDAQ100 11, US_BIOTECH_ROLE 2.

## Strong exact-exposure findings

### 1. GOLD_SPOT: 159934 is the strongest robust replacement for 518880
`159934 易方达黄金ETF` is a strict same-exposure candidate and has OLS-ready history from 2014-01-21.

Matched from 2015 common engine start:
- Base A cumulative: 4041.25% -> 4494.24%, delta +452.99pp; MDD improves from -34.78% to -34.58%; turnover +2 sides.
- Base B cumulative: 4188.79% -> 4623.60%, delta +434.82pp; MDD improves from -38.64% to -38.45%; turnover unchanged.
- Aggregated yearly breadth across both bases: 14 better / 10 worse.
- 126-session blocks: 20 better / 16 worse / 10 tied.
- Mean matched log-wealth advantage: +0.1002.

Other gold candidates also robustly dominate 518880 under the frozen rule: 518850, 518660, 518860, 159831, 518600. However 159934 has the strongest mean matched log-wealth advantage and the longest useful history among the robust alternatives.

Conclusion: 518880 is not historically the best OLS carrier for the frozen GOLD_SPOT exposure. `159934` is the strongest frozen replacement candidate.

### 2. CHINEXT_STANDARD: 159957 is the strongest robust replacement for 159915
`159957 华夏创业板ETF` is a strict standard-ChiNext candidate, OLS-ready from 2018-02-08.

Matched since 2018-02-08:
- Base A: +2842.56% -> +3883.96%, delta +1041.40pp; MDD only 0.14pp worse; turnover -4 sides.
- Base B: +2947.39% -> +4019.75%, delta +1072.35pp; MDD only 0.14pp worse; turnover -2 sides.
- Years across both bases: 12 better / 6 worse.
- 126-session blocks: 20 better / 12 worse / 2 tied.
- Mean matched log-wealth advantage: +0.3023, the strongest result in Stage8L.

159810, 159971 and 159964 also pass the frozen robust-dominance rule. 159958 has very large positive return delta but fails the frozen block-consistency gate, so it is not promoted.

Full-history permanent replacement with 159957 is lower than the incumbent base because 159957 did not exist before 2018 while 159915 did. This is why the matched-availability result is the relevant carrier evidence for current selection.

Conclusion: conditional on using a standard 创业板指数 ETF today, `159957` is the strongest frozen historical carrier candidate among tested products; 159915 is not historically optimal for this OLS system.

## More tentative exact-exposure finding

### NASDAQ100: 159660 and 159632 pass the historical gate, but evidence is short and QDII implementation risk matters
`159660 汇添富纳斯达克100ETF` passes the frozen robust-dominance rule from 2023-05-25:
- Base A matched delta +17.76pp, MDD improves about 4.09pp; blocks 5 better /1 worse /1 tied.
- Base B matched delta +22.41pp, MDD improves about 7.95pp; blocks 5 better /1 worse /1 tied.
- Mean matched log-wealth advantage +0.0212.

`159632 纳斯达克ETF华安` also passes, but with smaller return advantage (+2.09pp to +9.90pp depending base), while MDD improves materially.

`159941 广发纳指ETF` has a much larger historical matched return gain but fails the preregistered robustness rule because block breadth is 9 better /11 worse per base and Base A MDD worsens by about 3.45pp.

Important implementation caveat: the daily OLS carrier audit uses secondary-market ETF prices, not point-in-time NAV/premium-adjusted returns. NASDAQ100 products are QDII ETFs and can experience material premium/discount episodes. Therefore 159660 should NOT be promoted directly from this experiment. A separate premium-adjusted execution audit is required before replacing 513100.

## Same-role sensitivity, not pure carrier replacement

### HK_DIVIDEND_ROLE
Only `159726 港股通高股息ETF华夏` robustly dominates 513530 under the frozen same-role test:
- matched delta +30.88pp in Base A and +24.98pp in Base B;
- MDD improves by about 0.62pp and 1.15pp;
- blocks 5 better /4 worse per base;
- mean matched log-wealth advantage +0.0219.

However 159726 and 513530 follow different dividend index methodologies. This is a change in economic sub-exposure, not merely an ETF carrier swap. Stage8J already froze 513530 after a separate role-repair experiment. Do not replace 513530 with 159726 based on Stage8L alone; report it as a future structural candidate only.

### US_BIOTECH_ROLE
`159502 标普生物科技ETF嘉实` does not dominate `513290 纳指生物科技ETF汇添富`:
- matched cumulative delta is negative in both bases (-80.68pp and -69.67pp);
- blocks 1 better /3 worse per base;
- MDD also worsens.

Conclusion: retain 513290 among the currently tested biotech-role alternatives.

## Frozen decision
Strongest carrier-level changes supported by Stage8L:
1. `518880 -> 159934` for GOLD_SPOT: strong, long-history, strict same exposure.
2. `159915 -> 159957` for standard ChiNext: strong matched-availability evidence, strict same exposure, but starts only in 2018.

Candidate only / not yet promoted:
3. `513100 -> 159660` NASDAQ100: historical gate passes, but short history and QDII premium risk require a separate premium-adjusted audit.
4. `513530 -> 159726` HK dividend: same-role rather than same-index; do not promote from this carrier audit.

No replacement supported:
5. Keep `513290` vs tested biotech alternative.

## Anti-overfit note
Do not combine the strongest one-at-a-time replacements and call the result validated without a separately frozen combination test. Stage8L establishes marginal carrier evidence only.
