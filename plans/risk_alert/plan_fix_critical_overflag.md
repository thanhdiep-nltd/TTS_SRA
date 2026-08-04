# Kế hoạch: Khắc phục tình trạng CRITICAL bị kéo quá nhiều ở EWS v2_ensemble

> **Cập nhật theo phản biện chuyên sâu (3 điểm):**
> 1. Đặt `worst_factor_beta = 0.0` (loại hoàn toàn double-counting) thay vì 0.10.
> 2. Giữ `MODERATE = 52.5` (không nâng lên 55) để dải HIGH rộng hơn cho can thiệp sớm.
> 3. Bổ sung kiểm tra **granularity**: theo dõi cả `COUNT(*)` (bản ghi) lẫn `COUNT(DISTINCT student_code)` (học sinh).

## 1. Bối cảnh & vấn đề

Ở mốc 2025-HK1-Tuần8, model `v2_ensemble` (7151 bản ghi) có phân bố risk_level:

| Level | Số bản ghi | Tỷ lệ |
|-------|-----------|-------|
| CRITICAL | 1678 | 23.5% |
| HIGH | 2688 | 37.6% |
| MODERATE | 2128 | 29.8% |
| LOW | 657 | 9.2% |

**CRITICAL chiếm ~23.5% là quá cao** so với kỳ vọng một hệ thống cảnh báo sớm (thường 3-8%). Đây là dấu hiệu over-flagging.

## 2. Chẩn đoán gốc (đã xác minh bằng dữ liệu)

### 2.1. Alpha Polarization (α=2.5) — XÁC NHẬN
Công thức [`_softmax_weights()`](src/ews/risk_config.py:143): `logits = base * exp(alpha*s)`.
- Với `base_score=0.65`, `s_score=0.99` → `logit_score = 0.65 × e^(2.5×0.99) = 7.72`
- Các yếu tố khác ở `s≈0.1` chỉ ~0.13-0.19 → `w_score ≈ 94%`

**Dữ liệu:** 1153/1678 bản ghi CRITICAL (69%) có `weight_score ≥ 0.80`.

### 2.2. Worst-Factor Blend (β=0.20) — XÁC NHẬN
Công thức [`combine_risk_scores()`](src/ews/risk_config.py:204): `final = 0.8×softmax_avg + 0.2×max(S_k)`.
- Tái tính tay HS170100: `score=99.77, softmax_avg≈97.9` → `final = 0.8×97.9 + 0.2×99.77 = 98.25` (khớp DB).

### 2.3. Lỗ hổng "double-counting" (điểm mấu chốt)
Softmax đã dồn ~90% trọng số vào yếu tố tệ nhất, rồi worst-factor blend lại cộng thêm 20% của chính yếu tố đó → **yếu tố tệ nhất bị tính ~1.2 lần**. Hai cơ chế cùng mục đích ("không để yếu tố tệ bị che lấp") nhưng **dư thừa nhau** và cộng dồn làm phồng điểm.

### 2.4. Ngưỡng HIGH=80 cài cho thang điểm CŨ (lỗi hiệu chỉnh lỗi thời)
Comment cũ trong [`risk_weights.yaml`](src/ews/risk_weights.yaml:41): *"thang v2 bị nén (max ~83) nên đặt HIGH=80"*.
- Sau khi retrain (per-factor targets + bỏ calibration), **thang điểm giờ chạm tới ~98** (max=98.25).
- Ngưỡng 80 giờ quá thấp so với phân bố thực tế → bắt quá nhiều.

**Bằng chứng:** 1678/1678 bản ghi CRITICAL đều có 1 yếu tố áp đảo (max sub-score ≥ 80).

## 3. Mục tiêu

- Giảm CRITICAL từ ~23.5% xuống mức hợp lý (~5-8%).
- Giữ nguyên khả năng phát hiện học sinh thực sự nguy cấp (không bỏ sót).
- Không cần retrain model (chỉ chỉnh tham số + ngưỡng).

## 4. Phương án đề xuất

### Phương án A — Tái hiệu chỉnh ngưỡng (tác động lớn nhất, ít rủi ro nhất)
Chỉ sửa [`risk_weights.yaml`](src/ews/risk_weights.yaml:43), không đụng logic.

