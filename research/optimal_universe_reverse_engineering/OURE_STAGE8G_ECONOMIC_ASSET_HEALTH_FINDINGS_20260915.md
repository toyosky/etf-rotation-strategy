# OURE Stage8G — Economic Asset Health Findings

Date: 2026-09-15
Authoritative run: `34954293589`
Artifact: `oure-stage8g-economic-asset-health-34954293589`
Status: frozen historical diagnostic

## Method
Stage8G reused the pre-existing Asset Health V1 idea without retuning its health thresholds. It rebuilt the frozen Stage8E Economic Coverage path, then for every mature Economic Coverage Top1 day computed own-trading-day forward 5d/10d close returns and the frozen near-high state (within 0.5% of the prior 20-session closing high). The original V1 WARNING/WATCH/HEALTHY logic was applied at economic-slot and representative-symbol levels. Episode-first results were reported separately as dedup robustness and were not used to tune a new threshold.

Historical control from the original Asset Health monitor: `159825` had 28 Top1 events, mean fwd5 -2.66%, mean fwd10 -3.53%, 5d/10d win rate 21.4%; 12 near-high Top1 events had fwd10 mean -3.53% and win rate 16.7%, producing WARNING. This is a substantially stronger failure pattern than most current Stage8E economic representatives.

Stage8G contains 1,362 mature daily Top1 events and 321 episode starts; mature cutoff 2026-08-31. Slot V1 status counts: 9 HEALTHY, 6 WATCH, 11 INSUFFICIENT_DATA, 0 WARNING.

## Frozen slot-level WATCH set
- JAPAN
- EUROPE
- GLOBAL_RESOURCE_EQUITY
- CN_INDUSTRIAL_DEFENSE
- AGRICULTURE
- US_BIOTECH

These WATCH labels are not equally strong once episode-first robustness is considered.

## Strongest concerns
### 1. CN_FINANCIALS — high-priority structural review despite INSUFFICIENT_DATA status
Formal V1 status is INSUFFICIENT_DATA only because recent-2y near-high n=3 (<5). Historical behavior is unusually poor:
- 50 Top1 days: fwd10 mean -2.94%, win rate 12.0%.
- 17 near-high Top1 days: fwd10 mean -3.80%, win rate 5.9%.
- 12 episode starts: fwd10 mean -2.92%, win rate 25.0%.
This is one of the clearest candidates for a preregistered slot-removal/replacement counterfactual.

### 2. CN_HEALTHCARE — high-priority structural review despite INSUFFICIENT_DATA
Formal V1 recent sample is only n=4. Historical evidence is consistently poor:
- 43 Top1 days: fwd10 mean -1.92%, win rate 27.9%.
- 16 near-high Top1 days: fwd10 mean -3.89%, win rate 6.3%.
- 13 episode starts: fwd10 mean -2.36%, win rate 23.1%.
This also looks more like slot-level poor OLS suitability than a near-high-only issue.

### 3. CN_VALUE_DEFENSIVE — high-priority structural review despite INSUFFICIENT_DATA
- 32 Top1 days: fwd10 mean -2.22%, win rate 15.6%.
- 17 near-high Top1 days: fwd10 mean -2.00%, win rate 17.6%.
- 8 episode starts: fwd10 mean -0.73%, win rate 12.5%.
Recent-2y near-high n=3 prevents formal WATCH, but the historical hit rate is poor.

### 4. CN_CONSUMER — review candidate
- 20 Top1 days: fwd10 mean -0.64%, win rate 40.0%.
- 7 near-high Top1 days: fwd10 mean -3.00%, win rate 14.3%.
- 5 episode starts: fwd10 mean -1.75%, win rate 40.0%.
Evidence is weaker than the three above but directionally concerning.

