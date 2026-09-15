# OURE Stage8E — Human Economic Coverage Universe

Date: 2026-09-15
Status: preregistered before any Stage8E return result is computed

## Question
Can a Universe built from ex-ante economic risk coverage outperform purely historical selection by preserving dormant but economically distinct tools before their regime becomes visible?

## Hard prohibitions
Economic membership logic MUST NOT use: historical return, OLS score magnitude, backtest contribution, Fix15 membership, Stage8A/8C outcome, or future target-block data. Fix15 is benchmark only.

Current metadata labels are used only as structural identity (name / asset class / region / underlying exposure). Historical availability is still point-in-time: an ETF can fill a slot only if it belongs to the same common eligible pool available at that decision date.

## Human-defined economic slots
These slots were frozen from economic drivers after inspecting metadata identity only, before running Stage8E returns.

China equity:
1. CN_BROAD_CORE — broad/large-cap A-share beta.
2. CN_MID_SMALL — mid/small/micro-cap beta.
3. CN_GROWTH_BETA — ChiNext/STAR/innovation-growth beta.
4. CN_TECH_DIGITAL — semiconductor/software/AI/IT/communications/digital/cyber/electronics/internet/TMT.
5. CN_HEALTHCARE — healthcare/pharma/TCM/vaccine/biotech.
6. CN_CONSUMER — consumer/brands/tourism/automotive.
7. CN_FINANCIALS — banks/securities/insurance/broad financials/real-estate financial beta.
8. CN_INDUSTRIAL_DEFENSE — advanced manufacturing/defense/aerospace/machinery/robotics/infrastructure/transport/power-grid/new-energy industrials.
9. CN_RESOURCES_ENERGY — mining/materials/rare-metals/energy/oil-gas/chemical/petrochemical/resources.
10. CN_VALUE_DEFENSIVE — dividend/value/SOE/utilities and defensive/fundamental factor equity.

Offshore China / Hong Kong:
11. HK_OFFSHORE_BROAD_VALUE — HK broad/H-share/dividend/SOE.
12. HK_OFFSHORE_GROWTH — HK tech/healthcare/consumer/new-economy plus offshore-China internet/education.

US:
13. US_BROAD — S&P 500/Dow/large-cap broad and broad consumer beta.
14. US_GROWTH_TECH — Nasdaq 100 / US technology.
15. US_BIOTECH — US biotechnology.

Other foreign equity:
16. JAPAN — Japan equity.
17. EUROPE — Germany/France equity.
18. EMERGING_EX_CHINA — India/Brazil/Saudi/Asia diversified.
19. GLOBAL_RESOURCE_EQUITY — listed commodity-producer equity exposure such as global/US oil-gas producers and gold miners; kept separate from direct commodity futures/spot products because of equity beta and operating leverage.

Direct commodities:
20. GOLD — physical/spot gold products, not gold miners.
21. SILVER — direct silver.
22. CRUDE_OIL — direct crude-oil commodity exposure.
23. AGRICULTURE — direct agricultural commodity exposure (currently soymeal).
24. INDUSTRIAL_COMMODITY — direct industrial/energy-chemical commodity exposure distinct from crude oil.

Fixed income:
25. GOV_DURATION — sovereign/local-government/policy-bank duration exposure.
26. CREDIT — corporate/credit/short-credit/tech-innovation credit exposure.
27. CONVERTIBLE — convertible bonds, retained separately because of equity convexity.

Cash proxy remains the frozen OLS cash comparator and does not consume a risky slot.

## Representative selection within each slot
At each 126-session Universe decision:
1. Start from the same point-in-time common eligible pool used by repaired Opportunity.
2. Map candidates to the frozen economic slots using structural metadata only.
3. Within each non-empty slot, select exactly one representative with the highest median trading amount over the immediately preceding 60 completed sessions; ties by symbol.
4. No return or OLS performance information is used for within-slot selection.
5. The resulting K is variable and equals the number of economically distinct slots that have an eligible historical representative.

## Frozen comparison
Same OOS calendar, frozen downstream OLS rule, next-open accounting and 6bp per-side cost:
- ECONOMIC_COVERAGE (primary Stage8E method)
- OLD_SAFE_K15 (repaired Opportunity)
- OLD_SAFE_K30 (repaired Opportunity)
- FIX15_BENCHMARK (benchmark only)

Report annual 2021–2026 partial returns, full compounded return, MDD, turnover, Top1 tenure, actual economic K by block, selected representatives by slot, and contribution/switch usage by slot.

## Interpretation rule
This is a structural hypothesis test, not a search for a best taxonomy. No slot may be added/deleted/merged after seeing Stage8E returns and then presented as the same test. Any redesign is a new stage.