Đề xuất ngưỡng mới (dựa trên phân bố hiện tại, cần xác minh percentile trước khi chốt):
```
LOW: 20.0
MODERATE: 52.5   # GIỮ NGUYÊN (theo phản biện #2) — tránh nén dải HIGH
HIGH: 88.0
CRITICAL: 100
```
- Ranh giới CRITICAL thực chất = HIGH = 88 (thay vì 80).
- **Giữ MODERATE = 52.5** (không nâng lên 55) → dải HIGH `[52.5-88]` rộng ~35.5 điểm, tốt cho can thiệp sớm.
- Ranh giới MODERATE = LOW = 20 (thay vì 17.5).

> **Lưu ý:** Giá trị cụ thể phải được chốt sau khi chạy truy vấn percentile `risk_score` (p90/p95/p99) để đảm bảo CRITICAL rơi vào top ~5-8% **theo học sinh** (xem mục 5).

### Phương án B — Giảm Alpha (giảm phân cực trọng số)
Sửa `alpha: 2.5 → 1.2` trong YAML (hoặc env `EWS_ALPHA=1.2`).
- Giảm `w_score` từ ~94% xuống mức cân bằng hơn (~60-70%).
- Giảm độ nhạy của softmax với yếu tố tệ nhất.
- **Lưu ý tương tác α↔β:** α thấp làm gap `(max − softmax_avg)` lớn hơn → càng nên đặt β=0.0 (xem C).

### Phương án C — Bỏ Worst-Factor Blend (loại double-counting) — theo phản biện #1
Sửa `worst_factor_beta: 0.20 → 0.0`.
- Đóng góp thực của β là `β × (max − softmax_avg)`, không phải `β × max`.
- Với yếu tố tệ có trọng số gốc thấp (behavior/attendance) hoặc nhiều yếu tố vừa phải, gap lớn (5-9 điểm) → β gây phồng điểm đáng kể.
- Softmax đã tự dồn trọng số vào yếu tố tệ → β là dư thừa. Đặt β=0.0 loại hoàn toàn double-counting.

### Phương án D — Kết hợp (đã triển khai, chạy thành công)
Kết hợp A + B + C để xử lý cả 3 gốc rễ:
```
alpha: 1.2
worst_factor_beta: 0.0
risk_level_thresholds:
  LOW: 20.0
  MODERATE: 52.5
  HIGH: 88.0
  CRITICAL: 100
```
**Kết quả thực nghiệm (2025-HK1-Tuần8, 7151 bản ghi):**
- CRITICAL: 1678 → **759 bản ghi** (10.6%), **355 học sinh** (COUNT DISTINCT).
- HIGH: 3003, MODERATE: 2319, LOW: 1070.
- Trong CRITICAL: 434 bản ghi có 1 yếu tố xấu, 320 có 2, 5 có 3.
- **Vấn đề còn lại:** chỉ **5 bản ghi** có `attendance_risk≥80` bị xếp MODERATE (không bật HIGH) — do attendance base weight 10% + alpha chung 1.2 không đủ bù.

### Phương án E — Factor-Specific Alpha (α_k) — KHUYẾN NGHỊ DÀI HẠN
Giải quyết dứt điểm vấn đề "nghỉ nhiều phải bật HIGH" bằng cách tách **độ nhạy (α_k)** khỏi **chính sách (base weight)**.

**Cấu trúc YAML mới:**
```yaml
dynamic:
  enabled: true
  alpha:
    score: 1.0        # base 65% đã cao, không cần khuếch đại
    lms: 1.8          # LMS khuếch đại vừa phải
    attendance: 2.2   # Chuyên cần khuếch đại mạnh → nghỉ nhiều tự bật HIGH
    behavior: 1.8     # Hành vi khuếch đại vừa phải
  weight_floor: 0.05
  worst_factor_beta: 0.0   # GIỮ NGUYÊN — không đưa 0.08 trở lại (chống double-counting)
```

**Thay đổi code (src/ews/risk_config.py):**
1. `DynamicConfig`: `alpha: float` → `alpha: dict[str, float]` (giữ backward-compat: nếu alpha là số → dùng chung mọi yếu tố).
2. `_softmax_weights()`: nhận `alpha_vec` (mảng theo từng yếu tố) thay vì alpha vô hướng.
3. `combine_risk_scores()`: xây `alpha_vec` từ cfg theo `keys`, truyền vào `_softmax_weights`.
4. Env override: `EWS_ALPHA` (chung) + `EWS_ALPHA_SCORE/LMS/ATTENDANCE/BEHAVIOR` (riêng).

