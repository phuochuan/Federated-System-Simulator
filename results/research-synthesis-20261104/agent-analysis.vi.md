# Phân tích độc lập: Fuzzy uncertainty có cải thiện lựa chọn client FL không?

Ngày tổng hợp: 4/11/2026. Báo cáo này đọc lại bằng chứng đã công bố, không chạy
training, không sửa kết quả cũ và không chọn thêm tham số dựa trên test.
Các giá trị chi tiết được tính lại trong [agent-metrics.json](agent-metrics.json).
Accuracy, Macro-F1 và recall là tỷ lệ 0–1; chênh lệch **điểm phần trăm (pp)** bằng
100 lần chênh lệch tỷ lệ, không phải phần trăm cải thiện tương đối.

## Kết luận chính

**Chưa có bằng chứng đủ mạnh rằng thêm fuzzy uncertainty giúp tăng Accuracy
cuối cùng một cách nhất quán.** Ablation kiểm soát cho thấy fuzzy width thật sự
đổi quyết định, nhưng cả fixed, history-based và calibrated đều có mean Accuracy
thấp hơn zero-width khi gộp các điều kiện U0. History-based có tín hiệu thuận lợi
ở Non-IID mạnh alpha=0.1; đây là phát hiện có điều kiện, mang tính khám phá,
không phải chứng minh ưu thế chung hay lợi ích chống nhiễu.

Phương pháp calibrated không nên được mô tả là phương pháp tốt nhất chỉ vì
độ bao phủ TFN hoặc một số metric phụ tốt hơn: nó có mức giảm Accuracy trung bình
lớn nhất trong ba treatment. Kết quả âm này là đóng góp thực nghiệm hữu ích.

## 1. Phạm vi bằng chứng và cách đếm

| Nghiên cứu | Research runs | Điều kiện | Vai trò |
| --- | ---: | --- | --- |
| Fuzzy workflow E2 | 24 | C1–C4, U0/U1/U2, alpha=.5, một partition, hai seeds | Screening trên proxy |
| Fuzzy workflow E4 | 6 mới | C5, U0/U1/U2; so với baseline E2 được dùng lại | Screening calibration trên proxy |
| Fuzzy workflow E3 | 135 | C1/C4/C5, ba alpha, ba partitions, năm seeds, U0 | Generalization qua partition |
| Controlled ablation | 225 | A0–A4, ba alpha, ba partitions mới, năm seeds, U0 | Tách hiệu ứng fuzzy width |
| Pareto lịch sử | 60 | Bốn chính sách fairness, ba partitions, năm seeds | Bối cảnh trade-off fairness |

Ba nhóm công bố chính trên chứa **450 research runs phân biệt**: 165 của full
fuzzy workflow, 225 controlled, 60 Pareto. Hai audit của full fuzzy và hai audit
của controlled được tách riêng; audit Pareto và các thí nghiệm F/L lịch sử cũng
không cộng vào con số 450 này. Đây không phải 450 mẫu độc lập cho một phép kiểm định.

Snapshot pilot fuzzy cũ trùng các run E2/E4 trong full publication, không được
cộng thêm. Trường `runs` trong `e3-heldout-results.json` chứa cả E2/E4: chỉ các
entry `stage=E3` tạo thành 135 run held-out. File E4 còn chứa baseline E2 để so
sánh; số run C5 mới chỉ là sáu. **Ma trận robustness cuối 324 runs chưa được chạy**;
smoke synthetic không được dùng làm bằng chứng FL Covertype.

Nguồn: [full fuzzy publication](../research/fuzzy-uncertainty-20261031-004757-b6b730-full-20261103/README.md),
[controlled publication](../research/controlled-fuzzy-ablation-20261104-002235-69ac39/README.md),
[Pareto publication](../research/pareto-20261028-204148/pareto-tradeoff-summary.md).

## 2. Vì sao so sánh cũ chưa tách được hiệu ứng uncertainty?

Đọc source `CrispTopsisEngine`, `FuzzyTopsisEngine`, `CriterionNormalizer` và
`ClientCriteriaExtractor` xác nhận hai họ TOPSIS không chỉ khác fuzzy width.
Conventional Crisp dùng chuẩn hóa L2 theo cột và khoảng cách Euclidean qua các
criteria. Fuzzy dùng chuẩn hóa benefit theo upper cực đại, cost theo lower cực
tiểu chia endpoints đảo chiều; fuzzy ideals lấy extrema theo component;
khoảng cách là tổng RMS vertex theo từng criterion. Vì thế zero-width Fuzzy
không mặc nhiên bằng conventional Crisp.

