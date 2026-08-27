"""Interdisciplinary Early Warning System (EWS) Service.

Phân tích cảnh báo sớm rủi ro liên môn (STEM, Chiến Tranh & Hòa Bình...)
bằng mô hình Tích Hợp Thứ Bậc (Hierarchical Risk Aggregator) từ kết quả dự báo
đơn môn của CatBoost EWS + LLM.
"""

from __future__ import annotations

import logging
import math
import statistics
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Tuple

from sqlalchemy import text
from sqlalchemy.orm import Session

from src.ews.ews_config_service import get_effective_config
from src.ews.risk_config import RiskConfig, classify_risk_score, load_risk_config

logger = logging.getLogger(__name__)


# ============================================================================
# CẤU HÌNH CỤM LIÊN MÔN (CLUSTERS CONFIGURATION)
# ============================================================================

CLUSTERS_CONFIG: Dict[str, Dict[str, Any]] = {
    "STEM": {
        "code": "STEM",
        "name": "Liên Môn STEM",
        "full_name": "Khoa Học - Công Nghệ - Kỹ Thuật - Toán (STEM)",
        "description": "Tổ hợp 5 trụ cột liên môn Khoa học tự nhiên, Tin học, Kỹ thuật chế tạo và Năng lực Toán học.",
        "icon": "Cpu",
        "color": "#6366f1",  # Indigo
        "pillars": [
            {
                "id": "math",
                "name": "Toán học",
                "weight": 0.30,
                "matcher": lambda code, name: ("TOAN" in code.upper() or "MATH" in code.upper()),
                "aggregation": "mean",  # Lấy trung bình cộng nếu học sinh học nhiều môn Toán
            },
            {
                "id": "physics",
                "name": "Vật lý",
                "weight": 0.20,
                "matcher": lambda code, name: (code.upper() == "LY" or "VẬT LÝ" in name.upper()),
            },
            {
                "id": "biology",
                "name": "Sinh học",
                "weight": 0.20,
                "matcher": lambda code, name: (
                    code.upper() in ("SINH", "HOA", "KHTN")
                    or "SINH HỌC" in name.upper()
                    or "HÓA HỌC" in name.upper()
                    or "KHOA HỌC TỰ NHIÊN" in name.upper()
                ),
            },
            {
                "id": "technology",
                "name": "Tin học",
                "weight": 0.15,
                "matcher": lambda code, name: (code.upper() == "TIN" or "TIN HỌC" in name.upper()),
            },
            {
                "id": "engineering",
                "name": "STEM Robotics",
                "weight": 0.15,
                "matcher": lambda code, name: ("ROBOTICS" in code.upper() or "CÔNG NGHỆ" in name.upper()),
                "is_elective": True,
            },
        ],
    },
    "WAR_AND_PEACE": {
        "code": "WAR_AND_PEACE",
        "name": "Chiến Tranh & Hòa Bình",
        "full_name": "Khoa Học Xã Hội & Nhân Văn (Chiến Tranh & Hòa Bình)",
        "description": "Chuyên đề tích hợp Ngữ văn, Bối cảnh Lịch sử - Không gian Địa lý và Ý thức Giáo dục Công dân.",
        "icon": "BookOpen",
        "color": "#ec4899",  # Pink/Rose
        "pillars": [
            {
                "id": "literature",
                "name": "Ngữ văn",
                "weight": 0.40,
                "matcher": lambda code, name: (code.upper() == "VAN" or "VĂN" in name.upper()),
            },
            {
                "id": "history_geography",
                "name": "Lịch sử & Địa lý",
                "weight": 0.40,
                "matcher": lambda code, name: (
                    code.upper() in ("LS_DL", "SU", "DIA")
                    or "LỊCH SỬ" in name.upper()
                    or "ĐỊA LÝ" in name.upper()
                ),
            },
            {
                "id": "civics",
                "name": "Giáo dục công dân",
                "weight": 0.20,
                "matcher": lambda code, name: (code.upper() == "GDCD" or "CÔNG DÂN" in name.upper()),
            },
        ],
    },
}


# ============================================================================
# DATA STRUCTURES
# ============================================================================

@dataclass
class PillarResult:
    pillar_id: str
    pillar_name: str
    base_weight: float
    normalized_weight: float
    risk_score: float
    risk_level: str
    enrolled_subjects: List[Dict[str, Any]]
    is_active: bool


