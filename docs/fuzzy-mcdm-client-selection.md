# Fuzzy TOPSIS and opportunity-aware fairness credit selection

This implementation investigates system efficiency, model quality and long-term client participation. It adds three **selection** methods to the Java coordinator; it does not add an aggregation method or change FedAvg/FedLBW. All three share the same fuzzy engine:

FMCDM means **Fuzzy Multi-Criteria Decision Making**. In the [Controlled Experiment Matrix](controlled-matrix.md#nhóm-f--fmcdm-client-selection), it is **group F**, alongside the retained A/B/C groups. `MINIFLS_METHOD=fuzzy_matrix` is the enabled launcher for F1–F5; `MINIFLS_METHOD=matrix` executes only the A/B/C calls enabled in the application class. Python's method registry remains the aggregation catalog; these selectors run at the Federated Server in Java.

| Method | Default criteria | Scheduler |
|---|---|---|
| `fuzzy_topsis` | estimated time, reliability, learning utility | CC ranking |
| `fuzzy_topsis_fair` | same | fixed fairness coefficient |
| `adaptive_fuzzy_topsis_fair` | same | completed-round feedback coefficient |

The fuzzy matrix, normalization, fuzzy ideals, vertex distances and closeness coefficient follow the Fuzzy TOPSIS family described by [Chen (2000)](https://doi.org/10.1016/S0165-0114(97)00377-1). This implementation explicitly uses **data-derived componentwise fuzzy ideals**, rather than the alternative fixed `(1,1,1)` / `(0,0,0)` convention. Criterion construction, uncertainty widths, learning utility, credit combination and feedback controller are system heuristics, not claims that they originate from that paper. There is no Lyapunov derivation or theoretical convergence/fairness guarantee.

## Integration and lifecycle

`RoundCoordinator.executeRound` observes availability, then obtains the feasible pool through `Policies.feasibleClients` / `Policies.isFeasible`, the same predicate as Feasible-Random and Resource-aware. Fuzzy selectors consume only available profiles, configuration and the previous committed selection state. Baseline RNG seeds, policy rankings and aggregation remain unchanged.

Round t selects using state committed at t-1. After training, simulation, aggregation and server evaluation finish successfully, the coordinator records valid opportunities/completions and updates credit and feedback. `ExperimentRepository.commit` writes metrics and the complete snapshot in the existing SQLite transaction. A failure before commit restores the preceding snapshot, so a partial attempt cannot spend credit or advance lambda. No scheduler state is stored in a static object or singleton.

`Snapshot.selectionHistory` records feasible opportunities, entitlement, valid selections/completions and opportunity-based staleness. `Snapshot.fuzzySelectionState` records method, version `fuzzy-topsis-credit-v1`, last committed round, deficits, current lambda and smoothed Gini. Existing `ClientProfile` history preserves model-independent pre-round timing/loss, selection and completion counts. `selectorInput` in each fuzzy round stores the pre-training profiles/history/state for decision replay. Unknown/mismatched method, version, round, or missing fuzzy state on resume fails explicitly.

Old JSON configurations omit `fuzzySelection` and continue to work. Old baseline snapshots omit the new fields: diagnostics start at the first resumed round, identified by `feasibleHistoryStartRound` in metrics (`startRound` in the snapshot). These conditional opportunity metrics must not be presented as whole-run metrics for such a legacy run. Baselines never create or modify a fairness-credit state. No SQLite schema migration or new `ScenarioTrace` fields are needed.

## Feasibility and observation boundary

The pool contains available clients with `ramMb >= requiredRamMb` and, when configured, `estimate(config) <= deadlineSeconds`. Predictions use the existing historical estimate, otherwise `numSamples * localEpochs * priorSecondsPerSample / cpu`. These constraints remain active for feasibility-based policies even when simulation is disabled, matching the existing predicate. Selection takes `K_t = min(K, |F_t|)`; an empty pool selects nobody, and a small pool never falls back to an infeasible client. Predicted RAM/CPU/time observations must be finite and valid.

The selector has no access to future dropout, jitter, simulation results, actual upcoming training duration, proxy evaluation or held-out evaluation. Trace availability is the only trace event read before selection. Full traces stored later in round metrics are audit evidence, not selector input. Policy-specific observed timings can cause deadline candidate pools to diverge despite identical exogenous traces. The TXT report counts these differing pools per seed and explains this mechanism.

## Criteria and deterministic uncertainty

Positive configured weights must sum to one (zero weight disables a criterion). The explicit protocol weights are C1=.40, C2=.35, C3=.25, giving system time slightly more importance while retaining reliability and a modest learning heuristic. They are exploratory settings, not test-optimized values. New fuzzy methods require an explicit `fuzzySelection.weights`; they cannot silently adopt an implicit weight vector.

| Configuration name | Observation | Direction |
|---|---|---|
| `estimatedTime` | existing pre-round estimate, floored at epsilon | cost |
| `reliability` | `(completionCount + alpha) / (selectionCount + alpha + beta)` | benefit |
| `learningUtility` | `loss/(1+loss)` for preceding local training loss; neutral prior .5 without history | benefit |
| `fairnessDeficit` | maximum-normalized credit; for pure TOPSIS, positive cumulative opportunity entitlement minus valid selections | benefit, optional C4 |
| `selectionStaleness` | never selected: 1; otherwise `clip((round-lastSelectedRound)/round,0,1)` | benefit, optional C5 |

High previous local loss represents an underfit/difficulty heuristic. It is **not measured marginal contribution**, and can favor noisy clients. A loss from an executed but subsequently rejected update remains an observed training-only signal, consistent with existing profile history. No test data is read. C2 defaults to Beta(1,1), preventing exact 0/1 reliability at small sample counts. C4 tracks valid opportunities, not raw population-wide selection counts.

Let x be the crisp observation and u its uncertainty width. Time becomes `(max(eps,x(1-u)), max(eps,x), max(eps,x(1+u)))`. Unit-interval benefits become `(max(0,x-u), x, min(1,x+u))`. Credit/staleness bookkeeping is exact (width zero).

Uncertainty modes:

* `history_based` (protocol default): time/utility width `min(uncertaintyMax, uncertaintyFallback/sqrt(selectionCount+1))`; reliability width `min(uncertaintyMax, uncertaintyScale*sqrt(p(1-p)/(selectionCount+alpha+beta+1)))`.
* `fixed`: width `uncertaintyFallback` for the first three criteria, capped by `uncertaintyMax`.
* `crisp`: width zero, useful for the crisp-versus-fuzzy ablation through the same engine.

The widths are deterministic epistemic heuristics, not empirically calibrated confidence intervals. Defaults `.10`, maximum `.45`, scale `1`, and epsilon `1e-9` are explicit in the protocol file. No random fuzzy numbers are generated. Non-finite and invalid observations/configuration fail instead of producing NaN rankings. Time zero is floored at epsilon. Missing history uses the defined priors.

## Fuzzy TOPSIS equations

For triangular number `a=(l,m,u)`, scalar multiplication and addition are componentwise. Vertex distance is:

`d(a,b) = sqrt(((a.l-b.l)^2 + (a.m-b.m)^2 + (a.u-b.u)^2)/3)`.

For a benefit column j, with `U_j = max_i u_ij`, normalize `r_ij=(l_ij/U_j,m_ij/U_j,u_ij/U_j)`.

For a cost column, let `L_j=min_i max(eps,l_ij)`; normalize `r_ij=(L_j/max(eps,u_ij),L_j/max(eps,m_ij),L_j/max(eps,l_ij))`.

An all-zero column is uninformative and is mapped to `(1,1,1)` for every candidate. Weighted numbers are `v_ij=w_j*r_ij`. The positive ideal A+ uses componentwise maxima over v; A- uses componentwise minima (all columns now have benefit orientation). Distances sum vertex distances over criteria:

`D_i+ = sum_j d(v_ij,A_j+)`, `D_i- = sum_j d(v_ij,A_j-)`.

`CC_i = D_i- / (D_i+ + D_i-)`.

If the denominator is at most epsilon, use neutral CC=.5. This covers one candidate and completely identical alternatives. Every CC is finite in [0,1]. Descending scores are tied by ascending integer clientId, independently of map order or worker call order. Weights are crisp scalars multiplying TFNs; the algorithm is not a weighted sum of crisp observations.

## Fairness credit and adaptive control

For feasible clients only, `a_i(t)=K_t/|F_t|` and `x_i(t)=1` if selected. After a completed round:

`Q_i(t+1)=max(0,Q_i(t)+a_i(t)-x_i(t))`.

Infeasible/unavailable clients accrue no credit and retain their existing balance. Selection spends credit even if the update subsequently drops out: this targets **selection opportunity**, while completions are measured separately. There is no reset between rounds. The pure method keeps empty deficits and lambda zero.

`credit_score` normalizes `Q_i` by the maximum Q among this round's feasible candidates (all zero -> zero). Final score is `CC_i + lambda(t)*normalizedQ_i`. The fixed method defaults to lambda .30. Normalization deliberately bounds this bonus: it is a heuristic trade-off, not a proof of starvation freedom for arbitrarily unequal scores. Equal-resource/equal-score controlled tests verify rotation and eventual coverage. If a strict exploration floor is needed, use the separate quota ablation.

`credit_quota` reserves up to `fairnessQuota` slots for the highest Q, then fills remaining slots by CC. It never adds a fairness bonus simultaneously. Quota must be positive in this mode; score mode requires quota zero. Adaptive mode requires score mode. C4/C5 with a credit scheduler are rejected unless `allowFairnessDoubleCounting=true` explicitly enables that ablation. Default weights include neither.

For adaptive selection, end-of-round opportunity-adjusted selection rates are `s_i = validSelections_i / feasibleOpportunities_i` over **ever estimated-feasible clients**, including feasible clients never selected (rate zero). RAM-impossible clients never enter this population. Define ordinary Gini of these rates (empty/all-zero ->0). Apply EMA:

`gbar(t)=rho*gbar(t-1)+(1-rho)*Gini(s(t))` (first observation initializes it).

`delta=clip(eta*(gbar(t)-giniTarget),-maxUpdate,+maxUpdate)`.

`lambda(t+1)=clip(lambda(t)+delta,lambdaMin,lambdaMax)`.

Defaults: rho=.8, eta=.05, target=.55, bounds [0,1], maxUpdate=.05. EMA/bounded steps damp feedback; no test accuracy enters the controller. The new lambda applies starting at t+1. With no previously feasible population there is no feedback update. This is feedback control, **not Lyapunov optimization**. `FairnessScheduler` separates selection and after-round commit so a later derived scheduler can reuse state without changing the fuzzy engine.

## Metrics and interpretation

Per-round SQLite JSON and `/experiments/{id}/rounds` contain method/version, feasible count/IDs, selected/accepted IDs, `selectorComputationMs`, raw observations/TFNs, CC/ideals/distances, pre-round credits/lambda, final scores, post-round credits/next lambda and smoothed feasible Gini. Full scores are DEBUG/audit JSON; INFO emits `selection.started`, `selection.feasible_filtered`, `fuzzy_topsis.ranked`, `fairness.credit_updated`, `selection.completed` summaries.

| Metric | Definition |
|---|---|
| populationCoverage / existing coverage | completed at least once / all clients |
| ramFeasibleCoverage | completed at least once / static RAM-feasible clients |
| estimatedFeasibleCoverage | completed at least once / clients with any observed pre-round feasible opportunity (legacy-compatible diagnostic) |
| feasibleSelectionCoverage | selected during valid opportunity at least once / ever feasible-opportunity clients |
| feasibleCompletionCoverage | accepted during valid opportunity at least once / ever feasible-opportunity clients |
| selectionGini / completionGini | raw cumulative counts over the full population; includes excluded clients, explicitly labeled |
| ramFeasibleCompletionGini | completion count Gini over static RAM-feasible clients |
| feasibleOpportunityAdjustedGini | valid selections / valid opportunities, over ever feasible clients |
| feasibleCompletionOpportunityAdjustedGini | valid completions / valid opportunities, same population |
| max/meanFeasibleSelectionStaleness | consecutive valid opportunities missed since the latest valid selection; infeasible rounds do not age this counter |

Empty coverage denominators are null/N/A; all-zero Gini is zero by convention and must be interpreted together with coverage and accepted ratio. The 40 LOW clients excluded by a 600 MB requirement remain visible in population metrics, but not in conditional fairness denominators. `SelectionHistory.entitlement` also stores the sum of per-round K/F shares for audit/C4. The adaptive metric uses selection/opportunity rates, not entitlement-normalized rates; varying pool sizes can therefore affect the interpretation of fairness.

Selector time includes shared feasibility diagnostics plus decision, criteria extraction, ranking, snapshotting audit input and scheduling for every policy. `fairnessUpdateMs` separately measures valid-opportunity accounting and, for fuzzy methods, credit/controller update. Both include their local summary logging. Existing virtual time includes simulated job duration plus proxy/weight/aggregation overhead, excluding test evaluation. `virtualRoundSecondsWithSelector` and `cumulativeVirtualSecondsWithSelector` additionally include selector and fairness bookkeeping. Wall time includes real sequential training, test evaluation and local overhead, excluding initialization; it is not a networked FL deployment time. Logical tensor bytes are reported; WAN communication latency/cost remains NOT_MODELED.

## Controlled F experiments

The separate [L0–L5 fixed-lambda ablation](lambda-ablation.md) tests whether adaptive feedback adds value beyond a sufficiently large fixed credit coefficient. It keeps this engine/controller unchanged and adds stability and same-history raw-TOPSIS slot replacement diagnostics. Launch with `MINIFLS_METHOD=lambda_ablation`; the F protocol remains available unchanged.

`configurations/fuzzy-matrix.json` is a separate protocol; existing A/B/C configuration and entry points are retained. F1 feasible_random, F2 resource_aware, F3 fuzzy_topsis, F4 fuzzy_topsis_fair, F5 adaptive_fuzzy_topsis_fair all use FedAvg, large `54-256-128-7` MLP, a fixed Non-IID alpha=.5 manifest, 100 clients, K=5, 70 rounds, seeds `[42,43,44,45,46]`, local epoch1, batch32 and LR=.01. Scenario: heterogeneous, availability .9, dropout .05, deadline10s, requiredRAM600MB, jitter .1. Seeds vary model/training/selection/scenario; the dataset partition remains fixed at data seed42.

All five rows receive the same settings, model seed and shared counterfactual trace, and each pair is checked against actual initialized tensor hashes, manifest/split hashes and every round/client exogenous event. Trace paths and hashes contain no selection-specific score inputs. The six contrasts are F1–F2, F1–F3, F3–F4, F4–F5, F1–F5 and F2–F5. `ControlledExperiments.compareFuzzyClientSelection()` runs each row once per seed and exports:

`artifacts/comparisons/<batch-id>/F-fuzzy-client-selection.txt`

The report includes final metrics (not best checkpoints), mean +/- sample SD, all paired differences by seed, per-class recall statistics, candidate-pool divergence, selection/completion fairness, overhead, first time-to-target and sustained-through-final-round status. A target reached once then lost is not called sustained. Unreached targets remain NOT_REACHED; conditional timing means always show reached counts. Failure produces INCOMPLETE with its reason and suppresses the final comparison conclusion. The report describes observed trade-offs without asserting overall superiority or significance.

Prepare matching manifests from the repository root, start the worker, then run the F matrix (PowerShell):

```powershell
.\.venv\Scripts\python.exe -m minifls.data --dataset covertype --output artifacts/partitions/covertype-iid-42
.\.venv\Scripts\python.exe -m minifls.data --dataset covertype --strategy dirichlet_label_skew --alpha 0.5 --output artifacts/partitions/covertype-dirichlet-42
.\.venv\Scripts\python.exe -m uvicorn minifls.api:app --host 127.0.0.1 --port 8000 --workers 1
```

In another terminal at the repository root:

```powershell
$env:MINIFLS_METHOD = 'fuzzy_matrix'
$env:MINIFLS_WORKSPACE = (Get-Location).Path
$env:MINIFLS_FUZZY_MATRIX_CONFIG = 'configurations/fuzzy-matrix.json'
# Leave MINIFLS_MATRIX_ROUNDS unset for the 70-round protocol.
Set-Location ferderatedsystem
.\gradlew.bat bootRun --no-daemon
```

For an individual API run, combine `baseConfig` with top-level `fuzzySelection`, set selection to one of the three new names and POST that single object to `/experiments`. The entire matrix document is not an ExperimentConfig. After completion use `/experiments/{id}/result`; `/rounds` exposes the full trajectory and `/experiments/{id}` the final persisted snapshot. After failure/restart use POST `/experiments/{id}/resume`; start Java in `MINIFLS_METHOD=none` to avoid launching a second matrix batch. Matrix-level orchestration does not automatically resume the remaining batch: resume individual runs and rerun a fresh batch if a complete paired report is required.

## Validation and reproducibility

Recorded implementation check results: [2026-10-25 validation](validation/fuzzy-mcdm-2026-10-25.md).

```powershell
Set-Location ferderatedsystem
.\gradlew.bat test bootJar --no-daemon
Set-Location ..
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe scripts/verify_fuzzy.py
```

The smoke script starts its own services on free ports and isolated SQLite, uses real PyTorch training on synthetic data, runs all five methods for 3 rounds and seeds42/43, and verifies initialization hashes, all exogenous traces, feasibility, persisted credit recurrence, adaptive feedback, and an independent scalar reconstruction of TFN normalization/ideals/CC. It also interrupts an additional adaptive experiment, restarts both Java and Python, resumes through round12 from SQLite and verifies that committed history remains unchanged. Its summary and service log live in `artifacts/fuzzy-smoke/<id>/`; it stops only the processes it created. These results are explicitly SMOKE TEST ONLY and must never be mixed with the 70-round Covertype protocol.

Java tests include independently calculated nontrivial fuzzy distances/CC, arithmetic, normalization, identical/empty/small pools, cold priors, ties, invalid values, credit accumulation/repayment, controlled non-starvation, lambda bounds and serialization. SQLite coordinator tests interrupt partway through round3, create a new coordinator and verify identical subsequent decisions, credits, metrics and final state for all new methods against uninterrupted execution with deterministic observed worker timings. Baseline resume is checked too. Matrix tests enforce configuration equality except selection, actual model hashes and even unselected-client trace equality.

Repeatability means deterministic decisions **given the same observed histories**, not guaranteed identical physical wall-clock timings on separate fresh runs. Existing estimates derive from measured PyTorch times; operating-system timing noise can alter future ranking/deadline pools even with identical seeds/traces. Saved `selectorInput` makes the actual decision replayable, and resumed operation preserves committed history. A fully deterministic synthetic duration model would be a separate experimental protocol, not an undisclosed modification of the baseline simulator.

## Complexity and limitations

With N feasible clients and M active criteria, matrix construction, normalization and distances cost O(NM), ranking O(N log N), persistent scheduler state O(population). Per-round audit data adds O(NM + population) JSON storage. This deliberate audit overhead is included in selector measurement and can matter for short jobs; timings depend on JVM warmup/logging.

The uncertainty model and high-loss utility require ablation/calibration on a training/validation protocol. Max-normalized bounded credit does not prove fairness under arbitrary resource or score asymmetry. Feasibility and fairness denominators depend on observed history and can differ between policies. Neither virtual time nor payload byte counts model WAN transport. The adaptive target is exploratory. Five seeds with one partition still do not establish generalization across partitions. No tuning or checkpoint selection may use held-out test scores; use a separate validation split for future tuning. A 100-round/multiple-partition study must have a distinct config/report identity.
