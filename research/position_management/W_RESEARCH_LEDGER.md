# W research ledger
W1/W2 first rounds completed in conversation; W3.1 conditional groups completed; W3a conditional incremental opportunity audit completed this run. W4-W6 pending. W1 historical downside/MAE and P-All pending. Premium10 PIT/minute execution not established; no production changes.
## W3a
Sources: prediction blob 3a93afe73e85448650ce0cd9f8c20ebe4b2bf304; baseline blob d373130b1ae56d6a3f60b22a7182c9ccfb5016d2. Join date and target, NON_VOID, risk set 159934,159985,161226,513100,159957,159509,513290,159529,159981,501018,513530,164824,511380,512800. 960 rows, warmup 60. Past 252 eligible observations, midrank ties. Stratify by score, vol, D/Dbase rank >=0.5 (8 cells). Compare pMfe5_full rank >=0.5 and separately full minus vol-only probability rank >=0. Within cell difference high minus low, require >=5 each, weight by smaller group size. No fitted parameters or future labels in grouping. Descriptive, not causal or independent OOS; overlapping labels. Results decimal returns:
```json
[
  {
    "scope": "all",
    "raw": {
      "n": 900,
      "matchedPerSide": 178,
      "cells": 5,
      "ret": 0.002046021397463264,
      "end": 0.005288519296597995,
      "mfe": 0.024015629729961283,
      "loss": 0.009973303931674726
    },
    "increment": {
      "n": 900,
      "matchedPerSide": 219,
      "cells": 6,
      "ret": -0.0005852196317700245,
      "end": -0.0038177056512239,
      "mfe": 0.00030104392061384094,
      "loss": 0.0036140763762986675
    }
  },
  {
    "scope": "ex26",
    "raw": {
      "n": 759,
      "matchedPerSide": 150,
      "cells": 5,
      "ret": 0.0013321025380126149,
      "end": 0.0008688590582298474,
      "mfe": 0.01465767810189978,
      "loss": 0.006349294074681905
    },
    "increment": {
      "n": 759,
      "matchedPerSide": 190,
      "cells": 6,
      "ret": -0.0020239701781267997,
      "end": -0.0005410933667090522,
      "mfe": 0.0021390215921713233,
      "loss": 0.004790637827377977
    }
  },
  {
    "scope": "exOilSilver",
    "raw": {
      "n": 712,
      "matchedPerSide": 140,
      "cells": 5,
      "ret": 0.0012836326417360678,
      "end": 0.0011604658621773686,
      "mfe": 0.01705753351511731,
      "loss": 0.006957143869269117
    },
    "increment": {
      "n": 712,
      "matchedPerSide": 190,
      "cells": 6,
      "ret": -0.0016529476349331352,
      "end": -0.0007982496338976154,
      "mfe": 0.0022405646217048413,
      "loss": 0.0037043485536120335
    }
  }
]
```
Next: W3a daily portfolio replay and block bootstrap; compare A/C and opportunity rank; avoid treating MFE as realized. P-All unavailable in this run.
## W3b
Completed daily open-proxy replay, 5pp band, 6/10bp, 1419 days, frozen routing, past-only 252 ranks, no future labels. F replaces Score rank with full opportunity rank, V with vol-only rank, I adds 0.25*(full rank-vol rank) to C. Fixed and C exposure matches and fixed volatility matches are ex-post attribution. See w3b_replay.mjs and w3b_results.json. Bootstrap 20-day circular blocks within years, 1200 replicates. Exclusions are attribution not rerouted backtests. Premium10 PIT, P-All and lot/minimum commission still pending. Next W4 unless W3b shows robust incremental evidence. No production change.

## W4a
W3b archived: F/V/I all lower CAGR than exposure-matched C at both fees; close opportunity branch for now. W4a executed center vs edge no-trade bands 0/5/10pp for A/C, 6/10bp, matched center/fixed exposure and fixed volatility, 20-day paired bootstrap. See w4a_execution.mjs and w4a_results.json. Continuous shares/open proxy, no minimum commission or lot sizes; Void routing unchanged. Next W4b audit asymmetric execution and minimum commission/lot data availability; do not optimize prediction. Premium10 PIT and P-All pending.
