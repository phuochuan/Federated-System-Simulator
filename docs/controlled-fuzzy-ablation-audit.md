# Technical audit before implementation (3 November 2026)

Inspected main at cc201905, both fuzzy protocol documents, the generalization/
robustness plan, configuration, production selection classes, RoundCoordinator,
ScenarioTrace, Python data/API/simulation/evaluation/receipt code, workflow,
watchdog, frozen-resume controller, reporting and numerical/recovery tests.
The completed full publication records 167 runs, including 135 E3 runs under U0.
Its held-out scores are not used to choose widths or policies for this study.

1. `CrispTopsisEngine`: column L2 normalization, scalar weights, cost/benefit
   extrema ideals, Euclidean distance across criteria. Neutral .5 for identical
   alternatives. Descending score, ascending integer ID ties.
2. `FuzzyTopsisEngine`: benefits divided by maximum upper endpoint; costs use
   minimum lower endpoint divided by reversed endpoints. All-zero columns map
   to (1,1,1). Weighted componentwise empirical extrema form ideals. Sum of
   per-criterion RMS vertex distances gives D+/D- and CC=D-/(D++D-).
   Its zero-width limit is generally different from conventional Crisp TOPSIS.
3. `ClientCriteriaExtractor`: time TFN is x*(1-u,1,1+u), floored at epsilon;
   bounded benefits are (max(0,x-u),x,min(1,x+u)). Weights are .40/.35/.25.
   Inputs are prior/history duration, smoothed reliability and previous local
   loss transformed by loss/(1+loss). Feasibility uses observable RAM/deadline.
4. Fixed width is .1 capped .45. History time/utility width is
   .1/sqrt(selectionCount+1); reliability is sqrt(p*(1-p)/(n+alpha+beta+1)),
   capped .45. No equation changes are needed.
5. Calibrated uses nearest-rank .8 quantile of last 32 past residuals, minimum
   five observations, prior .1, cap .45. Time residual is absolute error divided
   by max(predicted,epsilon); reliability residual is absolute Bernoulli error.
   Utility remains prior .1. These TFNs are not probability confidence intervals.
6. All existing C policies extract the same point criteria; only width mode
   differs for the fuzzy policies. Credit/adaptive lambda are inactive for pure
   fuzzy_topsis. Offline replay must use one immutable pre-round input for all
   policies; end-to-end histories can legitimately diverge after selection.
7. Successful round transactions persist selected/completed counts, last loss,
   estimated duration, residual windows and opportunity history. Partial rounds
   restore the previous snapshot. History changes future criteria, feasibility
   and widths; it is part of the total treatment effect.
8. Data split seed is distinct from partition seed. Initialization uses training
   seed, and local training seed is seed+31*round+clientId. ScenarioTrace covers
   all clients/rounds, independent of selected sets; observation-noise hashes
   omit policy/experiment ID. Pair those identities, not just RNG call order.

## Reliability target audit

`completionCount` increments for accepted updates, not simply executed worker
requests. `selectionCount` increments for every selected/executed client in a
committed round. All selected clients must have a simulation result or the round
fails atomically. Thus Beta(1,1) estimates acceptance conditional on selection/
execution: COMPLETED simulation status and deadline success. The calibration
label is the same `accept` boolean. No denominator defect was found on this
committed cohort, so this study explicitly preserves this target as
`accepted-given-selected-executed-v1`. Calling it worker reliability would be
incorrect. Unselected/unavailable clients are not negative observations.
Dropout, deadline failure and acceptance must be reported separately. Selection
bias prevents interpreting this as population-wide calibrated reliability.

## New partition reservations and controls

A read-only inventory of 201 existing manifest/protocol/config JSON files found
partition seeds 44,45,1001,1002,2001,2002,2003,3001,3002,3003. Proposed pilot
5001/5002 and confirmation 6001/6002/6003 have no matches. Recheck and preserve
the inventory before creating each new batch. New assignments reuse the fixed
underlying train/proxy/test examples; they are not new independent test datasets.
Previously inspected test pools are a limitation even with unseen assignments.

New protocol `controlled-fuzzy-width-v1` retains original scientific formulas.
A0 is historical Crisp reference. A1/A2/A3/A4 map to crisp/fixed/history_based/
error_calibrated through the identical production Fuzzy engine. Primary contrasts
are A2-A1, A3-A1, A4-A1; A1-A0 is formulation-only diagnostic. Pilot screening
uses proxy only; confirmation parameters freeze before final-only test metrics.
Use partition-level means across seed repeats; with two/three partitions,
uncertainty intervals and standardized effects have very limited precision.