@dataclass
class StudentInterdisciplinaryResult:
    student_code: str
    student_name: str
    class_name: str
    grade_id: Optional[int]
    cluster_code: str
    cluster_name: str
    cluster_risk_score: float
    cluster_risk_level: str
    bottleneck_subject: Optional[str]
    bottleneck_risk: Optional[float]
    anchor_subject: Optional[str]
    anchor_risk: Optional[float]
    disparity_index: float
    pillars: List[PillarResult]
    has_llm: bool


# ============================================================================
# ALGORITHM: CALCULATE CLUSTER RISK FOR 1 STUDENT
# ============================================================================

def calculate_student_cluster_risk(
    student_info: Dict[str, Any],
    subject_predictions: List[Dict[str, Any]],
    cluster_code: str,
    cfg: Optional[RiskConfig] = None,
) -> Optional[StudentInterdisciplinaryResult]:
    """Tính toán điểm rủi ro liên môn cho 1 học sinh theo cấu hình cụm.

    - Xử lý trung bình môn Toán nếu học nhiều môn Toán.
    - Chuẩn hóa lại trọng số (Re-weighting) theo các môn thực học.
    - Bắt môn Nút thắt cổ chai (Bottleneck) và môn Trụ cột (Anchor).
    - Tính chỉ số Lệch pha (Disparity).
    """
    cluster_cfg = CLUSTERS_CONFIG.get(cluster_code)
    if not cluster_cfg:
        return None

    if cfg is None:
        cfg = load_risk_config()

    active_pillars: List[Dict[str, Any]] = []

    for pillar in cluster_cfg["pillars"]:
        matcher: Callable[[str, str], bool] = pillar["matcher"]
        aggregation = pillar.get("aggregation", "first")

        # Tìm các môn học sinh thực học khớp với pillar này
        matched_preds = []
        for p in subject_predictions:
            sub_code = str(p.get("subject_code") or "")
            sub_name = str(p.get("subject_name") or "")
            if matcher(sub_code, sub_name):
                # Điểm rủi ro hiệu lực (ưu tiên LLM nếu có)
                llm_score = p.get("llm_risk_score")
                eff_score = float(llm_score) if llm_score is not None else float(p.get("risk_score", 0.0))
                llm_level = p.get("llm_risk_level")
                eff_level = str(llm_level) if llm_level else str(p.get("risk_level", "UNKNOWN"))

                matched_preds.append({
                    "subject_id": p.get("subject_id"),
                    "subject_code": sub_code,
                    "subject_name": sub_name,
                    "risk_score": eff_score,
                    "risk_level": eff_level,
                    "last_score": p.get("last_score"),
                    "score_slope": p.get("score_slope"),
                    "has_llm": bool(llm_score is not None),
                })

        if matched_preds:
            if aggregation == "mean":
                # Lấy trung bình cộng (ví dụ: nhiều môn Toán)
                avg_score = statistics.mean([m["risk_score"] for m in matched_preds])
                pillar_level = classify_risk_score(avg_score, cfg)
                pillar_data = {
                    "pillar_id": pillar["id"],
                    "pillar_name": pillar["name"],
                    "base_weight": pillar["weight"],
                    "risk_score": round(avg_score, 2),
                    "risk_level": pillar_level,
                    "enrolled_subjects": matched_preds,
                    "is_active": True,
                }
            else:
                top_pred = matched_preds[0]
                pillar_data = {
                    "pillar_id": pillar["id"],
                    "pillar_name": pillar["name"],
                    "base_weight": pillar["weight"],
                    "risk_score": round(top_pred["risk_score"], 2),
                    "risk_level": top_pred["risk_level"],
                    "enrolled_subjects": matched_preds,
                    "is_active": True,
                }
            active_pillars.append(pillar_data)

    # Nếu học sinh không học bất kỳ môn nào trong cụm -> bỏ qua
    if not active_pillars:
        return None

    # Chuẩn hóa trọng số theo các môn thực học
    sum_base_weights = sum(p["base_weight"] for p in active_pillars)
    for p in active_pillars:
        norm_w = p["base_weight"] / sum_base_weights if sum_base_weights > 0 else (1.0 / len(active_pillars))
        p["normalized_weight"] = round(norm_w, 4)

    # Tính điểm trung bình có trọng số thực học
    weighted_risk = sum(p["normalized_weight"] * p["risk_score"] for p in active_pillars)

    # Tìm môn Bottleneck (nút thắt kéo tụt) & Anchor (môn trụ cột nâng đỡ)
    sorted_by_risk = sorted(active_pillars, key=lambda x: x["risk_score"], reverse=True)
    worst_p = sorted_by_risk[0]
    best_p = sorted_by_risk[-1]

    bottleneck_subject: Optional[str] = None
    bottleneck_risk: Optional[float] = None
    bottleneck_penalty = 0.0

    # Điều kiện kích hoạt Bottleneck (Nút thắt kéo tụt):
    # 1. Môn điểm rủi ro cao >= 70 và vượt trung bình cụm >= 12 điểm (nguy cơ cao kéo tụt)
    # HOẶC 2. Môn bước vào vùng cảnh báo (>= 45.0) và vượt trung bình cụm >= 15 điểm (kéo lệch cả cụm)
    is_bottleneck = (
        (worst_p["risk_score"] >= 70.0 and (worst_p["risk_score"] - weighted_risk) >= 12.0)
        or (worst_p["risk_score"] >= 45.0 and (worst_p["risk_score"] - weighted_risk) >= 15.0)
    )
    if is_bottleneck:
        bottleneck_penalty = (worst_p["risk_score"] - weighted_risk) * 0.25
        bottleneck_subject = worst_p["pillar_name"]
        bottleneck_risk = worst_p["risk_score"]

    anchor_subject: Optional[str] = None
    anchor_risk: Optional[float] = None
    # Môn trụ cột nâng đỡ: môn có rủi ro thấp <= 35 và thấp hơn trung bình cụm >= 12 điểm
    if best_p["risk_score"] <= 35.0 and (weighted_risk - best_p["risk_score"]) >= 12.0:
        anchor_subject = best_p["pillar_name"]
        anchor_risk = best_p["risk_score"]

    # Độ lệch pha (Disparity Index)
    scores_list = [p["risk_score"] for p in active_pillars]
    disparity = statistics.stdev(scores_list) if len(scores_list) > 1 else 0.0

    # Tổng hợp điểm rủi ro cụm liên môn
    final_cluster_score = min(100.0, max(0.0, weighted_risk + bottleneck_penalty))
    final_cluster_level = classify_risk_score(final_cluster_score, cfg)

    # Gộp tất cả pillar results
    all_pillar_results: List[PillarResult] = []
    for p_cfg in cluster_cfg["pillars"]:
        active_match = next((ap for ap in active_pillars if ap["pillar_id"] == p_cfg["id"]), None)
        if active_match:
            all_pillar_results.append(PillarResult(
                pillar_id=active_match["pillar_id"],
                pillar_name=active_match["pillar_name"],
                base_weight=active_match["base_weight"],
                normalized_weight=active_match["normalized_weight"],
                risk_score=active_match["risk_score"],
                risk_level=active_match["risk_level"],
                enrolled_subjects=active_match["enrolled_subjects"],
                is_active=True,
            ))
        else:
            all_pillar_results.append(PillarResult(
                pillar_id=p_cfg["id"],
                pillar_name=p_cfg["name"],
                base_weight=p_cfg["weight"],
                normalized_weight=0.0,
                risk_score=0.0,
                risk_level="NOT_ENROLLED",
                enrolled_subjects=[],
                is_active=False,
            ))

    has_any_llm = any(
        any(s.get("has_llm") for s in p.enrolled_subjects)
        for p in all_pillar_results
    )

    return StudentInterdisciplinaryResult(
        student_code=student_info["student_code"],
        student_name=student_info.get("student_name") or student_info["student_code"],
        class_name=student_info.get("class_name") or "—",
        grade_id=student_info.get("grade_id"),
        cluster_code=cluster_code,
        cluster_name=cluster_cfg["name"],
        cluster_risk_score=round(final_cluster_score, 2),
        cluster_risk_level=final_cluster_level,
        bottleneck_subject=bottleneck_subject,
        bottleneck_risk=round(bottleneck_risk, 2) if bottleneck_risk is not None else None,
        anchor_subject=anchor_subject,
        anchor_risk=round(anchor_risk, 2) if anchor_risk is not None else None,
        disparity_index=round(disparity, 2),
        pillars=all_pillar_results,
        has_llm=has_any_llm,
    )


