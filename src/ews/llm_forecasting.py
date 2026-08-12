# -*- coding: utf-8 -*-
"""
src/ews/llm_forecasting.py — LLM-based Forecasting cho EWS.

Bổ sung lớp phân tích định tính (biến cố gia đình, bệnh tật) mà CatBoost thuần ML
không nắm được. Sau khi CatBoost cho risk_score gốc (audit), module này gọi LLM cho
học sinh thuộc nhóm trigger (HIGH/CRITICAL, hoặc có biến cố/bệnh ONGOING đáng kể),
lưu kết quả vào 6 cột llm_* của `fact_student_subject_risk_predictions`.

Trigger condition (tinh chỉnh — tránh trigger thừa):
    Trigger = (risk_level IN ['HIGH', 'CRITICAL'])
           OR (EXISTS life_event WHERE status='ONGOING')
           OR (EXISTS medical WHERE status='ONGOING'
               AND (is_chronic = TRUE OR severity IN ('MODERATE','HIGH')))

Concurrency & rate limit (tránh HTTP 429):
    - ThreadPoolExecutor(max_workers=LLM_MAX_CONCURRENCY=5)
    - Retry exponential backoff khi HTTP 429/5xx: tối đa LLM_MAX_RETRIES=3, delay 2s→4s→8s
    - Lỗi sau cùng → log + skip học sinh (llm_* = NULL), không chặn batch
"""

from __future__ import annotations

import json
import logging
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import pandas as pd
from sqlalchemy import text
from sqlalchemy.orm import Session

from src.config import get_settings
from src.db.session import SessionLocal
from src.services.llm import get_llm

logger = logging.getLogger(__name__)

# Các cột llm_* sẽ được gắn vào DataFrame kết quả (khớp UPSERT trong pipeline_runner).
LLM_OUTPUT_COLS = [
    "llm_risk_score",
    "llm_risk_level",
    "llm_narrative_summary",
    "llm_forecast_trend",
    "llm_recommended_actions",
    "llm_evaluated_at",
]

# Các mức rủi ro hợp lệ do LLM trả về
VALID_LLM_LEVELS = {"LOW", "MODERATE", "HIGH", "CRITICAL"}


# ============================================================================
# HELPERS
# ============================================================================


def _safe_float(value: Any, default: float = 0.0) -> float:
    """Chuyển value sang float an toàn (NaN/None → default)."""
    try:
        if value is None:
            return default
        f = float(value)
        if f != f:  # NaN
            return default
        return f
    except (TypeError, ValueError):
        return default


def _safe_int(value: Any, default: int = 0) -> int:
    """Chuyển value sang int an toàn."""
    try:
        if value is None:
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def _json_safe(value: Any) -> Any:
    """Chuyển value sang kiểu JSON-serializable (Decimal/numpy → float/int).

    PostgreSQL trả DECIMAL (Decimal) cho các cột DECIMAL; json.dumps không
    serialize được Decimal → cần convert trước khi đưa vào prompt.
    """
    if value is None:
        return None
    if isinstance(value, bool):  # phải trước int (bool là subclass int)
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return value
    # Decimal, numpy.float64, numpy.int64, ... → float/int
    try:
        import decimal
        if isinstance(value, decimal.Decimal):
            if value == value:  # không NaN
                return float(value)
            return None
        import numpy as np
        if isinstance(value, np.generic):
            v = value.item()
            return _json_safe(v)
    except Exception:
        pass
    # Fallback: str
    return str(value)