**Lý do tối ưu dài hạn:**
- Tách bạch 3 khái niệm: base weight (chính sách) / α_k (độ nhạy) / threshold (ranh giới) → dễ tinh chỉnh độc lập, dễ giải thích nghiệp vụ.
- Bản chất phân phối khác nhau (score liên tục vs attendance/behavior lệch mạnh) → cần độ nhạy riêng.
- Linh hoạt tương lai: thêm yếu tố mới chỉ tinh chỉnh α_k của yếu tố đó.

**Điều kiện bắt buộc:**
- β = 0.0 (không tái lập double-counting).
- Kiểm chứng thực nghiệm TOÀN BỘ 7151 bản ghi (không chỉ 1 case cực đoan) trước khi chốt.
- Xác minh: học sinh nghỉ nhiều (attendance_risk cao) bật HIGH; không tái lập over-flag CRITICAL; ≥2 yếu tố xấu vẫn CRITICAL.

**Kết quả thực nghiệm (đã triển khai, 2025-HK1-Tuần8, 7151 bản ghi):**
- CRITICAL: **637 bản ghi (8.9%)**, **325 học sinh** (COUNT DISTINCT) — tốt hơn Phương án D (759/355).
- HIGH: 3235, MODERATE: 2250, LOW: 1029.
- **Nghỉ nhiều bật HIGH ✅**: 5 bản ghi `attendance_risk≥80` giờ đều **HIGH** (trước là MODERATE) — α_attendance=2.2 hoạt động đúng.
- **≥2 yếu tố xấu vẫn CRITICAL ✅**: 286 bản ghi (281 có 2 + 5 có 3) đều CRITICAL.
- Không tái lập over-flag: CRITICAL giảm từ 23.5% → 8.9%.
- Hồi quy: `py_compile` ✅, `tsc --noEmit` ✅, `pytest test_ews_rbac.py` 6 passed ✅.

## 5. Các bước triển khai

1. **Chạy truy vấn percentile** `risk_score` (p90/p95/p99) để chốt ngưỡng dữ liệu-driven.
2. **Sửa [`risk_weights.yaml`](src/ews/risk_weights.yaml)** theo phương án đã chọn (A/B/C/D).
3. **Chạy lại pipeline**:
   ```
   .venv\Scripts\python.exe scripts\run_ews_pipeline.py --school-year 2025 --semester 1 --week 8 --model-version v2_ensemble
   ```
4. **Xác minh phân bố mới** — theo dõi SONG SONG 2 thước đo (theo phản biện #3):
   - `COUNT(*)` (bản ghi) — cho bảng hiển thị.
   - `COUNT(DISTINCT student_code)` (học sinh) — cho tải can thiệp thực tế.
   - CRITICAL bản ghi nên ~5-8%; CRITICAL học sinh nên ~20-40 em/khối (mức GVCN xử lý được).
   - Kiểm tra không mất các bản ghi thực sự nguy cấp (HS có ≥2 yếu tố tệ cùng lúc vẫn CRITICAL).
5. **Kiểm tra hồi quy**: `py_compile`, `tsc --noEmit`, `pytest tests/test_api/test_ews_rbac.py`.
6. **Cập nhật comment** trong YAML cho khớp thang điểm mới (bỏ comment "max ~83" lỗi thời).

## 6. Tiêu chí chấp nhận (Definition of Done)

- [ ] CRITICAL bản ghi giảm từ ~23.5% xuống ~5-8% (~350-570 bản ghi).
- [ ] **CRITICAL học sinh** (`COUNT(DISTINCT student_code)`) nằm ở mức thực tế (~20-40 em/khối).
- [ ] Các bản ghi có ≥2 yếu tố tệ (max sub ≥ 80) vẫn được xếp CRITICAL.
- [ ] Không có lỗi runtime; pipeline chạy thành công.
- [ ] `py_compile`, `tsc --noEmit`, test EWS RBAC đều pass.
- [ ] Comment trong YAML được cập nhật cho khớp thang điểm mới.

## 7. Rủi ro & lưu ý

- **Rủi ro bỏ sót:** Nâng ngưỡng quá cao có thể bỏ sót học sinh nguy cấp thật. Cần kiểm tra kỹ vùng 80-90 (vùng tranh chấp) trước khi chốt.
- **Ảnh hưởng frontend:** Ngưỡng mới chỉ thay đổi `risk_level`/`risk_score`; frontend hiển thị theo dữ liệu API nên không cần sửa code, chỉ cần chạy lại pipeline.
- **Không retrain:** Tất cả thay đổi đều qua YAML/env, không cần retrain model.
