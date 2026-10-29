# Kiểm chứng kết luận FMCDM — batch 20261025-210944-391f30e9

Phân tích mô tả sau thực nghiệm, đọc evidence đã commit. Không sửa thuật toán, không train lại, không lựa chọn checkpoint hay điều chỉnh tham số bằng test metrics. Nhãn lớp trong diễn giải dưới đây dùng cách đánh số gốc 1–7; JSON dùng indices 0–6.

## Kết luận được dữ liệu hỗ trợ

F5 là ứng viên đáng nghiên cứu về accuracy–participation fairness trade-off so với Resource-aware và Fuzzy TOPSIS thuần trong protocol hiện tại. Chưa xác lập lợi thế của **adaptive control** so với một fairness coefficient cố định đủ lớn, chưa chứng minh superiority, convergence hay fairness guarantee. Năm seeds đều dùng cùng một partition dữ liệu seed42.

Đã kiểm tra đủ 25 runs COMPLETED, mỗi run 70 rounds. Mỗi seed có cùng initialized model hash trên cả năm methods. Toàn bộ exogenous traces khớp; **không có round nào khác candidate pool giữa F1–F5** trong batch này. Vì vậy candidate-pool divergence không giải thích các khác biệt quan sát ở batch này. Nhiễu đo thời gian vẫn có thể ảnh hưởng ranking.

## Kết quả cuối run (mean ± sample SD, n=5)

| Method | Accuracy (%) | Macro-F1 | Feasible completion coverage (%) | Opportunity-adjusted selection Gini |
| --- | --- | --- | --- | --- |
| F1 Feasible Random | 63.05 ± 4.68 | .3658 ± .0348 | 99.67 ± .75 | .2163 ± .0299 |
| F2 Resource-aware | 67.88 ± 2.44 | .3786 ± .0451 | 72.00 ± 7.40 | .7045 ± .0336 |
| F3 Fuzzy TOPSIS | 70.10 ± 1.00 | .3817 ± .0451 | 14.33 ± .91 | .8939 ± .0070 |
| F4 Fixed credit | 67.25 ± 5.73 | .3604 ± .0300 | 16.67 ± 2.64 | .8840 ± .0138 |
| F5 Adaptive credit | 67.69 ± 5.93 | .3847 ± .0355 | 99.67 ± .75 | .3601 ± .0388 |

F5 đạt **selection coverage 60/60 = 100% ở cả 5 seeds**. Completion coverage đạt 60/60 ở seeds42–45, 59/60 ở seed46: mean99.67%. Population completion coverage trên 100 clients chỉ là 59.8%; 40 LOW clients không đủ RAM. Không gọi đây là coverage100% của toàn hệ thống.

F5 có mean accuracy thấp hơn F2 .19 điểm phần trăm, nhưng SD cao hơn nhiều. Paired accuracy differences F5−F2 theo seeds42..46 lần lượt **+1.85, +.99, −.30, −8.48, +4.98 pp**. F1 có Gini thấp hơn F5 và completion coverage tương đương; lợi thế fairness của F5 phải gắn với comparator F2/F3/F4, không phải mọi baseline.

## Cơ chế fairness: điều đã kiểm chứng và giả thuyết

`audit.py` tái tính từ saved pre-round inputs tất cả **1,050 quyết định fuzzy** (F3/F4/F5 × 5 seeds × 70 rounds): Q recurrence, score bonus, Top-K/tie-breaking, feasible-opportunity Gini, EMA và lambda kế tiếp đều khớp. Không phát hiện sai khác số học trong các bước này. Audit không phải kiểm định độc lập toàn bộ engine CC: CC được lấy từ saved engine output; numerical engine tests/independent smoke đã được ghi ở validation trước đó.

So sánh trong cùng một observed state, thay scheduler score bằng raw CC rồi tính Top-K:

* F4: 69/1,750 slots (3.94%) khác raw-CC Top-K.
* F5: 1,058/1,750 slots (60.46%) khác raw-CC Top-K.
* Max applied lambda của F5 theo seed: .813, .691, .763, .826, .694; F4 luôn .300.
* F5 đạt full feasible selection coverage ở rounds39,34,33,37,30 tương ứng seeds42..46.

Đây là **one-step ranking contrast trên factual history**, không phải kết quả huấn luyện phản thực của một full run không có credit. Nó chứng minh bonus đã thay đổi lựa chọn, nhưng không tự cô lập causal contribution của adaptive controller so với larger fixed lambda.

Dấu hiệu lock-in rõ ở seed45. F3 và F4 chỉ chọn HIGH clients trong cả 350 slots, lần lượt chỉ 8 và 9 client IDs. F5 chọn đủ60 clients, với197 HIGH slots và153 MEDIUM slots. Ở round2 của F3, ngay trong cùng tier HIGH: clients đã được chọn có median estimate .0883s và CC .9412, trong khi HIGH chưa được chọn có estimate1.0974s và CC .1527. Prior cho cold clients và lịch sử timing/reliability cho warm clients tạo chênh lệch đáng kể. Đây là giả thuyết về cơ chế lock-in cần ablation calibration, không phải chứng minh time criterion là nguyên nhân duy nhất.

