# Kế hoạch: Golden Set kiểm tra độ chính xác EWS v2_ensemble

## 1. Mục đích
Tạo một **golden set** (tập case test có ground truth) để:
1. Kiểm tra mô hình dự đoán `risk_level` có **đúng** không (PASS/FAIL).
2. Thể hiện **sự đa dạng** về dự đoán — các tình huống khác nhau được phân loại đúng.
3. Ví dụ điển hình: **học sinh học giỏi nhưng nghỉ quá nhiều vẫn bị đánh risk cao**.

## 2. Cách hoạt động
- Mỗi case = 1 bộ **24 features** đầu vào + **kỳ vọng risk_level** (ground truth do chính sách/chuyên gia xác định).
- Chạy case qua pipeline thật: `load_ensemble()` → `run_ensemble_inference()` → `risk_level`.
- So sánh dự đoán vs kỳ vọng → **PASS/FAIL**.
- Xuất báo cáo tổng hợp (accuracy + từng case).

## 3. Các case đa dạng (ground truth)

| ID | Tình huống | Score | LMS | Attendance | Behavior | Kỳ vọng |
|----|-----------|-------|-----|-----------|----------|---------|
| GS-01 | Học giỏi + chăm chỉ | tốt | tốt | tốt | tốt | **LOW** |
| GS-02 | **Học giỏi + nghỉ nhiều** | tốt | tốt | **xấu** | tốt | **HIGH** |
| GS-03 | Học giỏi + hành vi xấu | tốt | tốt | tốt | **xấu** | **HIGH** |
| GS-04 | Học kém + chăm chỉ | **xấu** | tốt | tốt | tốt | **HIGH** |
| GS-05 | Học kém + nghỉ nhiều + hành vi xấu | **xấu** | tốt | **xấu** | **xấu** | **CRITICAL** |
| GS-06 | Học trung bình + bỏ bài LMS | TB | **xấu** | tốt | tốt | **MODERATE** |
| GS-07 | Học giỏi + mọi thứ tốt (đối chứng) | tốt | tốt | tốt | tốt | **LOW** |
| GS-08 | Học sinh mới (ít dữ liệu) | NaN | NaN | NaN | NaN | **MODERATE** |

## 4. Triển khai
- Script: `scripts/ews_golden_set.py`.
- Mỗi case định nghĩa dict feature (đủ 24 cột) + `expected_level`.
- Chạy `run_ensemble_inference` trên DataFrame gộp các case.
- In bảng: ID, mô tả, dự đoán, kỳ vọng, PASS/FAIL, sub-scores, weights.

## 5. Tiêu chí chấp nhận
- Các case "rõ ràng" (GS-01, GS-02, GS-05, GS-07) phải PASS.
- Case GS-02 (học giỏi + nghỉ nhiều) phải ra HIGH — minh chứng mô hình không bỏ sót rủi ro chuyên cần.
- Báo cáo in đầy đủ sub-scores + weights để giải thích vì sao.

## 6. Kết quả thực nghiệm (đã triển khai)

**Accuracy: 7/8 (87.5%)** — sau khi sửa 1 bug.

| ID | Tình huống | Dự đoán | Kỳ vọng | KQ |
|----|-----------|---------|---------|-----|
| GS-01 | Học giỏi + chăm chỉ | LOW | LOW | ✅ |
| GS-02 | **Học giỏi + NGHỈ NHIỀU** | HIGH | HIGH | ✅ |
| GS-03 | Học giỏi + hành vi xấu | MODERATE | HIGH | ❌ |
| GS-04 | Học kém + chăm chỉ | HIGH | HIGH | ✅ |
| GS-05 | Học kém + nghỉ nhiều + hành vi xấu | CRITICAL | CRITICAL | ✅ |
| GS-06 | Học trung bình + bỏ bài LMS | MODERATE | MODERATE | ✅ |
| GS-07 | Học giỏi + mọi thứ tốt (đối chứng) | LOW | LOW | ✅ |
| GS-08 | Học sinh mới (ít dữ liệu) | MODERATE | MODERATE | ✅ |

### Minh chứng GS-02 (học giỏi + nghỉ nhiều) — HIGH là hợp lý
- `score_risk=7.9` (học giỏi), `attendance_risk=97.4` (nghỉ ~80% buổi), `weight_attendance=0.588` (α_attendance=2.2 nâng từ base 15% → 58.8%), `final=59.48` → **HIGH**.
- **HIGH đúng**: nghỉ nhiều là rủi ro chuyên cần nghiêm trọng (không thể LOW/MODERATE), nhưng học giỏi nên chưa CRITICAL (CRITICAL dành cho đa yếu tố xấu như GS-05).
- Cơ chế hoạt động đúng: nghỉ nhiều tự bật HIGH mà không kéo kịch trần.

### Bug phát hiện & đã sửa
- **Bug `available or FACTOR_KEYS`** trong [`combine_risk_scores()`](src/ews/risk_config.py:205): khi `available=[]` (không yếu tố nào có dữ liệu), `[] or FACTOR_KEYS` trả về cả 4 yếu tố → học sinh mới bị đánh theo sub-model (HIGH) thay vì MODERATE trung tính. Đã sửa thành `available if available is not None else FACTOR_KEYS`. Sau sửa, GS-08 PASS (MODERATE, 50.0).

### Case FAIL còn lại (GS-03) — cần quyết định chính sách
- behavior_risk=99.3 (rất xấu), weight_behavior=0.495, nhưng final=52.3 (MODERATE) — vì α_behavior=1.8 < α_attendance=2.2 nên weight_behavior không đủ đẩy qua HIGH=88.
- **Nếu chính sách "hành vi xấu đơn lẻ → HIGH"**: tăng α_behavior (1.8 → 2.2).
- **Nếu chính sách "chỉ đa yếu tố mới HIGH"**: MODERATE là đúng, cập nhật kỳ vọng GS-03 = MODERATE.

## 7. Static JSON Cache (API không chạy inference ML tại runtime)

Endpoint `GET /ews/golden-set` **không còn chạy inference ML** mỗi lần khởi động.
Thay vào đó, nó đọc kết quả từ file cache tĩnh `src/ews/golden_set_data.json`
(đã được sinh sẵn và commit vào git) → phản hồi < 1ms, không phụ thuộc model `.cbm`/catboost.

### Quy trình tái sinh sau khi retrain model
1. Retrain model mới (sinh các file `.cbm` trong `src/models/gbdt/saved/`).
2. Chạy script sinh cache:
   ```bash
   .venv\Scripts\python.exe scripts\precompute_golden_set.py
   ```
   Script này: gọi `run_golden_set()` → validate JSON (`allow_nan=False`) → validate schema
   `EwsGoldenSetResult` → ghi đè `src/ews/golden_set_data.json` (kèm `model_version`, `generated_at`).
3. Commit file `src/ews/golden_set_data.json` mới vào git để runtime dùng.

### Hành vi khi file cache thiếu
- Endpoint trả `HTTP 503` kèm hướng dẫn chạy `scripts/precompute_golden_set.py`
  (thay vì `500` mơ hồ do thiếu model/NaN).
- `run_golden_set()` + CLI `scripts/ews_golden_set.py` vẫn là **nguồn sự thật** để
  kiểm chứng model và tái sinh cache.
