# Experiment protocol

Prepare a separate immutable manifest for each partition/seed. Covertype has 581,012 rows, 54 features and seven labels mapped to 0–6. The deterministic stratified split is 435,759 train / 29,051 proxy / 116,202 test. Fit scaling on training rows only, and scale only the first ten continuous Covertype features. Proxy and test rows never enter client partitions. Hashes, train/proxy/test indices, preprocessing statistics and client label histograms are saved.

Partition modes: `iid_equal`, `iid_quantity_skew`, `dirichlet_label_skew`, `dirichlet_mixed_skew`. Label skew uses per-client Dirichlet class preferences with capacity-constrained sample assignment. This is a defined implementation variant rather than a claim to match every published Dirichlet allocator. Equal IID and label-skew modes use nearly equal sample counts; quantity modes use seeded unequal capacities. Every sample is assigned once and every client is nonempty. Generate a histogram before interpreting severity at a particular alpha.

Hold dataset manifest, model initialization seed, training settings and resource scenario fixed for policy comparisons. Use alpha 1.0/0.5/0.1 and at least three independent seeds for research, reporting variability. Twenty rounds are a smoke test; they do not establish convergence or algorithm superiority. Use test metrics only for reporting, not tuning or selection. Proxy loss drives FedLBW only.

Seeded selection/availability/dropout/jitter and data/training operations are reproducible on the same software/CPU environment. Virtual durations are derived from measured wall times, so reruns do not promise identical virtual times. Persisted round JSON contains actual job durations and virtual events so timing can be audited/replayed from those measurements. GPU execution is not used. The generated environment lock records exact dependency versions for the validated Windows environment; install the CPU torch wheel separately on other platforms.

The centralized benchmark is a diagnostic reference on the same training pool, not a compute-matched FL comparison. Report loss, accuracy, macro-F1, class precision/recall and confusion matrix. Compare accuracy by rounds and virtual time; also report coverage, successful-participation Gini, opportunity-adjusted Gini, staleness, accepted/selected counts, failure statuses and proxy overhead. Full per-client histories permit selection/completion histograms and tier-specific analyses.

SQLite stores JSON round evidence and snapshots rather than many normalized analytics tables. Export routes produce CSV and full JSON, and `minifls.plot` produces a standalone PNG. The experiment snapshot records the source Git commit; also retain the dependency lock and manifest hashes. Keep artifacts out of Git.

## Controlled FMCDM protocol (group F)

The [controlled matrix](controlled-matrix.md) preserves the A/B/C comparisons and adds a separate F protocol in `configurations/fuzzy-matrix.json`. F1=`feasible_random`, F2=`resource_aware`, F3=`fuzzy_topsis`, F4=`fuzzy_topsis_fair`, F5=`adaptive_fuzzy_topsis_fair`. All use FedAvg; this study changes client selection, not aggregation.

Use 100 clients, K=5, 70 rounds, seeds `[42,43,44,45,46]`, large 54–256–128–7 MLP, one local epoch, batch32, LR=.01 and a fixed Non-IID alpha=.5 partition at data seed42. Heterogeneous scenario: availability=.9, dropout=.05, deadline=10s, RAM requirement=600MB, jitter=.1. Verify actual initialized tensor hashes and the full availability/dropout/jitter traces across methods per seed. Physical duration histories remain observed quantities; document policy-dependent candidate pools rather than assuming they are identical.

Run `MINIFLS_METHOD=fuzzy_matrix` to execute 25 experiments and export the six contrasts F1–F2, F1–F3, F3–F4, F4–F5, F1–F5 and F2–F5 in `artifacts/comparisons/<batch-id>/F-fuzzy-client-selection.txt`. Report final accuracy/Macro-F1, per-class recall, mean ± sample SD and paired differences by seed, first-crossing and sustained targets, virtual clocks with/without selector overhead, wall time, accepted ratio and conditional selection/completion fairness. Unreached targets remain censored, never imputed as zero.

Default fuzzy criteria use pre-round estimated training time, Bayesian-smoothed completion reliability and previous local training loss as a heuristic utility proxy. No test/proxy evaluation is used to construct these scores. Fairness credit accrues only for feasible opportunities and is spent on selection; completion fairness is measured separately. Adaptive lambda uses completed-round feasible-opportunity Gini with smoothing and bounds; it is not Lyapunov optimization. Weights, uncertainty and feedback parameters are explicit in the protocol and [mathematical documentation](fuzzy-mcdm-client-selection.md).

`scripts/verify_fuzzy.py` uses synthetic data, 2 seeds and 3 rounds per matrix experiment, plus a separate live restart/resume check. [Recorded validation](validation/fuzzy-mcdm-2026-10-25.md) confirms implementation, not superiority or convergence. Keep these smoke outputs separate from the 70-round Covertype study. A 100-round or multiple-partition study requires a separate protocol/configuration identity. Do not tune parameters or select best checkpoints with reported test metrics.

## Requirement coverage

| Work package | Implemented capability | Verification |
| --- | --- | --- |
| WP01 | Java/Python HTTP, configuration validation, IDs, logging, SQLite | Java context test; HTTP integration |
| WP02 | Covertype preparation, four partitions, train-only scaling, manifests | partition/split/checksum tests; full data preparation |
| WP03 | CPU MLP, fresh local optimizer, immutable checkpoints, centralized diagnostic | tensor/training isolation tests; benchmark CLI |
| WP04 | 100 clients, K=5, sample-weight FedAvg, version/acceptance checks | numeric tests; 20-round HTTP run |
| WP05 | CPU/RAM, availability, dropout, deadlines, two clocks | SimPy tests; rejection integration scenarios |
| WP06 | SQLite snapshots, resume, class metrics, fairness, JSON/CSV/plots | crash/resume integration; export checks |
| WP07 | inverse proxy-loss FedLBW, stable zero-loss policy, overhead | numeric and real HTTP tests |
| WP08 | resource heuristic, history, exploration, audit decisions | selection tests; resource-aware HTTP run |
| WP09 | deferred research extensions | FedProx/Oort/Lyapunov optimization remain unimplemented |
| FMCDM | shared Fuzzy TOPSIS engine, fixed/adaptive fairness credit, F1–F5 comparisons, persisted state and metrics | numerical/unit tests, SQLite resume equivalence and real Python/Java smoke; see [validation](validation/fuzzy-mcdm-2026-10-25.md) |

Physical resource calibration, larger multi-seed comparisons and hypothesis conclusions remain experimental work. No WAN/network-throughput or physical OOM claims are made by this simulator.
