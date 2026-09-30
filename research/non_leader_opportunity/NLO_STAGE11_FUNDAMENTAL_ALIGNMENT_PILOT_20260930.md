# NLO Stage 11 — Fundamental Alignment Pilot

Date: 2026-09-30

Status: manual event audit; exploratory only; no production-rule change.

## Objective

Test whether contemporaneously available fundamental/news information helps distinguish what happens *after* an OLS trend-establishment / stabilization event.

Assets:
- 159934 Gold ETF
- 501018 Crude Oil LOF
- 159981 Energy & Chemical Futures ETF
- 513290 Nasdaq Biotechnology ETF
- 161226 Silver LOF retained only as secondary reference

OLS event definition:
- annualized crosses from <=0 to >0
- inspect R² rebuild over t+1 to t+3
- subsequent returns are from internal daily-bar database

Important:
- Fundamental judgement uses only information that was public at or immediately around the event date.
- Later reports are used only as ex-post confirmation, not as contemporaneous inputs.

## Event audit

### 1. 501018 — 2026-06-10: false stabilization

OLS:
- annual t0 +1.6%
- R² t0 ~0
- t+1 R² 0.034
- t+3 annual back to -14.3%
- fwd5 -10.5%
- fwd10 -26.0%
- fwd20 -13.0%

Contemporaneous fundamentals:
- EIA June 9 STEO cut 2026 global oil-demand expectations.
- EIA said high fuel prices, reduced availability and government measures were curbing consumption, particularly in Asia.
- EIA explicitly said weaker demand could limit price increases caused by Hormuz disruptions.

Assessment: FUNDAMENTAL DIVERGENCE.
The price-level stabilization occurred against a demand backdrop that did not support a durable oil trend.

Source:
https://www.eia.gov/pressroom/releases/press589.php

### 2. 159981 — 2026-06-08: false/weak establishment

OLS:
- annual t0 +1.0%
- R² t0 ~0
- R² t+3 0.126
- annual t+3 +33.1%
- fwd5 -8.3%
- fwd10 -13.6%
- fwd20 -16.6%

Fundamental backdrop:
- June EIA demand downgrade was a major upstream headwind.
- China methanol fundamentals entering June were not cleanly bullish: domestic supply remained high and demand had been weak; the market expected inventories to bottom mainly because of maintenance and lower supply pressure rather than broad demand expansion.

Assessment: WEAK / MIXED FUNDAMENTAL SUPPORT.
Price structure improved briefly, but broad demand confirmation was absent.

Sources:
https://www.eia.gov/pressroom/releases/press589.php
https://en.oilchem.net/26-0515-08-aee6129b57bb6db5.html

### 3. 501018 — 2026-07-13: short-term bullish, medium-term bearish

OLS:
- annual t0 +30.2%
- R² t0 0.0045
- R² t+3 0.257
- annual t+3 +808.5%
- fwd5 +9.0%
- fwd10 +1.1%
- fwd20 -6.4%

Contemporaneous fundamentals:
- July 14 Brent curve moved into strong backwardation on acute supply risk and reduced tanker flows.
- But EIA July 7 expected reopening of Hormuz to restore production/trade flows and expected the market to return to oversupply after the Q3 adjustment.
- EIA forecast inventory builds in Q4 2026 and 2027.

Assessment: SHORT-TERM FUNDAMENTAL CONFIRMATION, MEDIUM-TERM DIVERGENCE.
This matches the realized path unusually well: sharp initial gain, then fade.

Sources:
https://www.reuters.com/business/energy/brent-oil-structure-changes-reflect-mounting-supply-risk-iran-tensions-flare-2026-07-14/
https://www.eia.gov/pressroom/releases/press590.php
https://www.eia.gov/outlooks/steo/pdf/steo_text.pdf

### 4. 159981 — 2026-08-13: strong aligned establishment

OLS:
- annual t0 ~0
- R² t0 ~0
- R² t+3 0.251
- annual t+3 +63.1%
- fwd5 +4.0%
- fwd10 +1.3%
- fwd20 +17.9%

Contemporaneous fundamentals:
- Oil jumped sharply around Aug 9 as U.S.-Iran tensions worsened and hopes of reopening Hormuz faded.
- EIA Aug 11 increased estimates of Middle East shut-in crude production because transit constraints remained severe.
- Methanol data around Aug 13 showed producer inventories down ~4.7%, port inventories down ~13.4%, arrivals down ~62.9%; MTO restart expectations were improving demand expectations.
- Supply-side tightness was therefore visible both upstream and in a key chemical-chain component.