def _parse_llm_response(text_content: str) -> Dict[str, Any]:
    """Parse nội dung JSON từ LLM response.

    LLM có thể trả JSON thuần, hoặc bọc trong ```json ... ``` (markdown fence).
    Trả dict đã chuẩn hoá; nếu không parse được → raise ValueError.
    """
    if not text_content:
        raise ValueError("LLM returned empty response")

    content = text_content.strip()
    # Bỏ markdown fence nếu có
    fence_match = re.search(r"```(?:json)?\s*(.*?)```", content, re.DOTALL)
    if fence_match:
        content = fence_match.group(1).strip()

    # Nếu vẫn còn text thừa quanh JSON object, cắt từ { đầu tiên đến } cuối cùng
    if not content.startswith("{"):
        start = content.find("{")
        end = content.rfind("}")
        if start != -1 and end != -1 and end > start:
            content = content[start : end + 1]

    try:
        data = json.loads(content)
    except json.JSONDecodeError as exc:
        raise ValueError(f"LLM response is not valid JSON: {exc}") from exc

    if not isinstance(data, dict):
        raise ValueError("LLM response JSON must be an object")

    return data


def _call_llm_with_retry(prompt: str) -> str:
    """Gọi LLM với retry exponential backoff khi HTTP 429/5xx.

    Dùng get_llm() (đã cấu hình qua .env LLM_PROVIDER). Sau LLM_MAX_RETRIES lần
    thất bại → raise Exception để caller quyết định skip.
    """
    settings = get_settings()
    max_retries = settings.llm_max_retries
    llm = get_llm()
    if hasattr(llm, "bind"):
        llm = llm.bind(max_tokens=350)
    delay = 2.0  # bắt đầu 2s

    last_exc: Optional[Exception] = None
    for attempt in range(1, max_retries + 1):
        try:
            response = llm.invoke(prompt)
            content = response.content
            if isinstance(content, list):
                # Một số model trả content dạng list các block — lấy text
                parts = [
                    b.get("text", "") if isinstance(b, dict) else str(b)
                    for b in content
                ]
                content = "".join(parts)
            if not isinstance(content, str):
                content = str(content)
            return content
        except Exception as exc:  # noqa: BLE001 — bắt mọi lỗi API/network
            last_exc = exc
            status = getattr(exc, "status_code", None)
            is_retryable = status == 429 or (status is not None and status >= 500)
            # Không có status_code (network error/timeout) → cũng retry
            is_retryable = is_retryable or status is None
            if not is_retryable or attempt == max_retries:
                # Lỗi không retry được (vd 4xx) hoặc đã hết lượt
                raise
            logger.warning(
                "[LLM Forecast] Attempt %d/%d failed (status=%s): %s. Retrying in %.0fs...",
                attempt,
                max_retries,
                status,
                exc,
                delay,
            )
            time.sleep(delay)
            delay *= 2  # 2s → 4s → 8s

    raise RuntimeError(f"LLM call failed after {max_retries} attempts: {last_exc}")


# ============================================================================
# PROMPT BUILDING
# ============================================================================


def _format_duration(quantity: Optional[int], unit: Optional[str]) -> str:
    """Định dạng khoảng thời gian cho prompt: '3 MONTH' → '3 tháng'."""
    if quantity is None:
        return "không rõ"
    unit_map = {
        "DAY": "ngày",
        "WEEK": "tuần",
        "MONTH": "tháng",
        "YEAR": "năm",
    }
    u = (unit or "").upper()
    unit_vn = unit_map.get(u, u or "đơn vị")
    return f"{quantity} {unit_vn}"