A1–A4 dùng chung engine Fuzzy, weights time/reliability/utility=.40/.35/.25,
feasibility và tie-break theo ID; khác cách tạo width. A1=0; A2 fixed=.1;
A3 giữ nguyên history equations; A4 giữ q=.8, window=32, min-history=5,
prior=.1, max=.45. Time dùng width tương đối, benefits dùng width cộng/trừ
trên miền [0,1]. Sau lựa chọn khác nhau, lịch sử end-to-end được phép khác nhau.

Do đó **A2/A3/A4−A1** là so sánh tách uncertainty hợp lệ trong protocol;
A1−A0 và C4/C5−C1 chỉ là so sánh cả formulation. Không được dùng mức tăng
C4−C1 ở E3 để khẳng định fuzzy uncertainty là nguyên nhân.
Nguồn: [technical audit](../../docs/controlled-fuzzy-ablation-audit.md).

## 3. Controlled ablation: kết quả chính dưới U0

Mean gộp cân bằng 45 run mỗi policy:

| Policy | Accuracy (%) | Macro-F1 | Minority recall | Accepted/selected | Feasible coverage | Selection Gini |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| A0 conventional Crisp | 69.3935 | .394194 | .020483 | .946667 | .148889 | .941604 |
| A1 zero-width Fuzzy | 69.5139 | .393331 | .014738 | .947492 | .218889 | .938516 |
| A2 fixed Fuzzy | 69.2575 | .396068 | .015273 | .947365 | .196296 | .939685 |
| A3 history Fuzzy | 69.3856 | .397996 | .020533 | .948000 | .188519 | .940259 |
| A4 calibrated Fuzzy | 68.7805 | .397738 | .023652 | .949270 | .225556 | .937378 |

| Contrast | Mean Accuracy (pp) | Median (pp) | Positive/negative/tied run pairs | Exploratory partition-t 95% interval (pp) |
| --- | ---: | ---: | --- | --- |
| A2−A1 | −.256373 | −.006024 | 14/26/5 | [−1.543234, +1.030487] |
| A3−A1 | −.128301 | −.005163 | 17/25/3 | [−1.993949, +1.737346] |
| A4−A1 | −.733378 | −.015490 | 22/23/0 | [−3.073167, +1.606411] |

Mỗi contrast có 45 run pairs nhưng chỉ **ba partition assignments độc lập**.
Intervals trên là khám phá, dựa trên ba partition means, giả định xấp xỉ t rất
yếu và không điều chỉnh multiplicity. Tất cả đều cắt 0. Không có cơ sở khẳng
định statistical superiority, equivalence, hay rằng phương pháp chắc chắn có hại
trên quần thể. Mean Accuracy âm vẫn phải được báo cáo, không đổi metric chính
sang Macro-F1 sau khi thấy kết quả.

A4 có 22 cặp dương/23 âm nhưng mean âm lớn: dấu của từng cặp không mô tả độ lớn
tổn thất. Ba partition means của A4−A1 đều âm: −.382380, −.017384, −1.800371 pp.
A3 có partition means −.964814, +.091909, +.488001 pp; hiệu ứng không đồng nhất.

Nguồn: [run-results.csv](../research/controlled-fuzzy-ablation-20261104-002235-69ac39/run-results.csv),
[paired statistical data](../research/controlled-fuzzy-ablation-20261104-002235-69ac39/controlled-ablation-results.json).

## 4. Tín hiệu có điều kiện ở alpha=.1

| Alpha | A1 Accuracy (%) | A3 Accuracy (%) | A3−A1 (pp) |
| --- | ---: | ---: | ---: |
| .1 | 64.980465 | 66.042524 | +1.062059 |
| .5 | 71.084089 | 70.061904 | −1.022186 |
| 1.0 | 72.477008 | 72.052231 | −.424778 |

Ở alpha=.1, năm seeds được lấy trung bình trong từng partition:
6001=+.284505 pp, 6002=+1.827335 pp, 6003=+1.074336 pp. Ba dấu đều dương;
leave-one-partition-out mean vẫn dương, từ +.679420 đến +1.450836 pp.
Tuy nhiên exploratory partition-t 95% interval là [−.854425,+2.978542] pp,
vẫn bao gồm hiệu ứng âm. Alpha=.1 được chú ý sau khi đã xem kết quả nên đây
là tín hiệu phát sinh giả thuyết, không phải xác nhận tiên nghiệm H1 mới.

Những số này ủng hộ câu hỏi “khi nào có lợi?” thay vì kết luận “luôn có lợi”.
Chúng chưa cho biết lợi ích có tăng dưới U2 vì toàn bộ controlled ablation là U0.

## 5. Ranking đã đổi nhưng learning chưa tăng nhất quán

100 immutable decision states, mỗi treatment so với A1 trên cùng observable input:

| Treatment | Fraction đổi selected set | Mean top-K overlap | Mean Jaccard | Mean Spearman | Mean Kendall tau-b |
| --- | ---: | ---: | ---: | ---: | ---: |
| A2 | .10 | .978 | .964286 | .999263 | .996078 |
| A3 | .19 | .956 | .929524 | .998211 | .993827 |
| A4 | .28 | .940 | .901905 | .998176 | .991899 |

Các ranking gần như giống nhau toàn cục; khác biệt tập trung vào ít vị trí,
có thể ở sát biên top-K. Đổi quyết định là quan sát trực tiếp; “chọn client tốt
hơn cho learning” không tự suy ra từ overlap hoặc CC. Replay không huấn luyện
counterfactual, và 100 trạng thái này không phải 100 FL replications độc lập.

Các dấu hiệu downstream cũng không cho thấy cải thiện hệ thống lớn: accepted/
selected của A1=.947492, A3=.948000, A4=.949270; virtual time khoảng 87 giây
mỗi run ở cả ba. A3 tăng tail Accuracy SD từ .020451 lên .023271; A4 giảm
nhẹ xuống .019705 nhưng final Accuracy thấp hơn. Cải thiện stability hoặc tỷ lệ
acceptance không đồng nghĩa cải thiện Accuracy cuối.

Selection Gini khoảng .94, opportunity Gini khoảng .90 và feasible coverage
chỉ .19–.23 ở A1/A3/A4 cho thấy tham gia tập trung. Đây là mô tả rõ trong log;
khả năng width thay đổi ranking ít nhưng không cải thiện class contribution,
hoặc feedback từ previous loss/reliability duy trì exploitation, mới là giải thích
cần kiểm chứng. Chưa có phép đo mediation hay outcome cho client không được chọn
để khẳng định chuỗi nhân quả này.
Nguồn: [offline-comparisons.csv](../research/controlled-fuzzy-ablation-20261104-002235-69ac39/offline-comparisons.csv).

## 6. Calibration tốt hơn không đủ bảo đảm decision tốt hơn

Selected-only diagnostics trong controlled ablation:

| Policy | Mean time relative error | Mean time width | Time TFN support coverage | Mean reliability width | Brier |
| --- | ---: | ---: | ---: | ---: | ---: |
| A1 | .049710 | 0 | 0 | 0 | .064009 |
| A2 | .049911 | .100000 | 1.000000 | .100000 | .062880 |
| A3 | .049854 | .026230 | .268762 | .072917 | .061885 |
| A4 | .049941 | .081067 | .808571 | .176166 | .062909 |

A4 support coverage gần .8 như quantile mục tiêu, nhưng không có nghĩa TFN là
80% statistical confidence interval hay đạt population calibration. A3 thu hẹp
time width theo số lần chọn, trong khi jitter vẫn tồn tại, nên coverage thấp hơn
là quan sát dễ hiểu; không thể từ coverage này suy ra thuật toán sai.
Fixed .1 có coverage=1 dưới bounded ±10% simulation jitter, cũng không chứng minh
fixed width là tối ưu. Width trên timing và reliability có convention khác nhau,
không nên gộp trung bình hai kênh rồi gọi là một độ lệch chuẩn chung.

Reliability dự báo **accepted-given-selected-executed**, không phải xác suất
worker HTTP thành công. Dropout/deadline rejection đều ảnh hưởng label. Outcomes
chỉ có cho client được thực thi; unselected không phải negative examples.
Brier cần diễn giải trên cohort được chọn, vốn có thể khác nhau giữa policy.

E0 công bố 84.495 outcomes nhưng gộp DB lịch sử `artifacts/minifls.db` với DB
full workflow, không phải 84.495 samples độc lập của riêng batch 167 runs.
Reliability mean relative error rất lớn (~43 triệu) là hậu quả chia cho safe
epsilon khi binary outcome=0, không phải metric calibration có ý nghĩa thực tiễn.
Ưu tiên Brier=.072271 và calibration bins selected-only trong phân tích E0.
Sai số giữa predicted virtual duration và measured worker duration cũng có
target khác nhau, không được coi là một loại prediction error duy nhất.
Nguồn: [E0 measurement](../research/fuzzy-uncertainty-20261031-004757-b6b730-full-20261103/e0-uncertainty-measurement.json).

## 7. E3 cũ, E2/E4 pilot và Pareto cung cấp gì?

E3 cũ có mean final Accuracy C1=68.909294%, C4=69.627775%, C5=69.487215%.
C4−C1=+.718481 pp; C5−C1=+.577921 pp. Cả hai có partition-mean differences
dương ở 3001/3002/3003, nhưng khác cả normalization/distance nên không phải
bằng chứng riêng cho width. Macro-F1 mean lần lượt .404069/.407608/.409771.
Không gộp E3 và controlled như cùng một causal protocol để tăng giả tạo sample size.