Assessment: STRONG FUNDAMENTAL ALIGNMENT.

Sources:
https://www.reuters.com/business/energy/oil-rises-uncertainty-continues-over-reopening-strait-2026-08-09/
https://www.eia.gov/pressroom/releases/press591.php
https://www.linkedin.com/pulse/20260814-methanol-pta-px-citic-futures-vbwqc
https://cnc.ccfgroup.com/newscenter/newsview.php?Class_ID=D00000&Info_ID=2026081930034

### 5. 501018 — 2026-09-03: aligned physical-market tightness

OLS:
- annual t0 +7.0%
- R² t0 0.0028
- R² t+3 0.321
- annual t+3 +130.1%
- fwd5 +6.3%
- fwd10 +7.4%
- fwd20 unavailable as of Sep 30

Information available around the event:
- Sep 2 Reuters reported the sharpest U.S.-Iran exchange since July and reduced tanker traffic through Hormuz.
- U.S. crude inventories had fallen by 4.5 million barrels, more than expected.
- European gasoline and diesel refining margins were near record/high levels because of constrained global fuel supply.

Assessment: STRONG FUNDAMENTAL ALIGNMENT.
The physical market—not only headlines—was visibly tight.

Sources:
https://www.reuters.com/business/energy/oil-up-nearly-1-us-iran-trade-fresh-strikes-2026-09-02/
https://www.reuters.com/business/energy/european-refiners-reaping-near-record-profits-gasoline-2026-09-02/

### 6. 159934 — 2026-08-05: successful gold stabilization

OLS:
- annual t0 +6.9%
- R² t0 0.017
- R² t+1 0.147
- R² t+3 0.434
- annual t+3 +117.7%
- fwd5 +5.2%
- fwd10 +3.7%
- fwd20 +3.0%

Contemporaneous fundamentals:
- Treasury yields fell and the U.S. dollar softened.
- Weaker labor data reduced expectations of additional near-term tightening.
- Gold broke upward from a multi-month technical wedge.
- World Gold Council later documented that August became one of gold's strongest months in decades, driven especially by ETF/futures flows and a weaker dollar.
- Central-bank demand strengthened later in August.

Important nuance:
- At the exact Aug 5 turn, structural demand confirmation was not uniformly strong: H1 central-bank demand had been weak and Q2 ETF flows had been negative.
- The macro price drivers turned first; stronger flow confirmation accumulated afterwards.

Assessment: EARLY MACRO ALIGNMENT, THEN FUNDAMENTAL/FLOW CONFIRMATION.

Sources:
https://www.reuters.com/world/india/gold-ticks-up-softer-dollar-focus-us-jobs-data-2026-08-05/
https://www.gold.org/goldhub/gold-focus/2026/08/weekly-markets-monitor-unwedged
https://www.gold.org/goldhub/research/gold-market-commentary-august-2026
https://www.reuters.com/commentary/reuters-open-interest/central-banks-spearhead-renewed-gold-rush-2026-08-13/

### 7. 513290 — 2026-06-01: first flip, not a true establishment

OLS:
- annual t0 +8.8%
- R² t0 0.018
- R² t+1 fell to 0.001
- annual t+3 returned to -22.1%
- fwd5 -3.4%
- fwd10 -1.4%
- fwd20 +11.5%

Interpretation:
The +20d return is misleading if treated as one continuous signal. The first June 1 crossing structurally failed; a second crossing occurred June 16.

Contemporaneous backdrop:
- Broad U.S. equities were strong, but rate/inflation uncertainty remained.
- Healthcare/biotech capital-market evidence was still mixed; June 2 commentary described IPO conditions as volatile.
- Stronger sector confirmation arrived later through M&A and successful biotech IPOs.

Assessment: NO CLEAN FUNDAMENTAL CONFIRMATION AT FIRST CROSS.
The later positive 20d return belongs economically to a subsequent establishment event.

Sources:
https://www.reuters.com/business/wall-st-futures-steady-investors-await-mideast-deal-updates-dell-soars-2026-05-29/
https://www.reuters.com/legal/litigation/gic-backed-asia-healthcare-eyes-ipo-within-12-18-months-cautious-market-2026-06-02/

### 8. 513290 — 2026-06-16: successful establishment

OLS:
- annual t0 ~0
- R² t0 ~0
- R² t+3 0.218
- annual t+3 +34.2%
- fwd5 +4.1%
- fwd10 +12.3%
- fwd20 +12.3%