# ============================================================================
# DATABASE QUERY & DATA FETCHING
# ============================================================================

def fetch_student_predictions_batch(
    session: Session,
    school_year_id: int,
    semester_index: int,
    evaluated_at_week: int,
    so_school_id: Optional[int] = None,
    model_version: Optional[str] = None,
) -> Dict[str, Dict[str, Any]]:
    """Truy vấn tất cả kết quả EWS của học sinh trong tuần/kỳ gom nhóm theo student_code."""
    where_clauses = [
        "rp.school_year_id = :sy",
        "rp.semester_index = :sem",
        "rp.evaluated_at_week = :wk",
    ]
    params: Dict[str, Any] = {
        "sy": school_year_id,
        "sem": semester_index,
        "wk": evaluated_at_week,
    }
    if so_school_id is not None:
        where_clauses.append("rp.so_school_id = :so_school_id")
        params["so_school_id"] = so_school_id
    if model_version is not None:
        where_clauses.append("rp.model_version = :model_version")
        params["model_version"] = str(model_version)

    where_sql = " AND ".join(where_clauses)

    sql = text(f"""
        WITH ranked_hcs AS (
            SELECT
                hcs.student_code,
                hcs.student_name,
                hcs.class_name,
                hcs.grade_id,
                hcs.so_school_id,
                ROW_NUMBER() OVER (
                    PARTITION BY hcs.student_code, hcs.so_school_id
                    ORDER BY hcs.id DESC
                ) AS rn
            FROM s360.dim_homeroom_class_student hcs
            WHERE hcs.school_year_id = :sy
        )
        SELECT
            rp.student_code,
            COALESCE(hcs.student_name, rp.student_code) AS student_name,
            COALESCE(hcs.class_name, '—') AS class_name,
            hcs.grade_id,
            rp.subject_id,
            sub.code AS subject_code,
            sub.name AS subject_name,
            sub.subject_category,
            rp.risk_score,
            rp.risk_level,
            rp.risk_probability,
            rp.score_risk,
            rp.lms_risk,
            rp.attendance_risk,
            rp.behavior_risk,
            rp.last_score,
            rp.score_slope,
            rp.llm_risk_score,
            rp.llm_risk_level
        FROM s360.fact_student_subject_risk_predictions rp
        LEFT JOIN ranked_hcs hcs ON rp.student_code = hcs.student_code AND hcs.so_school_id = rp.so_school_id AND hcs.rn = 1
        LEFT JOIN s360.dim_subject sub ON rp.subject_id = sub.id
        WHERE {where_sql}
        ORDER BY rp.student_code, rp.subject_id;
    """)

    rows = session.execute(sql, params).fetchall()

    students_map: Dict[str, Dict[str, Any]] = {}
    for r in rows:
        sc = r.student_code
        if sc not in students_map:
            students_map[sc] = {
                "student_info": {
                    "student_code": sc,
                    "student_name": r.student_name,
                    "class_name": r.class_name,
                    "grade_id": r.grade_id,
                },
                "predictions": [],
            }
        students_map[sc]["predictions"].append({
            "subject_id": r.subject_id,
            "subject_code": r.subject_code or "",
            "subject_name": r.subject_name or "",
            "subject_category": r.subject_category or "",
            "risk_score": r.risk_score,
            "risk_level": r.risk_level,
            "risk_probability": r.risk_probability,
            "score_risk": r.score_risk,
            "lms_risk": r.lms_risk,
            "attendance_risk": r.attendance_risk,
            "behavior_risk": r.behavior_risk,
            "last_score": r.last_score,
            "score_slope": r.score_slope,
            "llm_risk_score": r.llm_risk_score,
            "llm_risk_level": r.llm_risk_level,
        })

    return students_map


