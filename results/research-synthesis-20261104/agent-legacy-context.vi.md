# Phụ lục: các thí nghiệm F/L, baseline và fairness lịch sử

Đọc lại file kết quả thực tế, không suy loại thí nghiệm từ timestamp mới nhất.
Phụ lục này không cộng các run dưới đây vào 450 research runs của ba nhóm chính,
không gộp các protocol thành một phép kiểm định và không chạy lại training.
Tên A1/C1 trong các matrix cũ không đồng nghĩa A1/C1 của nghiên cứu uncertainty.
Các JSON `agent-legacy-*.json` bên cạnh giữ metric đã trích từ từng file nguồn;
metric trong TXT có độ chính xác hữu hạn theo cách xuất báo cáo gốc.

## 1. Hai file F/L mới nhất là smoke synthetic

- [F 20261025-232712](../comparisons/20261025-232712-32bcd9d4/F-fuzzy-client-selection.txt):
  F1–F5 × seeds42/43, **10 run × 3 rounds**, dataset=`synthetic`,
  MLP54-256-128-7, FedAvg. Đây là kiểm tra tích hợp, không phải xác nhận Covertype.
- [L 20261027-193806](../comparisons/20261027-193806-e45cc78f/L-fixed-lambda-ablation.txt):
  L0–L5 × seeds42/43, **12 run × 3 rounds**. Nguồn manifest
  `artifacts/lambda-smoke/028e5b5482/non-iid/manifest.json` xác nhận synthetic.
  Không dùng mean Accuracy khoảng 14% của fixture này làm kết luận chất lượng FL.

Một L smoke khác ở `20261025-232329-a5c0f6bb` cũng có 12 run × 3 rounds.
Chọn file có timestamp mới nhất rồi gọi là “kết quả full F/L mới nhất” sẽ sai phạm vi.

## 2. F Covertype thực: 25 run × 70 rounds

Nguồn [F 20261025-210944](../comparisons/20261025-210944-391f30e9/F-fuzzy-client-selection.txt)
và [research diagnosis](../comparisons/20261025-210944-391f30e9/analysis/research-diagnosis.md).
Năm policies, năm seeds42–46, một client partition seed42, alpha=.5,
MLP54-256-128-7, FedAvg. Năm seeds không phải năm partition độc lập.

| Policy | Phương pháp | Mean Accuracy (%) | Macro-F1 | Feasible selection coverage | Opportunity-adjusted selection Gini |
| --- | --- | ---: | ---: | ---: | ---: |
| F1 | Feasible Random | 63.04778 | .365842 | 1.000000 | .216327 |
| F2 | Resource-aware | 67.87696 | .378641 | .730000 | .704488 |
| F3 | Fuzzy TOPSIS thuần | 70.10138 | .381703 | .143333 | .893890 |
| F4 | Fuzzy + fixed credit lambda=.3 | 67.25290 | .360386 | .166667 | .884016 |
| F5 | Fuzzy + adaptive credit, initial=.3 | 67.68540 | .384651 | 1.000000 | .360149 |

F3 có Accuracy mean cao nhất nhưng participation tập trung vào ít client.
F5 mở rộng participation rất mạnh so với F3/F4 và giữ Macro-F1 mean cao hơn,
nhưng Accuracy không cao nhất; F1 còn có Gini thấp hơn F5. Đây là trade-off
theo comparator, không có policy trội trên mọi mục tiêu. F3/F4/F5 cùng dùng
history-based uncertainty; khác scheduler credit nên không cô lập fuzzy-width.

Diagnostic gốc đã kiểm tra 25 run hoàn tất, initial model/traces ghép cặp và
không có candidate-pool divergence giữa F1–F5 ở batch này. Trên cùng factual
state, F4 thay 3,94% slots so với raw CC, F5 thay 60,46%; đây là replay một bước,
không phải full counterfactual training và không tách adaptive khỏi bonus lớn hơn.

**Giữ lại anomaly seed45:** F5 Accuracy round69=72,256%, round70=57,718%,
giảm **14,538 pp**. Tất cả năm selected updates round70 đều hoàn tất; lambda
giảm, không spike ở round cuối. Tỷ lệ lớp2 trong accepted clients' training samples
tăng lên 73,012%, đi cùng thay đổi recall rất lớn giữa các lớp. Đây là liên hệ
quan sát và phân rã metric, chưa chứng minh quan hệ nhân quả model drift.
F4 seed45 cũng có final Accuracy khoảng57,354% dù không adaptive. Không được
loại seed45, thay bằng checkpoint round69, hay đổ toàn bộ lỗi cho adaptive lambda.

## 3. L Covertype thực: 30 run × 70 rounds

Nguồn [L 20261025-233756](../comparisons/20261025-233756-966e51c9/L-fixed-lambda-ablation.txt).
Sáu policies, seeds42–46, cùng manifest Covertype Dirichlet alpha=.5/seed42.
Engine, criteria và history-based uncertainty giữ chung; treatment là fairness
credit/coefficient. Round count=70, tail window=10. Không dùng file smoke mới hơn
để thay thế kết quả này.

| Policy | Lambda | Mean Accuracy (%) | Macro-F1 | Feasible selection coverage | Opportunity Gini | Slots đổi so với raw CC |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| L0 | 0, không credit | 68.73118 | .359927 | .140000 | .895005 | 0 |
| L1 | fixed .3 | 62.54126 | .382519 | .153333 | .893018 | .033143 |
| L2 | fixed .5 | 67.89884 | .389611 | .256666 | .870807 | .118857 |
| L3 | fixed .7 | 66.67322 | .388503 | 1.000000 | .274657 | .725143 |
| L4 | fixed .9 | 67.57626 | .391353 | 1.000000 | .148621 | .834286 |
| L5 | adaptive, initial .3 | 70.31152 | .390680 | 1.000000 | .369377 | .605143 |

