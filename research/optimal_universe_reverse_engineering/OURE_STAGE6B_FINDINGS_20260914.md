# OURE Stage6B — 2022–2024 Good-Universe Traits Findings

Date: 2026-09-14
Run: `34848320084`
Status: frozen explanatory layer-1
Scope: exact Fix15 14-risk subset lattice only; cash 511220 always retained.

## Exact frontier
Across all 16,384 subsets, the exact 2022–2024 champion inside the Fix15 lattice is K=7 including cash:
`511220,159509,159915,159985,513100,513290,513920`
with total return `+267.93%`.

The best-by-K frontier rises sharply through K7 and then plateaus/declines:
K2 +62.52%, K3 +130.07%, K4 +217.72%, K5 +227.86%, K6 +253.55%, K7 +267.93%, K8 +264.55%, K9 +265.94%, K10 +249.69%, K15(full Fix15) +74.54%.
This is exact only within the Fix15 subset lattice.

## Strong identity-free traits, controlling nominal K
Within each K, high-return 2022–24 subsets show a strong persistence / low-harmful-competition architecture.

Strongest associations with within-K return rank:
- mean Top1 tenure: corr `+0.638`; top-decile mean `8.60d` vs bottom `6.62d`; SMD `+1.56`.
- leader switch rate: corr `-0.632`; top `12.19%` vs bottom `15.48%`; SMD `-1.62`.
- median Top1 tenure: corr `+0.413`; top `5.24d` vs bottom `3.93d`.
- short-run <=2d share: corr `-0.373`; top `26.82%` vs bottom `33.56%`.
- leader HHI: corr `+0.335`; good sets have somewhat more concentrated leadership.
- max pair trend Jaccard: corr `-0.279`; top `0.504` vs bottom `0.549`.
- mean member trend episode length: corr `+0.274`; top `17.41d` vs bottom `15.94d`.
- mean eligible count: corr `-0.232`; top `2.93` vs bottom `3.15`.
- coverage efficiency: corr `+0.215`.
- mean competitors when covered: corr `-0.215`.
- mean pair trend Jaccard: corr `-0.207`.
- absolute coverage share itself is slightly lower in good sets: corr `-0.203`; top `0.930` vs bottom `0.942`.

Interpretation: in 2022–24, good Universes did not maximize raw opportunity coverage. They accepted slightly less coverage in exchange for fewer simultaneous eligible competitors, less trend overlap, fewer rank switches, and longer leader persistence. The dominant trait is controlled competition, not breadth.

## Member-level descriptive traits
Banzhaf-style mean marginal log contribution over all subset contexts:
- 159985 `+0.2473`, positive in 99.71% of contexts; top-1% inclusion 97.56%.
- 513100 `+0.2100`, positive 91.97%; top-1% inclusion 93.29%.
- 159915 `+0.1878`, positive 93.53%; top-1% inclusion 98.78%.
- 159509 `+0.1296`, positive 98.52%; top-1% inclusion 75.61%.
- 513920 `+0.0959`, positive 89.12%; top-1% inclusion 62.20%.

Strong negative average contributors:
- 518880 `-0.1859`; top-1% inclusion 3.66%.
- 159825 `-0.2098`; positive marginal share only 1.44%; top-1% inclusion 0%.

513290 is noteworthy: average Banzhaf marginal is negative (`-0.0536`) yet it appears in the exact champion. This is direct evidence that set interactions matter; standalone/context-average quality is not sufficient to construct the best Universe.

## Contrast with 2025–26 inside the same lattice
The strong 2022–24 persistence signatures largely disappear or reverse in 2025–26. For example mean Top1 tenure within-K rank correlation falls from `+0.638` to about `-0.030`; leader switch-rate association moves from `-0.632` to about `+0.044`.

This supports Stage6's regime interpretation: 2022–24 good Universes are primarily persistence / controlled-competition structures, while the later period cannot be described by the same architecture.

## Frozen interpretation and limitation
Within the exact Fix15 lattice, 2022–24 had a very clear good-Universe signature:
`longer leader persistence + fewer switches + fewer short-lived leaders + lower trend overlap + fewer simultaneous competitors`, even after controlling for K.

This does NOT yet prove the same signature across the full ETF market because Fix15 itself was historically curated. Member identities are hindsight descriptions, not admissible X<=t rules. A full-market external replication is required before promoting persistence architecture as a general 2022–24 mechanism.