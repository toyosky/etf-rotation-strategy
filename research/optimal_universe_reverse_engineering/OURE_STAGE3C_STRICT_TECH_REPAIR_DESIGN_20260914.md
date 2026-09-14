# OURE Stage3C — Strict Exposure-Disjoint Mechanical Repair

Date: 2026-09-14
Parent: Stage3B run 34809905970

## Why this repair exists

Stage3B successfully broadened the exclusion taxonomy and raised the search cardinality cap, but post-run audit found two mechanical boundary failures:

1. The stated broad technology-chain veto omitted explicit software / artificial-intelligence / big-data labels, allowing `CHINA_SOFTWARE_AI` members into the Stage3B champion.
2. The Stage3B champion again landed exactly at the configured maximum (`30` non-cash members), so the search had not demonstrated an interior optimum.

Stage3B is retained as an auditable failed replication attempt. Its numerical result is not promoted as proof of exposure-disjoint replication.

## Frozen research semantics

No change to:
- historical sample;
- frozen OLS feature/ranking semantics;
- transaction costs;
- hindsight static-Universe objective;
- cash proxy `511220`;
- Stage3/3B search mechanics except for the two repairs below;
- Stage2 architecture features remain excluded from the search objective.

## Mechanical repairs only

### Technology-chain exclusion completion

In addition to the Stage3B terms, reject rows whose name/metadata contain any of:
- `SOFTWARE`
- `ARTIFICIAL_INTELLIGENCE`
- `INTELLIGENCE`
- `BIG_DATA`
- `BIGDATA`
- `CLOUD_COMPUTING`
- `软件`
- `人工智能`
- `大数据`
- `云计算`
- `计算机`

This closes the observed `CHINA_SOFTWARE_AI` leakage without using return information.

### Cardinality boundary repair

Raise `MAX_NONCASH` from 30 to 60. This does not assert that K=60 is desirable; it only tests whether the search naturally stops before the boundary. If the champion again lands at K=60, cardinality remains unresolved and must not be interpreted as optimal.

## Acceptance gate

Stage3C counts as a valid exposure-disjoint replication sample only if:
1. champion and elites pass the completed broad-exposure exclusion audit;
2. champion does not rely on a forbidden exposure leakage;
3. champion is not merely an unacknowledged boundary optimum; if it lands on K=60, report the boundary failure explicitly;
4. the frozen OLS value is materially above same-K random controls.

Only after this gate may the result enter the planned three-group architecture comparison.