Contemporaneous/near-contemporaneous sector information:
- J&J announced a $1bn acquisition of Firefly Bio on June 8.
- Kardigan completed an upsized $400m biotech IPO on June 18; shares opened ~31% above the offer price.
- Reuters explicitly described the IPO as evidence of renewed investor appetite and an improving biotech IPO window.

Assessment: FUNDAMENTAL/CAPITAL-MARKET ALIGNMENT.
This is a cleaner example of price trend establishment occurring alongside reopening capital markets and strategic M&A.

Sources:
https://www.reuters.com/business/healthcare-pharmaceuticals/johnson-johnson-buy-firefly-bio-1-billion-2026-06-08/
https://www.reuters.com/business/healthcare-pharmaceuticals/kardigan-rises-nasdaq-debut-after-upsized-400-million-ipo-2026-06-18/

### 9. 513290 — 2026-08-10: strong sector confirmation

OLS:
- annual t0 +18.6%
- R² t0 0.027
- R² t+1 0.140
- R² t+3 0.427
- annual t+3 +118.6%
- fwd5 -1.2%
- fwd10 +7.7%
- fwd20 +6.4%

Contemporaneous fundamentals:
- Reuters Aug 5 reported U.S. healthcare stocks up 11.2% over three months vs 6% for the S&P 500.
- Healthcare funds received $2.44bn inflows in July after $1.5bn in June.
- 2026 healthcare M&A value was nearing $284bn.
- Earnings expectations were improving into late 2026/2027 and valuations were still viewed as attractive.

Assessment: STRONG SECTOR FUNDAMENTAL/FLOW ALIGNMENT.

Source:
https://www.reuters.com/business/finance/wall-street-warms-healthcare-stocks-tech-trade-faces-turbulence-2026-08-05/

### 10. 513290 — 2026-09-29: live unresolved case

OLS:
- annual crossed positive to +14.1%
- R² only 0.019
- no post-cross R² rebuild data yet

Current sector backdrop:
Positive micro/industry signals:
- AstraZeneca announced a $2bn investment/collaboration with Summit.
- ADARx had a strong upsized Nasdaq IPO.
- Multiple biotech IPO filings and licensing/M&A activity show functioning capital markets.

Negative macro/idiosyncratic signals:
- U.S. Treasury yields are near multi-decade highs and policy expectations remain hawkish, a valuation headwind for long-duration biotech.
- UniQure fell sharply on disappointing trial data, illustrating continued high clinical-event risk.
- broader Big Pharma R&D returns/patent-cliff economics remain challenging.

Assessment: MIXED FUNDAMENTALS.
The price signal has not yet reached the "R² rebuilt" stage. This should remain a live observation rather than a buy conclusion.

Sources:
https://www.reuters.com/legal/litigation/summit-soars-after-2-billion-investment-astrazeneca-cancer-therapies-2026-09-29/
https://www.reuters.com/legal/litigation/adarx-pharmaceuticals-raises-4463-million-upsized-us-ipo-2026-09-25/
https://www.reuters.com/business/us-stock-futures-flat-tech-bounce-meets-crude-driven-caution-2026-09-29/
https://www.reuters.com/business/healthcare-pharmaceuticals/uniqures-huntingtons-therapy-fails-significantly-slow-disease-progression-trial-2026-09-29/

## Pilot conclusion

The small recent-month case sample is directionally consistent with a useful second-layer audit:

1. PRICE SIGNAL + FUNDAMENTAL DIVERGENCE
   - examples: June crude / June energy-chemical
   - tends to fail quickly or reverse

2. PRICE SIGNAL + SHORT-TERM FUNDAMENTALS ONLY
   - example: July crude
   - can produce an initial rally but poor medium-horizon continuation

3. PRICE SIGNAL + PHYSICAL / FLOW / CAPITAL-MARKET ALIGNMENT
   - examples: Aug energy-chemical, Sep crude, Aug gold, Jun/Aug biotech
   - more often followed by durable continuation

This is not a statistical proof:
- sample is very small;
- the fundamental classification is partly qualitative;
- different asset classes require different driver maps;
- public information availability/timestamps must be enforced rigorously.

However, the cases support continuing the project as a formal "Fundamental Alignment Audit" rather than a generic news-sentiment model.

Recommended next design:
- predefine driver maps by asset;
- score only information available as of event time;
- classify ALIGN / MIXED / DIVERGE without using future return;
- accumulate prospective events;
- test whether alignment predicts 10/20d return, trend lifespan, MFE and MAE.
