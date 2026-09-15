# OURE Stage8J — Dividend Role Replacement Findings

Date: 2026-09-15
Authoritative run: `34982388838`
Artifact: `oure-stage8j-dividend-role-replacement-34982388838`
Status: frozen historical repair diagnostic

## Frozen base
`Fix13 = Fix15 - 159825 - 159981` under the same frozen daily OLS engine, next-open accounting and 6bp/side costs.

BASE_FIX13:
- cumulative +1216.68%
- MDD -38.63%
- turnover sides 481
- switches 249
- mean Top1 tenure 5.56d

## Results
- DROP_513920: +1244.15%, MDD -35.49%, turnover 483, switches 251, tenure 5.53d.
- REPLACE_513920_510880 (Shanghai broad dividend; PRIMARY): +968.71%, MDD -41.45%, turnover 497, switches 255, tenure 5.43d.
- REPLACE_513920_515080 (CSI dividend): +1115.15%, MDD -36.92%, turnover 495, switches 255, tenure 5.44d.
- REPLACE_513920_512890 (dividend low-vol): +1067.39%, MDD -37.86%, turnover 481, switches 247, tenure 5.61d.
- REPLACE_513920_513530 (HK Connect broad high dividend): +1452.20%, MDD -34.78%, turnover 475, switches 245, tenure 5.64d.
- Original BASE_FIX15: +902.19%, MDD -44.72%.

## Breadth versus BASE_FIX13
### 513530
- full return delta +235.52pp
- MDD improves by 3.85pp
- turnover -6 sides
- annual better/worse/tied: 4/1/1
- 126-session blocks better/worse/tied: 5/2/5
- mean block return delta +1.70pp

Annual return vs BASE_FIX13:
- 2021: +15.17% vs +15.17% (not yet available / no effect)
- 2022: +26.56% vs +21.17%
- 2023: +23.84% vs +28.24% (worse)
- 2024: +35.12% vs +26.72%
- 2025: +144.26% vs +139.26%
- 2026 partial: +160.54% vs +142.68%

513530 becomes the OLS target on 109 daily signal observations; those target-day net returns compound to about +18.68% over the historical path. It is a materially more useful dividend competitor than 513920 in this sample.

### Drop 513920
Dropping without replacement raises cumulative return only modestly (+27.47pp) and lowers MDD, but block breadth is weak: 2 better / 3 worse / 7 tied, with mean block delta -1.15pp. Thus pure deletion is not as convincing as the aggregate headline suggests.

### Mainland broad dividend / low-vol replacements
The preregistered primary `510880` replacement fails badly versus BASE_FIX13: cumulative return falls to +968.71%, MDD worsens, turnover rises, and blocks are 4 better / 7 worse / 1 tied.

`515080` and `512890` also underperform BASE_FIX13 on total return. Low-vol 512890 slightly improves MDD/tenure structure but sacrifices substantial return; it is not a compelling replacement under this OLS objective.

## Interpretation
The user's original intuition that `513920` was not the intended generic dividend exposure is partly validated, but the evidence does NOT support replacing it with a mainland generic dividend ETF.

The strongest historical repair is instead:
`Fix13 - 513920 + 513530`.

This keeps the Hong Kong equity opportunity channel while removing the central-SOE restriction and using a broader Hong Kong Connect high-dividend index. It improves return, MDD, turnover and Top1 tenure versus Fix13 with 4/6 annual slices and 5/12 blocks better (5 tied because of availability/no effect).

This suggests the useful role may be `HK dividend / value income` rather than `central-SOE dividend` or `mainland dividend`.

## Caution
513530 only launched in April 2022, so 2021 is necessarily identical to BASE_FIX13. This is a same-sample historical repair, not clean OOS proof. Do not further search additional dividend ETFs after seeing this result. Freeze 513530 as the only replacement candidate if a prospective Fix13-v2 experiment is launched.