Ở F5 seed45, MEDIUM clients lần đầu được chọn tại round18 (IDs71 và74). Lambda đạt .6523 tại round21; coverage tăng từ21.67% ở round20 lên30% ở round21,86.67% ở round30 và100% ở round37. Sau đó lambda giảm khi Gini thấp hơn target; round70 dùng lambda .5979. Cần kiểm tra hiệu ứng EMA/integral history và mức bonus, không chỉ đặt tên cơ chế là adaptive.

## Seed45: biến động cuối run

| Chỉ số F5 | Round69 | Round70 |
| --- | --- | --- |
| Accuracy | 72.256% | 57.718% |
| Macro-F1 | .40976 | .33881 |
| Recall lớp1 | 78.651% | 8.041% |
| Recall lớp2 | 73.389% | 99.317% |
| Tỷ lệ lớp2 trong accepted clients' training samples | 42.014% | 73.012% |
| Applied lambda | .60893 | .59789 |
| Accepted updates | 5/5 | 5/5 |

Round70 nhận clients `[50,89,91,93,94]`; tất cả COMPLETED, không có dropout/timeout/OOM trong nhóm này. Training data của nhóm có15.861% lớp1 và73.012% lớp2. FedAvg weights gần .2 mỗi client, phù hợp sample counts. Ba slots khác raw-CC Top-K trên cùng state. Lambda đã **giảm**, không spike ở round cuối.

Đóng góp của recall thay đổi vào accuracy delta, tính đúng theo supports trong confusion matrix: lớp1 −25.745pp; lớp2 +12.643pp; lớp3 −2.143pp; các lớp còn lại cộng .707pp; tổng **−14.538pp**. Đây là phân rã kế toán của metric, không phải chứng minh causal từ nhãn của clients sang tham số model.

Mean accuracy rounds61–70: F5 **69.377%**, F2 **68.624%**, F3 **68.872%**. F5 có nhiều dao động lớn trong trajectory, nhưng dữ liệu không ủng hộ diễn giải đơn giản là toàn bộ giai đoạn cuối đã suy giảm liên tục. Last10 mean là diagnostic hậu nghiệm; **không thay thế final-round metric, không chọn round69/best checkpoint làm kết quả chính**.

F4 seed45 cũng có final accuracy57.354% dù không có adaptive feedback. Do vậy giả thuyết “lambda adaptive quá lớn gây toàn bộ sự cố” chưa đủ bằng chứng. Một giả thuyết hợp lý để kiểm chứng là local training/FedAvg trên các nhóm Non-IID nhỏ gây model drift/dao động, còn scheduler quyết định nhóm nào xuất hiện. Cần một thí nghiệm đối chứng để tách hai thành phần.

## Các ablation ưu tiên, không thêm tính năng

1. **Adaptive hay chỉ là bonus lớn hơn?** So sánh fixed-lambda trong phạm vi đã định trước với adaptive, giữ nguyên engine/partition/initial weights/traces/training. Có thể dùng các mức .3/.6/.8 để khảo sát cơ chế, nhưng không chọn mức “tốt nhất” bằng test seed45. Quyết định tham số bằng validation và xác nhận trên seeds/partitions chưa dùng. Ghi cả coverage/Gini, slot replacements và distribution của CC-gap/bonus.
2. **Cold-start lock-in:** dùng timing prior được calibrate chỉ từ benchmark training để làm một protocol đối chứng; giữ protocol hiện tại làm reference. Không sửa baseline âm thầm. Đối chiếu seen/unseen trong cùng tier và số client được chọn lần đầu, để tách prior bias khỏi resource preference. Các modes `crisp`/`history_based` và utility-off là ablation tiếp theo nếu cần xác định thành phần fuzzy/utility.
3. **Seed45 model drift:** từ checkpoint69 bất biến, branch một round với các candidate sets định trước; giữ training seed/hyperparameters/aggregation cố định. Đo training label mix, update norms/directions nếu đã có công cụ, và đánh giá trên validation độc lập. Replay factual set để làm kiểm soát. Một-round branch là kiểm chứng cơ chế tại state69, không thay thế full-run prospective validation.
4. **Ổn định training với scheduler cố định:** nếu giả thuyết drift được validation hỗ trợ, kiểm tra một yếu tố như learning rate theo protocol riêng và áp dụng settings đồng nhất cho các methods đối chứng. Không thay cả scheduler, aggregation và training đồng thời. Không thêm test-driven early stopping hoặc chọn checkpoint tốt nhất bằng test.

Trước prospective experiments cần một validation split không trùng train/proxy/test reporting protocol, hoặc một protocol phân chia đã định trước phù hợp. Không dùng kết quả test hiện tại để tối ưu lambda, learning rate hay learning utility. Các phát hiện trên là exploratory hypotheses cần xác nhận ngoài partition seed42.

## Evidence

* Báo cáo batch: `../F-fuzzy-client-selection.txt`.
* `audit.py`, `audit.json`, `audit-output.txt`: thống kê và kiểm tra arithmetic/ranking/controller.
* `mechanism.json`: cohort observations và phân rã seed45 rounds69–70.
* `seed45-trajectories.png`: accuracy, feasible coverage, applied lambda và opportunity Gini theo round.

Không thay đổi source Java/Python production hay file cấu hình; mọi output của audit nằm trong thư mục analysis riêng của batch.
