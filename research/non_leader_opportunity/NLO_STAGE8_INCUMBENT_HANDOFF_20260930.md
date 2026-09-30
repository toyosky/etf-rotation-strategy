# NLO Stage 8 — Incumbent Weakening × Transition Challenger Handoff

Date: 2026-09-30

Status: exploratory handoff study; no production-rule change.

## Question

Can the new transition signal be used not as a standalone entry, but as a replacement candidate when the current raw OLS Top1 appears mature or weakening?

Explored incumbent deterioration proxies:
- Top1 age / consecutive leadership days
- 3-session raw-score weakening
- current score below its own recent 5-session peak
- Top1–Top2 gap narrowing over 3 sessions

Transition challenger:
- non-Top1 asset
- annualized > 0
- zero-axis crossing occurred within the previous 0–3 sessions
- R² has rebuilt over the previous 3 sessions
- choose the highest raw-score eligible transition challenger for comparison

Comparator:
- current raw OLS Top1
- separate cash comparator: 511220

## 1. Age + score weakening does not create a robust early-switch edge

When a transition challenger exists, conditioning on incumbent age terciles and incumbent 3-session score decline does not produce a stable candidate advantage over the current Top1.

Examples:

### 2021–2024
Oldest-age + weakening incumbent:
- candidate minus incumbent future20: approximately 0
- beat-incumbent rate: ~50.8%

Middle-age + weakening:
- future20 excess: approximately 0
- beat rate: ~57%, but no robust mean edge

### 2025–2026
Oldest-age + weakening:
- future20 excess: -2.59 pct
- beat rate: 50%

Middle-age + weakening:
- future20 excess: -0.22 pct
- beat rate: 44%

Conclusion:
Top1 age and raw score decline are insufficient handoff triggers.

## 2. Normalized score drawdown + gap narrowing also does not justify direct switching

Incumbent weakening redefined more robustly as:
- current raw score below own trailing 5-session score peak
- Top1 minus Top2 gap is narrower than three sessions earlier

When both conditions are true:

### 2021–2024
Transition challenger vs incumbent:
- average future20 excess: -0.23 pct
- median excess: +0.32 pct
- challenger beats incumbent: 51.8%

### 2025–2026
- average future20 excess: -2.71 pct
- median excess: -1.16 pct
- challenger beats incumbent: 46.8%

This is not a stable switching edge.

## 3. Apparent incumbent weakening does not imply stop-profit to cash

Compare the incumbent against 511220 after the same "weakening" states.

The major finding is that old/weakening Top1 leaders often continue to outperform cash, especially in 2025–2026.

Examples in 2025–2026:

Score below 5d peak + gap narrowing + middle age (~6 sessions):
- incumbent future20: +3.83%
- 511220 future20: +0.07%
- excess vs cash: +3.76%

Score below peak + gap narrowing + old age (~18 sessions):
- incumbent future20: +11.88%
- 511220: +0.12%
- excess: +11.76%

Thus "old + off peak + narrowing leadership gap" can occur during powerful persistent trends.

Leadership age is not a reliable stop-profit signal.

## 4. Interpretation

The correct decision problem is a relative handoff state machine, but incumbent deterioration must be defined structurally, not by age alone.

Current evidence separates three concepts:

### Challenger maturity
Useful diagnostic:
- recent negative-to-positive annualized crossing
- rapid R² rebuild
- optional price/volume confirmation

This answers:
"Is the challenger becoming a real trend?"

### Incumbent maturity / age
Not sufficient:
- long Top1 life
- score below recent peak
- gap narrowing

These do not reliably answer:
"Is the incumbent finished?"

### Capital handoff
Requires stronger incumbent invalidation plus challenger maturity.

A reasonable architecture for future testing is:

1. INCUMBENT_HEALTHY
   - keep incumbent even if challenger is rebuilding

2. INCUMBENT_WEAKENING_BUT_VALID
   - no automatic switch
   - challenger enters watch/standby state

3. INCUMBENT_STRUCTURALLY_INVALID
   - e.g. annualized loses positive sign, R² collapses in a positive-trend incumbent, production invalidation/D2/risk rule triggers
   - then evaluate mature challenger as replacement

4. NO_MATURE_CHALLENGER
   - route to cash/defensive asset rather than force a replacement

## Decision

Do not add:
- Top1 age stop-profit
- score-drawdown stop-profit
- gap-narrowing stop-profit
- direct switch to a transition challenger

The next useful study is to define incumbent structural invalidation using the same annualized/R² decomposition that worked for challenger-state diagnosis, and then test:

> incumbent trend breakdown + challenger trend rebuild

as a true handoff event.

This is more economically coherent than "old Top1 + new candidate".
