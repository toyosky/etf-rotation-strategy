# OURE Stage4C — Two-Architecture Mechanism Validation Findings

Date: 2026-09-14
Run: `34830882472`
Artifact: `oure-stage4c-two-architecture-34830882472`
Status: frozen
Decision: `partial_support_relay_only`

## Frozen question

Do the Stage1 small-K elite and Stage3B large-K elite groups each separate from same-K controls in coherent, repeatable structural directions, rather than only at the champion level?

The preregistered two-architecture hypothesis required both sides to separate at group level. That criterion was not met.

## Small-K persistence side: only partial support

Across the Stage1 K7 top-25 versus 50 same-K random controls, the separation is weak and mixed.

Full history median differences (elite minus control):
- mean Top1 tenure: `+0.204` days;
- median Top1 tenure: `0`;
- short-run <=2 share: `+0.023` (opposite the persistence hypothesis);
- leader HHI: `-0.0074` and effective leader count `+0.216` (also opposite the expected stronger concentration);
- Top1-Top2 median gap: `+0.274` (supportive);
- mean score-crossing rate: `-0.0033` (weakly supportive).

Era check:
- 2021–24: tenure is only about `+0.190` days; short-run share is `+0.0375` (opposite); leader HHI remains lower; crossing is slightly higher (`+0.0037`, opposite); the Top1-Top2 median gap remains larger (`+0.189`).
- 2025–26: tenure remains only about `+0.200` days; short-run share becomes mildly lower (`-0.0107`); crossing becomes lower (`-0.0142`); the Top1-Top2 median gap remains larger (`+0.386`), but leader concentration still does not move in the expected direction.

Therefore the exact K7 champion is a strong persistence example, but the Stage1 K7 top-25 do not form a clean, repeatable persistence class relative to same-K controls. The persistence architecture is not promoted as a validated second state.

## Large-K relay side: coherent group-level support

Across the Stage3B large-K top-25 versus same-K random controls, the relay/productive-replacement separation is coherent and persists across eras.

Full history median differences (elite minus control):
- coverage share: `+0.0152`;
- coverage efficiency: `+0.439`;
- active leader share: `+0.103`;
- switch rate: `-0.0334`;
- mean Top1 tenure: `+0.864` days;
- productive-switch share: `+0.0758`;
- switch counterfactual gain sum: `+1.776`;
- switch counterfactual gain mean: `+0.00688`;
- leader-year specialization: `+0.0623`;
- leader-transition diversity: `+0.0524`.

2021–24 retains the core relay signal:
- switch rate `-0.0414`;
- mean tenure `+1.384` days;
- productive-switch share `+0.0693`;
- counterfactual gain sum `+1.094`;
- counterfactual gain mean `+0.00701`;
- leader-year specialization `+0.0662`;
- score crossing `-0.0114`.

2025–26 also retains the economically important replacement signal:
- active leader share `+0.0736`;
- productive-switch share `+0.0975`;
- counterfactual gain sum `+0.578`;
- counterfactual gain mean `+0.00582`;
- transition diversity `+0.0472`;
- coverage efficiency `+0.170`.

The later era no longer shows a meaningful switch-rate reduction (`-0.0037`) or tenure extension (`+0.045`), which is consistent with the previously frozen regime shift: relay quality is better characterized by productive replacement and coverage efficiency than by simply reducing switching.

## Interpretation

Stage4C rejects the strong statement that there are already two validated discrete architecture classes.

What survives is narrower:

1. `relay architecture` is a reproducible group-level mechanism among the Stage3B large-K elite;
2. the exact K7 champion remains a valid persistence example, but persistence is not a repeatable K7 elite-group signature under the frozen metrics;
3. nominal K, raw switch count and Top1 tenure are not sufficient state variables;
4. the more robust relay state is defined by opportunity coverage plus replacement quality: productive switches, positive switch counterfactual gain, efficient use of eligible opportunities and diversified leader transitions.

This is a negative result for the symmetric two-state hypothesis and is frozen as such. No metric threshold, group size or era definition is changed to rescue persistence.

## Next gate

Stage4D will test the frozen relay directions on disjoint Universes not used in Stage4C discovery. It will not search for a better hindsight champion and will not train a return classifier.

Only after cross-Universe replication may a later stage seek point-in-time proxies for relay structure. If relay structure fails the holdout replication, it will be frozen as discovery-sample specific and the research will fall back to a continuous effective-competition interpretation.