def _build_llm_prompt(
    student_code: str,
    subject_name: str,
    features: Dict[str, Any],
    life_events: List[Dict[str, Any]],
    medical: List[Dict[str, Any]],
) -> str:
    """Tạo prompt structured (tiếng Việt) cho LLM.

    Phần static prefix (System Instructions + JSON Schema) được giữ cố định ở ĐẦU PROMPT
    để kích hoạt DeepSeek Automatic Prompt Caching (Cache Hit ~90%).
    Phần dynamic suffix (dữ liệu học sinh, môn học, features) được nối ở CUỐI PROMPT.
    """
    # Feature chính liên quan nhất đến rủi ro (tránh prompt quá dài)
    feature_keys = [
        "weighted_early_avg", "weighted_late_avg", "score_slope", "score_volatility",
        "max_drop", "last_score", "lms_avg_score", "lms_recent_drop",
        "lms_submission_rate", "daily_absence_rate", "unexcused_absent_rate",
        "total_demerit_points", "repeat_offense_count", "severe_sanction_count",
    ]
    feat_lines = []
    for k in feature_keys:
        if k in features:
            v = _json_safe(features[k])
            if isinstance(v, float):
                v = round(v, 3)
            feat_lines.append(f'    "{k}": {json.dumps(v, ensure_ascii=False)}')
    features_str = ",\n".join(feat_lines)

    # Biến cố cuộc sống
    le_lines = []
    for ev in life_events:
        le_lines.append(
            json.dumps(
                {
                    "event_name": ev.get("event_name"),
                    "event_type": ev.get("event_type"),
                    "severity": ev.get("severity"),
                    "duration": _format_duration(ev.get("time_quantity"), ev.get("time_unit")),
                    "status": ev.get("status", "UNKNOWN"),
                    "description": ev.get("description"),
                },
                ensure_ascii=False,
            )
        )
    le_str = ",\n".join(le_lines) if le_lines else "[]"

    # Bệnh lý
    med_lines = []
    for m in medical:
        med_lines.append(
            json.dumps(
                {
                    "condition_name": m.get("condition_name"),
                    "condition_type": m.get("condition_type"),
                    "severity": m.get("severity"),
                    "is_chronic": bool(m.get("is_chronic", False)),
                    "duration": _format_duration(m.get("time_quantity"), m.get("time_unit")),
                    "status": m.get("status", "UNKNOWN"),
                    "notes": m.get("notes"),
                },
                ensure_ascii=False,
            )
        )
    med_str = ",\n".join(med_lines) if med_lines else "[]"

    cb_score = _safe_float(features.get("risk_score"))
    cb_level = str(features.get("risk_level", "UNKNOWN"))

    # STATIC PREFIX: Giữ cố định 100% cho mọi lượt gọi -> Kích hoạt DeepSeek Prompt Cache Hit
    static_prefix = """Bạn là chuyên gia phân tích rủi ro học tập và cố vấn tâm lý giáo dục tại trường phổ thông Việt Nam.
Nhiệm vụ: phân tích rủi ro học tập của 1 học sinh theo môn học, kết hợp dữ liệu định lượng (CatBoost) với dữ liệu định tính (biến cố cuộc sống, bệnh lý) để đưa ra đánh giá tổng hợp (llm_risk_score) và khuyến nghị can thiệp.

=== HƯỚNG DẪN ĐÁNH GIÁ ===
1. Risk_score CatBoost là điểm rủi ro ML [0-100]. Hãy điều chỉnh lên/xuống dựa trên biến cố và bệnh lý:
   - Biến cố/bệnh ONGOING (MODERATE/HIGH/CRITICAL) hoặc bệnh mãn tính -> tăng mức rủi ro phù hợp.
   - Biến cố đã RESOLVED (cũ) hoặc bệnh/cảnh nhẹ (LOW) -> không nâng rủi ro.
2. llm_risk_score phải nằm trong [0, 100], gần risk_score CatBoost (chênh tối đa ±20) trừ khi biến cố/bệnh nghiêm trọng rõ rệt.
3. Viết súc tích, cô đọng nguyên nhân gốc rễ (narrative) và hành động khuyến nghị.

=== ĐỊNH DẠNG TRẢ LỜI ===
Trả về CHỈ MỘT JSON object (không thêm text ngoài), đúng schema:
{
  "llm_risk_score": <float 0-100>,
  "llm_risk_level": "<LOW|MODERATE|HIGH|CRITICAL>",
  "llm_narrative_summary": "<2 câu ngắn gọn tiếng Việt phân tích nguyên nhân gốc rễ>",
  "llm_forecast_trend": "<1 câu dự báo xu hướng 3-4 tuần tới>",
  "llm_recommended_actions": ["<hành động ngắn 1>", "<hành động ngắn 2>", "<hành động ngắn 3>"]
}"""

    # DYNAMIC SUFFIX: Nối thông tin động ở cuối prompt
    dynamic_suffix = f"""

=== DỮ LIỆU HỌC SINH CẦN ĐÁNH GIÁ ===
Mã học sinh: {student_code}
Môn học: {subject_name}

--- Kết quả CatBoost ---
{{
{features_str},
    "risk_score": {cb_score},
    "risk_level": "{cb_level}"
}}

--- Biến cố cuộc sống / gia đình ---
{le_str}

--- Bệnh lý / tiền sử y tế ---
{med_str}"""

    return static_prefix + dynamic_suffix