E2 alpha=.5, một partition, hai seeds: C4−C1 proxy Accuracy là −.829576 pp ở U0,
+.764173 pp ở U1 và +1.134212 pp ở U2. C4−C2 (zero-width Fuzzy cùng formulation)
là −.005163, +.824412, −.091219 pp: **không có xu hướng lợi ích tăng đơn điệu**
khi tách formulation. Vì chỉ một partition và hai seeds, pilot không đủ xác nhận
robustness. E4 C5−C4 qua sáu cặp proxy có mean +.298326 pp nhưng SD=2.236051 pp;
đây là screening eligibility, không phải superiority. Không dùng test về sau để
điều chỉnh quantile/window và gọi đó là confirmation.

Pareto lịch sử cho thấy fairness credit có thể đạt feasible coverage=1 trong
protocol riêng, trong khi Accuracy/fairness trade-off thay đổi theo policy và
partition; không có universal winner. Mean Accuracy P1/P2/P3/P4 lần lượt
70.871643/70.072632/69.959668/71.186899%, opportunity Gini tương ứng
.501441/.480157/.386337/.560926. Không quy thành tác dụng fuzzy width hoặc
khẳng định adaptive lambda là đóng góp chính của nghiên cứu này.

Một điểm cần chú ý cho paper: Accuracy khoảng 70% vẫn đi cùng Macro-F1 khoảng .4.
Trong controlled alpha=1, **mọi run A1–A4 đều có minority recall=0** theo định nghĩa
hai lớp ít gặp nhất trong train. Do đó không được chỉ báo cáo Accuracy; đây là
hạn chế substantive về chất lượng học lớp hiếm, không được che bằng mean tổng.

## 8. Những kết luận được và chưa được hỗ trợ

Được hỗ trợ trong simulator và protocol đã chạy:

- Nonzero TFN width có thể đổi ranking và selected set dù giữ chung engine.
- Hiệu quả Accuracy không tăng nhất quán dưới U0; baseline zero-width cạnh tranh.
- History-based có tín hiệu dương ở alpha=.1, với heterogeneity theo condition.
- Calibration/support coverage, acceptance, fairness, stability và Accuracy có thể
  đi theo các hướng khác nhau; không thể thay thế metric này bằng metric kia.

Chưa được hỗ trợ:

- Fuzzy uncertainty vượt trội một cách thống kê hoặc tổng quát trên FL.
- A3 chống observation noise tốt hơn A1 trên held-out partitions.
- A4 calibrated tốt hơn A3 hoặc A1 về Accuracy cuối.
- Đổi client selection là nguyên nhân đã xác định của cải thiện class contribution.
- TFN membership intervals là confidence intervals, hoặc calibration selected-only
  đúng cho toàn bộ population.
- Hiệu ứng độc lập trên dữ liệu test mới: các study tái dùng pool test Covertype.

## 9. Có cần chạy nghiên cứu robustness cuối không?

Nếu paper chỉ kết luận về **controlled width ablation dưới U0**, có thể viết ngay
với kết quả âm/inconclusive và những giới hạn trên; không cần tạo thêm thuật toán
hay cố tìm seed thuận lợi. Nếu paper muốn trả lời **khi nào uncertainty hữu ích
dưới noisy observations**, hiện còn khoảng trống thực nghiệm: cần nghiên cứu
robustness đã preregister, hoặc phải ghi câu hỏi đó chưa được trả lời.

Ma trận đề xuất A1/A3/A4 × ba alpha × U0/U1/U2 × sáu partitions × hai seeds
là 324 research runs, không phải kết quả đã tồn tại. H1/H2/H3 cần được đọc theo
partition: mean seeds trong partition, contrast ghép cặp, multiplicity khai báo
trước, LOPO và mọi partition phải được báo cáo. Sáu assignments vẫn không phải
sáu datasets độc lập; test examples đã được xem trong các nghiên cứu trước.
Không nên mở rộng matrix chỉ để tìm mean dương hoặc đổi kết luận sau khi thấy test.

## 10. Ý nghĩa khi xoá dữ liệu local

Các report, CSV/JSON, compressed experiment/round evidence và provenance đã có
trong Git đủ cho nhiều phép tổng hợp phân tích như báo cáo này; model tensors
không cần để tính lại những metric đã ghi. Tuy nhiên bản tổng hợp **không thay thế
checkpoint archive**: xoá model binaries mất khả năng đánh giá lại checkpoint,
kiểm tra tensor, đổi metric chưa ghi hoặc resume training từ checkpoint đó.
Backup model lên Release đã dừng theo yêu cầu và chưa hoàn tất; không được mô tả
là full backup. Quyết định xoá file gốc thuộc người dùng, báo cáo này không xoá gì.