L5 có Accuracy mean cao hơn L0 khoảng1,58034 pp và hơn L4 khoảng2,73526 pp;
L4 lại có Gini thấp hơn đáng kể. Fixed coefficient đủ lớn cũng đạt full feasible
coverage, nên full coverage của adaptive không chứng minh cần adaptive control.
Đây là mô tả trên một partition, không phải superiority/convergence guarantee.
Số slots đổi là contrast trên factual history của mỗi policy, không phải cùng
một lịch sử chung giữa toàn bộ các run.

Metric `maxAccuracyDropPp` trong L là giảm **giữa hai round liên tiếp**; báo cáo
controlled mới dùng largest peak-to-current drawdown. Không trộn hai định nghĩa.
Measured execution và protocol timing thay đổi qua các thế hệ; không so wall/
virtual time tuyệt đối giữa F/L cũ với các study timing deterministic như cùng
một benchmark đồng nhất.

## 4. Fairness-matching validation: giữ cả thất bại và NO_MATCH

[Snapshot đầu](../research/fairness-matched/validation/fairness-matched-results.json)
có **17 result rows được giữ lại**, một partition1001, các seeds42–44 xuất hiện
không cân bằng giữa policies. `complete=false`, lỗi rõ ràng:
`Experiment research-80e687cf9e00d2b736bba0e7c74a9065710b8ce5 ended with FAILED: Worker unavailable`.
Không loại lỗi này khỏi lịch sử, không suy ra policy lock hay final comparison
từ các policy means có số run khác nhau.

[Retry E1 validation](../research/retry-20261028-183037/e1/validation/fairness-matched-results.json)
hoàn tất **42 run × 70 rounds**: bảy policies × partitions1001/1002 × seeds42/43/44.
Final evaluation ở đây là **proxy**, không phải test confirmation.
M1–M6 là fixed lambda .6/.625/.65/.675/.7/.725; M7 adaptive initial=.3.
Tất cả có feasible selection coverage=1 nhưng fairness status vẫn **NO_MATCH**.

| Policy | Mean proxy Accuracy (%) | Macro-F1 | Opportunity Gini |
| --- | ---: | ---: | ---: |
| M1 fixed .6 | 71.38481 | .424188 | .572961 |
| M2 fixed .625 | 67.68499 | .400762 | .544884 |
| M3 fixed .65 | 72.04284 | .436385 | .528963 |
| M4 fixed .675 | 71.25687 | .432682 | .483073 |
| M5 fixed .7 | 70.03947 | .412216 | .499139 |
| M6 fixed .725 | 70.07561 | .413378 | .456595 |
| M7 adaptive initial .3 | 70.25863 | .419747 | .570376 |

Nearest candidate M4/.675 vẫn có selection opportunity-Gini gap=.087303,
vượt tolerance .025; max-staleness gap5,5 vượt5 và mean-staleness gap4,433 vượt2.
Matching không dùng learning metrics, nhưng **full coverage không đủ để gọi
fairness-matched**. Không được kết luận adaptive kém hơn/hơn tại cùng fairness
từ bảng này. Kết quả hợp lệ là “không tìm được match trong grid đã định”.
NO_MATCH dẫn tới Pareto comparison riêng, không phải lý do chỉnh held-out policy
để tạo match sau khi đã xem test. Các snapshot đầu/retry tái dùng điều kiện
partition/seed; không coi chúng là những replications độc lập để tăng n.

## 5. Baseline A/B/C có mục tiêu khác

Các file A/B/C ở
[batch20-round 20261025-170857](../comparisons/20261025-170857-d7361cec/A-model-size.txt)
dùng Covertype/seeds42–44: A so MLP54-128-64-7 với54-256-128-7,
B so FedAvg với FedLBW, C thay selection/aggregation. Ví dụ A có mean Accuracy
70,0834% so70,4262%; B có65,1501% so67,7481%. Các contrast là riêng từng block,
không gộp cùng row name giữa block hoặc batch. Đây không phải uncertainty ablation.

[C 70-round 20261025-180444](../comparisons/20261025-180444-8e31b019/C-client-selection.txt)
có25 run: năm configurations × năm seeds. Mean Accuracy random/FedAvg=65,2082%,
resource-aware/FedAvg=69,6745%, random/FedLBW=69,6620%,
resource-aware/FedLBW=69,3401%, feasible-random/FedAvg=63,0478%.
Các quan sát giúp mô tả hiệu ứng selection/aggregation trong protocol cũ,
không chứng minh fuzzy superiority hay calibration quality. Những fixture synthetic
1–3 rounds khác trong `results/comparisons` chỉ là kiểm tra hạ tầng.

## 6. Kết luận dùng cho tổng hợp nghiên cứu

Legacy F/L cung cấp bằng chứng về **participation–learning trade-off**, cold-start
lock-in và training instability; chúng không trả lời độc lập tác dụng fuzzy width.
Fairness matching đã thất bại theo tolerance nên phải được công bố là NO_MATCH.
Kết quả Accuracy thấp, seed45 drawdown và worker failure đều cần giữ trong paper
hoặc phụ lục, thay vì chỉ giữ bảng mean thuận lợi. Controlled ablation225 runs
mới là bằng chứng chính cho causal contrast về width; robustness324 runs vẫn chưa
có kết quả thực. Mọi kết luận về model chưa lưu metric cần checkpoint; xoá binary
sau khi giữ phụ lục này vẫn mất khả năng đánh giá lại/resume các model cũ.