# ============================================================================
# CONTEXT LOADING & TRIGGER
# ============================================================================


def _load_context(
    session: Session,
    student_code: str,
    school_year_id: int,
) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Load biến cố cuộc sống + bệnh lý của học sinh (kèm thời gian/status)."""
    le_sql = text("""
        SELECT event_name, event_type, event_date, severity, description,
               time_quantity, time_unit, status
        FROM s360.fact_student_life_events
        WHERE student_code = :sc AND school_year_id = :sy
        ORDER BY event_date DESC
        LIMIT 50
    """)
    le_rows = session.execute(le_sql, {"sc": student_code, "sy": school_year_id}).fetchall()
    life_events = [
        {
            "event_name": r.event_name,
            "event_type": r.event_type,
            "event_date": r.event_date,
            "severity": r.severity,
            "description": r.description,
            "time_quantity": r.time_quantity,
            "time_unit": r.time_unit,
            "status": r.status,
        }
        for r in le_rows
    ]

    med_sql = text("""
        SELECT condition_name, condition_type, severity, is_chronic, diagnosed_date, notes,
               time_quantity, time_unit, status
        FROM s360.fact_student_medical_history
        WHERE student_code = :sc AND school_year_id = :sy
        ORDER BY diagnosed_date DESC
        LIMIT 50
    """)
    med_rows = session.execute(med_sql, {"sc": student_code, "sy": school_year_id}).fetchall()
    medical = [
        {
            "condition_name": r.condition_name,
            "condition_type": r.condition_type,
            "severity": r.severity,
            "is_chronic": bool(r.is_chronic) if r.is_chronic is not None else False,
            "diagnosed_date": r.diagnosed_date,
            "notes": r.notes,
            "time_quantity": r.time_quantity,
            "time_unit": r.time_unit,
            "status": r.status,
        }
        for r in med_rows
    ]

    return life_events, medical


def _get_active_context_student_codes(
    session: Session,
    school_year_id: int,
    so_school_id: int | None = None,
) -> set[str]:
    """Lấy danh sách mã học sinh có biến cố ONGOING hoặc bệnh lý ONGOING theo trường."""
    school_filter = " AND so_school_id = :school_id" if so_school_id else ""
    params: Dict[str, Any] = {"sy": school_year_id}
    if so_school_id:
        params["school_id"] = so_school_id

    le_sql = text(f"""
        SELECT DISTINCT student_code FROM s360.fact_student_life_events
        WHERE school_year_id = :sy AND status = 'ONGOING' {school_filter}
    """)
    le_codes = {r[0] for r in session.execute(le_sql, params).fetchall()}

    med_sql = text(f"""
        SELECT DISTINCT student_code FROM s360.fact_student_medical_history
        WHERE school_year_id = :sy AND status = 'ONGOING' {school_filter}
    """)
    med_codes = {r[0] for r in session.execute(med_sql, params).fetchall()}

    return le_codes | med_codes


def _should_trigger(
    risk_level: str,
    life_events: List[Dict[str, Any]],
    medical: List[Dict[str, Any]],
) -> bool:
    """Kiểm tra trigger condition (xem docstring module)."""
    # Tạm thời bỏ HIGH để test trước (chỉ giữ CRITICAL)
    # if risk_level in ("HIGH", "CRITICAL"):
    if risk_level == "CRITICAL":
        return True
    # Biến cố ONGOING → trigger
    if any(ev.get("status") == "ONGOING" for ev in life_events):
        return True
    # Bệnh ONGOING + (mãn tính hoặc mức MODERATE/HIGH) → trigger
    for m in medical:
        if m.get("status") == "ONGOING":
            is_chronic = bool(m.get("is_chronic", False))
            severity = str(m.get("severity", "")).upper()
            if is_chronic or severity in ("MODERATE", "HIGH"):
                return True
    return False


# ============================================================================
# SINGLE-STUDENT FORECAST
# ============================================================================


def _normalize_llm_result(data: Dict[str, Any], cb_score: float) -> Dict[str, Any]:
    """Chuẩn hoá kết quả LLM về đúng schema cột llm_*."""
    llm_score = _safe_float(data.get("llm_risk_score"), cb_score)
    # Clamp 0-100
    llm_score = max(0.0, min(100.0, llm_score))

    level = str(data.get("llm_risk_level", "")).strip().upper()
    if level not in VALID_LLM_LEVELS:
        # Suy level từ score nếu LLM trả level không hợp lệ
        if llm_score >= 80:
            level = "CRITICAL"
        elif llm_score >= 60:
            level = "HIGH"
        elif llm_score >= 40:
            level = "MODERATE"
        else:
            level = "LOW"

    actions = data.get("llm_recommended_actions", [])
    if not isinstance(actions, list):
        actions = []

    return {
        "llm_risk_score": llm_score,
        "llm_risk_level": level,
        "llm_narrative_summary": str(data.get("llm_narrative_summary", "")).strip(),
        "llm_forecast_trend": str(data.get("llm_forecast_trend", "")).strip(),
        "llm_recommended_actions": json.dumps(actions, ensure_ascii=False),
        "llm_evaluated_at": datetime.now(timezone.utc),
    }


def forecast_student_risk(
    session: Session,
    student_code: str,
    subject_id: int,
    school_year_id: int,
    semester_index: int,
    evaluated_at_week: int,
    subject_name: str,
    features: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """Gọi LLM cho 1 học sinh, trả dict llm_* (hoặc None nếu không trigger/fail).

    features: dict chứa risk_score, risk_level + các feature chính (từ result DataFrame).
    """
    # Load context + kiểm tra trigger
    life_events, medical = _load_context(session, student_code, school_year_id)
    cb_level = str(features.get("risk_level", "UNKNOWN"))
    if not _should_trigger(cb_level, life_events, medical):
        logger.debug("[LLM Forecast] %s không thuộc nhóm trigger — bỏ qua", student_code)
        return None

    # Build prompt + gọi LLM
    prompt = _build_llm_prompt(
        student_code=student_code,
        subject_name=subject_name,
        features=features,
        life_events=life_events,
        medical=medical,
    )
    try:
        raw = _call_llm_with_retry(prompt)
        data = _parse_llm_response(raw)
    except Exception as exc:  # noqa: BLE001
        logger.warning("[LLM Forecast] Lỗi khi gọi LLM cho %s: %s", student_code, exc)
        return None

    cb_score = _safe_float(features.get("risk_score"))
    result = _normalize_llm_result(data, cb_score)

    # Persist ngay vào DB (cột llm_*)
    _persist_llm_columns(
        session,
        student_code=student_code,
        subject_id=subject_id,
        school_year_id=school_year_id,
        semester_index=semester_index,
        evaluated_at_week=evaluated_at_week,
        llm_cols=result,
    )
    return result


def _persist_llm_columns(
    session: Session,
    student_code: str,
    subject_id: int,
    school_year_id: int,
    semester_index: int,
    evaluated_at_week: int,
    llm_cols: Dict[str, Any],
) -> None:
    """UPDATE cột llm_* cho đúng dòng dự báo (khớp unique key)."""
    sql = text("""
        UPDATE s360.fact_student_subject_risk_predictions
        SET llm_risk_score = :llm_risk_score,
            llm_risk_level = :llm_risk_level,
            llm_narrative_summary = :llm_narrative_summary,
            llm_forecast_trend = :llm_forecast_trend,
            llm_recommended_actions = :llm_recommended_actions,
            llm_evaluated_at = :llm_evaluated_at
        WHERE student_code = :student_code
          AND subject_id = :subject_id
          AND school_year_id = :school_year_id
          AND semester_index = :semester_index
          AND evaluated_at_week = :evaluated_at_week
    """)
    session.execute(
        sql,
        {
            "llm_risk_score": llm_cols.get("llm_risk_score"),
            "llm_risk_level": llm_cols.get("llm_risk_level"),
            "llm_narrative_summary": llm_cols.get("llm_narrative_summary"),
            "llm_forecast_trend": llm_cols.get("llm_forecast_trend"),
            "llm_recommended_actions": llm_cols.get("llm_recommended_actions"),
            "llm_evaluated_at": llm_cols.get("llm_evaluated_at"),
            "student_code": student_code,
            "subject_id": subject_id,
            "school_year_id": school_year_id,
            "semester_index": semester_index,
            "evaluated_at_week": evaluated_at_week,
        },
    )
    session.commit()


# ============================================================================
# BATCH FORECAST
# ============================================================================


def _subject_name_for(session: Session, subject_id: int) -> str:
    """Lấy tên môn học (fallback 'Môn #id')."""
    row = session.execute(
        text("SELECT name FROM s360.dim_subject WHERE id = :sid"),
        {"sid": subject_id},
    ).fetchone()
    return row.name if row and row.name else f"Môn #{subject_id}"


def run_llm_forecasting_batch(
    session: Session,
    df: pd.DataFrame,
    school_year_id: int,
    semester_index: int,
    evaluated_at_week: int,
    so_school_id: int | None = None,
    enable: bool = True,
    dry_run: bool = False,
) -> pd.DataFrame:
    """Gọi LLM song song (thread pool) cho nhóm trigger trong df.

    df: DataFrame kết quả pipeline (chứa student_code, subject_id, risk_score,
    risk_level + features). Trả df đã gắn cột llm_* (None nếu không trigger/fail).

    enable=False → chỉ gắn cột llm_* = None, không gọi LLM.
    dry_run=True → chỉ đếm & log số bản ghi thỏa điều kiện trigger, không gọi LLM API.

    Concurrency: mỗi worker tạo session riêng (SessionLocal) — SQLAlchemy Session
    không thread-safe, nên không dùng chung session giữa các thread. Session truyền
    vào chỉ dùng để đọc tên môn học trước khi chạy.
    """
    # Luôn gắn cột llm_* mặc định None
    for col in LLM_OUTPUT_COLS:
        if col not in df.columns:
            df[col] = None

    if not enable or df.empty:
        return df

    settings = get_settings()
    max_workers = settings.llm_max_concurrency

    # Pre-filter: lấy danh sách học sinh có biến cố/bệnh ONGOING đáng chú ý từ DB theo đúng trường
    active_context_students = _get_active_context_student_codes(
        session, school_year_id, so_school_id=so_school_id
    )

    # Tạm thời bỏ HIGH để test trước (chỉ giữ CRITICAL)
    active_risk_levels = {"CRITICAL"}  # {"HIGH", "CRITICAL"}

    tasks = []
    seen = set()
    subject_names: Dict[int, str] = {}
    total_predictions = len(df)

    for _, row in df.iterrows():
        sc = str(row.get("student_code"))
        sid = _safe_int(row.get("subject_id"))
        key = (sc, sid)
        if key in seen:
            continue

        level = str(row.get("risk_level", "UNKNOWN"))
        is_trigger_level = level in active_risk_levels
        has_active_context = sc in active_context_students

        if not (is_trigger_level or has_active_context):
            continue

        seen.add(key)
        features = row.to_dict()
        tasks.append((sc, sid, features))
        if sid not in subject_names:
            subject_names[sid] = _subject_name_for(session, sid)

    # Thống kê phân rã theo risk_level của các task được chọn
    level_counts: Dict[str, int] = {}
    for t in tasks:
        lvl = str(t[2].get("risk_level", "UNKNOWN"))
        level_counts[lvl] = level_counts.get(lvl, 0) + 1

    lvl_str = ", ".join(f"{k}: {v}" for k, v in sorted(level_counts.items()))

    if dry_run:
        logger.info(
            "[LLM Forecast DRY-RUN] 🛑 Tìm thấy %d/%d bản ghi dự báo thỏa điều kiện trigger LLM (%s). Dừng chạy (Không gọi LLM API).",
            len(tasks),
            total_predictions,
            lvl_str,
        )
        return df

    logger.info(
        "[LLM Forecast] Lọc được %d/%d bản ghi dự báo thỏa điều kiện trigger LLM (%s, max_workers=%d)",
        len(tasks),
        total_predictions,
        lvl_str,
        max_workers,
    )

    results: Dict[tuple, Dict[str, Any]] = {}

    def _worker(task):
        """Chạy forecast cho 1 (student_code, subject_id) với session ngắn 2 đầu."""
        sc, sid, features = task
        # 1. Đọc context ngắn từ DB
        with SessionLocal() as s1:
            life_events, medical = _load_context(s1, sc, school_year_id)

        cb_level = str(features.get("risk_level", "UNKNOWN"))
        if not _should_trigger(cb_level, life_events, medical):
            return sc, sid, None

        # 2. Build prompt + gọi LLM (KHÔNG giữ DB connection trong lúc đợi HTTP API!)
        prompt = _build_llm_prompt(
            student_code=sc,
            subject_name=subject_names.get(sid, f"Môn #{sid}"),
            features=features,
            life_events=life_events,
            medical=medical,
        )
        try:
            raw = _call_llm_with_retry(prompt)
            data = _parse_llm_response(raw)
        except Exception as exc:  # noqa: BLE001
            logger.warning("[LLM Forecast] Lỗi khi gọi LLM cho %s: %s", sc, exc)
            return sc, sid, None

        cb_score = _safe_float(features.get("risk_score"))
        result = _normalize_llm_result(data, cb_score)

        # 3. Ghi kết quả vào DB nhanh trong session ngắn
        with SessionLocal() as s2:
            _persist_llm_columns(
                s2,
                student_code=sc,
                subject_id=sid,
                school_year_id=school_year_id,
                semester_index=semester_index,
                evaluated_at_week=evaluated_at_week,
                llm_cols=result,
            )
        return sc, sid, result

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(_worker, t) for t in tasks]
        for future in as_completed(futures):
            try:
                sc, sid, result = future.result()
                if result is not None:
                    results[(sc, sid)] = result
            except Exception as exc:  # noqa: BLE001
                logger.warning("[LLM Forecast] Lỗi xử lý task: %s", exc)
                continue

    # Gắn kết quả vào df (theo cặp student_code + subject_id)
    for idx, row in df.iterrows():
        sc = str(row.get("student_code"))
        sid = _safe_int(row.get("subject_id"))
        res = results.get((sc, sid))
        if res:
            for col in LLM_OUTPUT_COLS:
                df.at[idx, col] = res.get(col)

    done = len(results)
    logger.info("[LLM Forecast] Hoàn tất: %d/%d học sinh đã đánh giá", done, len(tasks))
    return df