# ============================================================================
# API SERVICE METHODS
# ============================================================================

def get_clusters_list() -> List[Dict[str, Any]]:
    """Trả danh sách định nghĩa cụm liên môn cho UI selector."""
    return [
        {
            "code": c["code"],
            "name": c["name"],
            "full_name": c["full_name"],
            "description": c["description"],
            "icon": c["icon"],
            "color": c["color"],
            "pillar_count": len(c["pillars"]),
            "pillars": [
                {"id": p["id"], "name": p["name"], "weight": p["weight"]}
                for p in c["pillars"]
            ],
        }
        for c in CLUSTERS_CONFIG.values()
    ]


def get_cluster_overview_metrics(
    session: Session,
    school_year_id: int,
    semester_index: int,
    evaluated_at_week: int,
    cluster_code: str = "STEM",
    so_school_id: Optional[int] = None,
    model_version: Optional[str] = None,
) -> Dict[str, Any]:
    """Tính toán thống kê KPIs tổng quan của một cụm liên môn."""
    cfg = (
        get_effective_config(session, so_school_id)
        if so_school_id is not None
        else load_risk_config()
    )

    students_map = fetch_student_predictions_batch(
        session, school_year_id, semester_index, evaluated_at_week,
        so_school_id=so_school_id, model_version=model_version,
    )

    results: List[StudentInterdisciplinaryResult] = []
    for sc, data in students_map.items():
        res = calculate_student_cluster_risk(
            data["student_info"], data["predictions"], cluster_code, cfg=cfg
        )
        if res:
            results.append(res)

    total_students = len(results)
    if total_students == 0:
        return {
            "cluster_code": cluster_code,
            "total_students": 0,
            "avg_cluster_risk": 0.0,
            "risk_distribution": {"CRITICAL": 0, "HIGH": 0, "MODERATE": 0, "LOW": 0},
            "bottleneck_count": 0,
            "bottleneck_ratio": 0.0,
            "top_bottlenecks": [],
        }

    risk_dist = {"CRITICAL": 0, "HIGH": 0, "MODERATE": 0, "LOW": 0}
    bottleneck_counts: Dict[str, int] = {}
    bottleneck_total = 0
    sum_scores = 0.0

    for r in results:
        sum_scores += r.cluster_risk_score
        risk_dist[r.cluster_risk_level] = risk_dist.get(r.cluster_risk_level, 0) + 1
        if r.bottleneck_subject:
            bottleneck_total += 1
            bottleneck_counts[r.bottleneck_subject] = bottleneck_counts.get(r.bottleneck_subject, 0) + 1

    top_bottlenecks = [
        {"subject_name": k, "count": v, "percentage": round(v / total_students * 100, 1)}
        for k, v in sorted(bottleneck_counts.items(), key=lambda x: x[1], reverse=True)
    ]

    return {
        "cluster_code": cluster_code,
        "total_students": total_students,
        "avg_cluster_risk": round(sum_scores / total_students, 2),
        "risk_distribution": risk_dist,
        "bottleneck_count": bottleneck_total,
        "bottleneck_ratio": round(bottleneck_total / total_students * 100, 1),
        "top_bottlenecks": top_bottlenecks,
    }


