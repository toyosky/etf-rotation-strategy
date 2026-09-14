# OURE Stage4B — K30 Pruning and Leader-Occupation Audit

Date: 2026-09-14
Status: preregistered mechanism audit

## Question
The Stage4 effective-competition audit shows that the large-K elite is not dominated by only a few permanent leaders: all 30 members lead at least once over the full sample and the effective leader count is about 13. But does this still hide removable passengers or a smaller high-value core?

## Frozen objects
- Small-K reference: exact Stage1 best K=7 including cash (6 risk assets + 511220).
- Large-K reference: exact Stage3B champion (30 risk assets + 511220).
- Frozen OLS, execution dates, costs and data semantics unchanged.

## Tests
1. Per-member Top1 occupation share, run count, first/last leader date and risk bucket for K6 and K30.
2. Exact deletion shells around K30:
   - all 30 single deletions;
   - all C(30,2)=435 double deletions;
   - all C(30,3)=4,060 triple deletions.
3. Greedy forced-pruning path from K30 down to K6: at each step delete the member whose removal leaves the highest downstream OLS log growth, even if every deletion is harmful.

## Interpretation
- If any 1/2/3 deletion improves K30, then the Stage3B local-optimum claim was too weak and K30 contains a locally removable interaction set.
- If none improves, the large-K elite is a genuine local basin at least through third-order deletions.
- A long flat forced-pruning path would still indicate redundancy even if no local deletion is profitable.
- A steep path indicates a true relay architecture where many low-frequency members contribute regime-specific opportunities.

No full-market search or feature fitting is permitted in this stage.