## Formal WATCH slots with meaningful robustness
### EUROPE
Mostly represented by 513030 Germany ETF.
- 58 Top1 days: fwd10 +0.72%, win 56.9% overall.
- 28 near-high days: fwd10 -0.53%.
- recent-2y near-high n=7: fwd10 -4.82%, win 0%.
- 11 episode starts: fwd10 -0.30%; 5 near-high episode starts: -3.42%, win 20%.
Interpretation: not generally bad, but high-state continuation has deteriorated materially; replacement/removal should be tested rather than assumed.

### AGRICULTURE
This slot is direct soymeal `159985`, not the old agriculture-equity `159825`.
- 86 Top1 days: fwd10 +0.90%, win 55.8% overall.
- 39 near-high days: fwd10 -0.20%, win 38.5%.
- recent-2y near-high n=10: fwd10 -2.28%, win 10%.
- 13 episode starts: fwd10 -0.17%; near-high episode starts -0.47%.
Interpretation: 159985 is not a repeat of the old 159825 failure. Its general Top1 behavior is positive; the issue is specifically recent near-high continuation/exhaustion. Treat as conditional entry-quality concern, not immediate slot deletion.

## Representative-level problems hidden by healthier slot history
### 562500 Robot ETF — WARNING
Within CN_INDUSTRIAL_DEFENSE, `562500` alone triggers formal WARNING:
- 19 Top1 days: fwd10 +0.49%, win 42.1%.
- 10 near-high days, all recent: fwd10 -0.58%, win 30%.
- 5 episode starts: fwd10 -2.15%, win 20%.
The broader CN_INDUSTRIAL_DEFENSE slot is only WATCH and its episode-level behavior is positive because older representatives (defense/new-energy) were different. This points to representative-selection quality, not necessarily deletion of the whole economic slot.

### 512480 Semiconductor ETF — WATCH while CN_TECH_DIGITAL slot is HEALTHY
- 76 Top1 days: fwd10 -0.63%, win 39.5%.
- 41 near-high days: fwd10 -1.76%, win 29.3%.
- 18 episode starts: fwd10 +0.21%, win 55.6%.
This is mixed: repeated daily states are poor, but independent episodes are not. Do not delete from daily-state evidence alone.

## WATCH labels weakened by episode-first robustness
JAPAN (513520) has daily V1 WATCH, but 12 independent episode starts have fwd10 +0.70% and 58.3% win; its near-high episode-start result is also positive. GLOBAL_RESOURCE_EQUITY similarly has positive episode-start fwd10 (+0.94%, 54.5% win). CN_INDUSTRIAL_DEFENSE slot overall also has positive episode-start behavior. These should not be treated as strong deletion candidates from daily-counted V1 status alone.

US_BIOTECH is WATCH but has only 5 episode starts. Evidence is too small for structural exclusion.

## Healthy reference slots
Direct commodity and major global-beta tools remain strong under this audit: GOLD, SILVER, CRUDE_OIL, US_BROAD, US_GROWTH_TECH, CN_GROWTH_BETA and HK_OFFSHORE_BROAD_VALUE are HEALTHY under frozen V1. SILVER and CRUDE_OIL in particular show strong positive all-Top1 continuation, consistent with the economic-optionality rationale for retaining them.

## Decision
Stage8G supports using Asset Health as a second filter on Economic Coverage, but it does not justify deleting all WATCH slots.

Next clean experiment should be single-variable counterfactuals, prioritized as:
1. remove/replace CN_FINANCIALS;
2. remove/replace CN_HEALTHCARE;
3. remove/replace CN_VALUE_DEFENSIVE;
4. test CN_CONSUMER;
5. test representative substitution for 562500 inside CN_INDUSTRIAL_DEFENSE;
6. separately test EUROPE and the recent near-high AGRICULTURE issue.

Each experiment must hold the other 26-slot structure, OLS engine, execution and costs fixed. This is necessary because the original 159825 lesson was diagnostic; deletion only becomes justified if the counterfactual portfolio improves robustly rather than merely because an asset looked bad ex post.