def get_students_interdisciplinary_paged(
    session: Session,
    school_year_id: int,
    semester_index: int,
    evaluated_at_week: int,
    cluster_code: str = "STEM",
    risk_level: str = "ALL",
    grade_id: Optional[int] = None,
    class_name: Optional[str] = None,
    bottleneck_only: bool = False,
    page: int = 1,
    page_size: int = 20,
    so_school_id: Optional[int] = None,
    model_version: Optional[str] = None,
) -> Dict[str, Any]:
    """Lấy danh sách phân trang học sinh có nguy cơ liên môn."""
    cfg = (
        get_effective_config(session, so_school_id)
        if so_school_id is not None
        else load_risk_config()
    )

    students_map = fetch_student_predictions_batch(
        session, school_year_id, semester_index, evaluated_at_week,
        so_school_id=so_school_id, model_version=model_version,
    )

    all_results: List[StudentInterdisciplinaryResult] = []
    for sc, data in students_map.items():
        res = calculate_student_cluster_risk(
            data["student_info"], data["predictions"], cluster_code, cfg=cfg
        )
        if res:
            all_results.append(res)

    # Bộ lọc
    filtered = all_results
    if risk_level and risk_level != "ALL":
        filtered = [r for r in filtered if r.cluster_risk_level == risk_level]

    if grade_id is not None:
        filtered = [r for r in filtered if r.grade_id == grade_id]

    if class_name and class_name != "ALL":
        clean_cls = class_name.strip().lower()
        filtered = [r for r in filtered if clean_cls in r.class_name.strip().lower()]

    if bottleneck_only:
        filtered = [r for r in filtered if r.bottleneck_subject is not None]

    # Sắp xếp theo điểm rủi ro cụm giảm dần
    filtered.sort(key=lambda x: x.cluster_risk_score, reverse=True)

    total_count = len(filtered)
    total_pages = max(1, math.ceil(total_count / page_size))
    offset = (page - 1) * page_size
    paged_items = filtered[offset:offset + page_size]

    items_data = [
        {
            "student_code": r.student_code,
            "student_name": r.student_name,
            "class_name": r.class_name,
            "grade_id": r.grade_id,
            "cluster_code": r.cluster_code,
            "cluster_name": r.cluster_name,
            "cluster_risk_score": r.cluster_risk_score,
            "cluster_risk_level": r.cluster_risk_level,
            "bottleneck_subject": r.bottleneck_subject,
            "bottleneck_risk": r.bottleneck_risk,
            "anchor_subject": r.anchor_subject,
            "anchor_risk": r.anchor_risk,
            "disparity_index": r.disparity_index,
            "has_llm": r.has_llm,
            "pillars": [
                {
                    "pillar_id": p.pillar_id,
                    "pillar_name": p.pillar_name,
                    "weight": p.normalized_weight,
                    "risk_score": p.risk_score,
                    "risk_level": p.risk_level,
                    "is_active": p.is_active,
                    "enrolled_subjects": p.enrolled_subjects,
                }
                for p in r.pillars
            ],
        }
        for r in paged_items
    ]

    return {
        "items": items_data,
        "total": total_count,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
    }
