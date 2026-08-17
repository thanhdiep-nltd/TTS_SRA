# -*- coding: utf-8 -*-
"""
MASTER GOLDEN SET MOCK DATA GENERATOR FOR TTS_SRA (v4 - 23 SUBJECTS, 2 SCHOOLS, 100-1500 STUDENTS)
========================================================================================================
Production-Ready Data Synthesis Engine for Educational EWS / At-Risk Prediction.

MATHEMATICAL FOUNDATIONS (v4 - Causal Copula + AR(1) + Logistic Decay):
--------------------------------------------------------------------------------
1. LATENT CAUSAL MODEL (Gaussian Copula):
   Sinh 6 latent variables với correlation matrix R phản ánh causal chain thực tế:
       Chuyên cần (attend) -> LMS (lms_effort) -> Kỷ luật (conduct) -> Điểm thi (ability)
   Dùng Cholesky decomposition R = L·Lᵀ để tạo biến chuẩn tương quan, sau đó
   transform qua inverse-CDF (Gaussian Copula) sang phân phối biên mong muốn.

2. AR(1) AUTO-REGRESSIVE DECAY (temporal dependency):
   Mỗi chuỗi thời gian (điểm thi, LMS, chuyên cần) tuân theo:
       X_t = φ·X_{t-1} + (1-φ)·μ + ε_t,  ε_t ~ N(0, σ²)
   φ ∈ [0,1] là hệ số tự tương quan (persistence). φ cao -> chuỗi ổn định,
   φ thấp -> chuỗi nhiễu. Điều này KHẮC PHỤC lỗi "gieo nhiễu i.i.d" của v2/v3.

3. LOGISTIC DECAY (crisis / at-risk trajectory):
   Khi học sinh gặp biến cố (crisis) tại tuần t_c, điểm số suy giảm theo hàm logistic:
       drop(t) = D_max / (1 + exp(-k·(t - t_c)))
   D_max = biên độ suy giảm tối đa, k = tốc độ suy giảm. Tạo "điểm gãy" (breakpoint)
   thực tế thay vì giảm tuyến tính đều.

4. CAUSAL CHAIN (SEM - Structural Equation Model):
       Chuyên cần (t)  ->  LMS (t+1w)  ->  Kỷ luật (t+2w)  ->  Điểm thi (t+3w)
   Mỗi mắt xích có độ trễ 1 tuần, phản ánh cơ chế nhân quả thực tế:
   - Học sinh nghỉ nhiều (tuần t) -> bỏ bài LMS (tuần t+1) -> vi phạm kỷ luật (t+2)
     -> điểm thi giảm (t+3). Điều này tạo temporal asymmetry ĐÚNG cho EWS feature extractor.

5. 23 MÔN HỌC (2 trường, 100-1500 học sinh/trường):
   - Môn quốc gia MOET (SCALE_10): 106-111 (TOAN_6..11), 2 (VAN), 3 (ANH), 4 (LY),
     5 (HOA), 6 (SINH), 7 (KHTN), 8 (LS_DL)
   - Môn quốc tế: 9 (CAM_ENG, LETTER_AF), 10 (CAM_MATH, LETTER_AF), 11 (IB_MATH, SCALE_6),
     12 (IB_SCI, SCALE_6), 13 (TIN, SCALE_100), 14 (ROBOTICS, SCALE_100), 15 (GPA_HONOR, SCALE_4)
   - Môn đánh giá nhận xét (REMARK/PASS_FAIL): 16 (THE_DUC), 17 (MY_THUAT), 18 (AM_NHAC)

6. TOÀN VẸN SCHEMA 37 BẢNG: Không làm gãy schema SQL hiện tại. Seed đầy đủ:
   public (users, refresh_tokens, teacher_assignments, exam_papers, curriculum_units,
   exam_competencies, audit_logs, report_schedules, classroom_recordings, ai_*)
   s360 (dim_* + fact_* + fact_swb_*)

7. LOGGER + VALIDATION CHECK: Gắn sẵn logging, correlation matrix validation,
   schema integrity check, distribution sanity check sau khi seed.

COVERAGE: 37+ Tables (public + s360 schemas) + Data Serialization CLI (--export-serialized).
"""

import sys
import os
import random
import argparse
import json
import math
import logging
from datetime import datetime, timedelta, date
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any

import numpy as np

# Ensure project root is on sys.path
if __name__ == "__main__" and __package__ is None:
    _root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    if _root not in sys.path:
        sys.path.insert(0, _root)

from sqlalchemy import text
from src.db.session import SessionLocal
from src.services.metadata_indexer import sync_school_metadata
from src.core.security import hash_password

# ============================================================================
# LOGGING SETUP
# ============================================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("GoldenSetGeneratorV4")

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

# Random Seeds for Deterministic Reproducibility
SEED = 42
np.random.seed(SEED)
random.seed(SEED)

DEFAULT_HASHED_PASSWORD = hash_password("password123")
BATCH_SIZE = 5000

# Fixed Dates for School Year 2025-2026
SCHOOL_YEAR_START = date(2025, 9, 1)
SCHOOL_YEAR_END = date(2026, 5, 31)

# ============================================================================
# 23 MÔN HỌC (subject_id, code, name, name_en, assessment_type, scale_name, subject_category)
# ============================================================================
SUBJECTS_23 = [
    # Môn quốc gia MOET (SCALE_10)
    (106, 'TOAN_6', 'Toán 6', 'Mathematics 6', 'SCORED', 'SCALE_10', 'MATH_SCIENCE'),
    (107, 'TOAN_7', 'Toán 7', 'Mathematics 7', 'SCORED', 'SCALE_10', 'MATH_SCIENCE'),
    (108, 'TOAN_8', 'Toán 8', 'Mathematics 8', 'SCORED', 'SCALE_10', 'MATH_SCIENCE'),
    (109, 'TOAN_9', 'Toán 9', 'Mathematics 9', 'SCORED', 'SCALE_10', 'MATH_SCIENCE'),
    (110, 'TOAN_10', 'Toán 10', 'Mathematics 10', 'SCORED', 'SCALE_10', 'MATH_SCIENCE'),
    (111, 'TOAN_11', 'Toán 11', 'Mathematics 11', 'SCORED', 'SCALE_10', 'MATH_SCIENCE'),
    (2, 'VAN', 'Ngữ văn', 'Literature', 'SCORED', 'SCALE_10', 'HUMANITIES'),
    (3, 'ANH', 'Tiếng Anh', 'English', 'SCORED', 'SCALE_10', 'HUMANITIES'),
    (4, 'LY', 'Vật lý', 'Physics', 'SCORED', 'SCALE_10', 'MATH_SCIENCE'),
    (5, 'HOA', 'Hóa học', 'Chemistry', 'SCORED', 'SCALE_10', 'MATH_SCIENCE'),
    (6, 'SINH', 'Sinh học', 'Biology', 'SCORED', 'SCALE_10', 'MATH_SCIENCE'),
    (7, 'KHTN', 'Khoa học tự nhiên', 'Natural Sciences', 'SCORED', 'SCALE_10', 'MATH_SCIENCE'),
    (8, 'LS_DL', 'Lịch sử & Địa lý', 'History & Geography', 'SCORED', 'SCALE_10', 'HUMANITIES'),
    # Môn quốc tế
    (9, 'CAM_ENG', 'Tiếng Anh Cambridge', 'Cambridge ESL', 'SCORED', 'LETTER_AF', 'HUMANITIES'),
    (10, 'CAM_MATH', 'Toán Cambridge', 'Cambridge Math', 'SCORED', 'LETTER_AF', 'MATH_SCIENCE'),
    (11, 'IB_MATH', 'Toán IB', 'IB Mathematics', 'SCORED', 'SCALE_6', 'MATH_SCIENCE'),
    (12, 'IB_SCI', 'Khoa học IB', 'IB Science', 'SCORED', 'SCALE_6', 'MATH_SCIENCE'),
    (13, 'TIN', 'Tin học', 'Computer Science', 'SCORED', 'SCALE_100', 'TECHNOLOGY'),
    (14, 'ROBOTICS', 'STEM Robotics', 'STEM Robotics', 'SCORED', 'SCALE_100', 'TECHNOLOGY'),
    (15, 'GPA_HONOR', 'Môn Chuyên Honor', 'Honor Course', 'SCORED', 'SCALE_4', 'MATH_SCIENCE'),
    # Môn đánh giá nhận xét
    (16, 'THE_DUC', 'Giáo dục thể chất', 'Physical Education', 'REMARK', 'PASS_FAIL', 'ARTS_PE'),
    (17, 'MY_THUAT', 'Mỹ thuật', 'Fine Arts', 'REMARK', 'PASS_FAIL', 'ARTS_PE'),
    (18, 'AM_NHAC', 'Âm nhạc', 'Music', 'REMARK', 'PASS_FAIL', 'ARTS_PE'),
    (19, 'GDCD', 'Giáo dục công dân', 'Civic Education', 'SCORED', 'SCALE_10', 'HUMANITIES'),
]

# ============================================================================
# CORRELATION MATRIX (Copula) — Causal Chain: attend -> lms -> conduct -> ability
# 6 latent variables: [ability_math, ability_lang, eff, attend, lms_effort, conduct]
# ============================================================================
# Ma trận tương quan phản ánh causal chain thực tế:
#   ability_math  ~ ability_lang (0.6) — năng lực học tập tương quan
#   attend -> lms_effort (0.7)      — chuyên cần cao -> nộp bài LMS tốt
#   lms_effort -> conduct (0.6)      — nộp bài tốt -> ít vi phạm
#   conduct -> ability (0.5)          — kỷ luật tốt -> điểm cao
#   eff (hiệu quả) tương quan mọi thứ (0.3-0.5)
CORR_MATRIX = np.array([
    [1.0, 0.6, 0.4, 0.3, 0.4, 0.3],  # ability_math
    [0.6, 1.0, 0.4, 0.3, 0.4, 0.3],  # ability_lang
    [0.4, 0.4, 1.0, 0.5, 0.5, 0.4],  # eff
    [0.3, 0.3, 0.5, 1.0, 0.7, 0.6],  # attend
    [0.4, 0.4, 0.5, 0.7, 1.0, 0.6],  # lms_effort
    [0.3, 0.3, 0.4, 0.6, 0.6, 1.0],  # conduct
])

# ============================================================================
# AR(1) CONFIG
# ============================================================================
AR1_PHI = 0.85  # Hệ số tự tương quan mặc định (persistence)
AR1_NOISE = 0.3  # Độ nhiễu AR(1)

# ============================================================================
# LOGISTIC DECAY CONFIG (crisis)
# ============================================================================
LOGISTIC_K = 0.8  # Tốc độ suy giảm logistic
LOGISTIC_D_MAX = 3.0  # Biên độ suy giảm tối đa

# ============================================================================
# EXAM CREATED_AT — NGÀY THỰC TẾ CỦA TỪNG MỐC ĐIỂM (QUAN TRỌNG CHO EWS)
# ============================================================================
# EWS feature_extractor lọc `is_locked = 1` VÀ `created_at <= cutoff_date`.
# Nếu created_at = NOW() (2026) > cutoff (2025-09-29) → 0 rows → pipeline fail.
# Các mốc này được đặt trong quá khứ (đầu năm học) để có dữ liệu trước cutoff.
EXAM_CREATED_AT = {
    1: datetime(2025, 9, 12, 8, 0, 0),   # TX đầu HK1 (trước cutoff week 5 = 2025-09-29)
    2: datetime(2025, 10, 10, 8, 0, 0),  # Giữa kỳ HK1 (trước cutoff week 8 = 2025-10-21)
    3: datetime(2026, 1, 22, 8, 0, 0),   # Mốc đầu HK2
}

# ============================================================================
# RISK STRATIFICATION (Golden Set)
# ============================================================================
RISK_POOL = ['SAFE'] * 68 + ['MODERATE'] * 17 + ['HIGH'] * 9 + ['CRITICAL'] * 6

# ============================================================================
# SCORE PROFILES G1-G9 (PHÂN PHỐI ĐIỂM NHƯ V2 — trải rộng 0-10)
# ============================================================================
# Tái sử dụng phân phối điểm của v2 (generate_train_dataset.py) để tạo đa dạng:
#   G1: cao ổn định (8-10)      G2: TB ổn định (5.5-7.8)   G3: cải thiện dần
#   G4: TB-thấp biến động (3.8-5.5)  G5: cao giảm dần      G6: thấp, LMS bù (2-4)
#   G7: giảm mạnh (3-5)         G8: rất thấp (1.5-3.4)     G9: zero (0)
PROFILE_WEIGHTS = {"G1": 10, "G2": 20, "G3": 12, "G4": 15, "G5": 8,
                   "G6": 10, "G7": 12, "G8": 8, "G9": 5}
PROFILE_LIST = list(PROFILE_WEIGHTS.keys())
PROFILE_PROB = [PROFILE_WEIGHTS[p] / sum(PROFILE_WEIGHTS.values()) for p in PROFILE_LIST]

# base_ability (điểm gốc 0-10) theo profile — trải rộng như v2
PROFILE_BASE_ABILITY = {
    "G1": 9.0, "G2": 6.5, "G3": 5.5, "G4": 4.5, "G5": 7.0,
    "G6": 3.0, "G7": 4.0, "G8": 2.5, "G9": 0.5,
}

# ============================================================================
# VIETNAMESE NAMES
# ============================================================================
FIRST_NAMES = ["An", "Bình", "Cường", "Dương", "Đạt", "Đức", "Giang", "Hải", "Hào", "Hương", "Huy", "Khánh", "Lâm", "Linh", "Long", "Minh", "Nam", "Nga", "Nhi", "Phúc", "Quang", "Quỳnh", "Sơn", "Tâm", "Thảo", "Thịnh", "Trang", "Tú", "Tuấn", "Vinh"]
MIDDLE_NAMES = ["Văn", "Thị", "Hồng", "Minh", "Đức", "Ngọc", "Thành", "Phương", "Hoàng", "Bảo", "Đình", "Gia", "Khánh"]
LAST_NAMES = ["Nguyễn", "Trần", "Lê", "Phạm", "Hoàng", "Huỳnh", "Vũ", "Võ", "Đặng", "Bùi", "Đỗ", "Hồ", "Ngô", "Dương", "Lý"]

def generate_vietnamese_name():
    return f"{random.choice(LAST_NAMES)} {random.choice(MIDDLE_NAMES)} {random.choice(FIRST_NAMES)}"


# ============================================================================
# COPULA-BASED LATENT VARIABLE GENERATOR
# ============================================================================
def generate_correlated_latents(n: int, corr_matrix: np.ndarray, seed: int = SEED) -> np.ndarray:
    """
    Sinh n vector latent variables tương quan bằng Gaussian Copula.
    - Sinh Z ~ N(0, R) với R = corr_matrix (Cholesky decomposition)
    - Transform qua inverse-CDF chuẩn -> uniform(0,1) -> phân phối biên mong muốn
    Returns: (n, 6) array [ability_math, ability_lang, eff, attend, lms_effort, conduct]
    """
    rng = np.random.default_rng(seed)
    # Cholesky decomposition R = L·Lᵀ
    L = np.linalg.cholesky(corr_matrix)
    Z = rng.standard_normal((n, corr_matrix.shape[0])) @ L.T
    # Transform sang uniform(0,1) qua CDF chuẩn
    U = 0.5 * (1.0 + np.vectorize(math.erf)(Z / math.sqrt(2.0)))
    # Transform sang phân phối biên mong muốn (chuẩn hóa về [-2, 2])
    latents = (U - 0.5) * 4.0  # scale về [-2, 2]
    return latents


# ============================================================================
# AR(1) AUTO-REGRESSIVE PROCESS
# ============================================================================
def ar1_series(n: int, phi: float, mu: float, sigma: float, n_steps: int, seed: int = SEED) -> np.ndarray:
    """
    Sinh chuỗi AR(1): X_t = phi·X_{t-1} + (1-phi)·mu + eps_t, eps_t ~ N(0, sigma²)
    Returns: (n, n_steps) array
    """
    rng = np.random.default_rng(seed)
    X = np.zeros((n, n_steps))
    X[:, 0] = mu + rng.normal(0, sigma, n)
    for t in range(1, n_steps):
        X[:, t] = phi * X[:, t-1] + (1 - phi) * mu + rng.normal(0, sigma, n)
    return X


# ============================================================================
# LOGISTIC DECAY (crisis trajectory)
# ============================================================================
def logistic_decay(n: int, n_steps: int, crisis_weeks: np.ndarray, d_max: float, k: float, seed: int = SEED) -> np.ndarray:
    """
    Suy giảm logistic: drop(t) = d_max / (1 + exp(-k·(t - t_c)))
    crisis_weeks: (n,) array, tuần xảy ra biến cố (nếu không có biến cố -> 999)
    Returns: (n, n_steps) array — hệ số suy giảm nhân vào điểm
    """
    rng = np.random.default_rng(seed)
    t = np.arange(n_steps).astype(np.float64)
    # drop_factor = 1.0 nếu không có biến cố, giảm dần nếu có biến cố
    drop = np.ones((n, n_steps))
    for i in range(n):
        if crisis_weeks[i] < n_steps:
            tc = crisis_weeks[i]
            drop[i, :] = 1.0 - d_max / (1.0 + np.exp(-k * (t - tc)))
    return drop


# ============================================================================
# STUDENT PERSONA (v4 — kết hợp Copula + AR(1) + Logistic Decay)
# ============================================================================
@dataclass
class StudentV4:
    """Học sinh với latent variables tương quan (Copula) + crisis trajectory."""
    student_id: int
    code: str
    name: str
    gender: str
    school_id: int
    grade_id: int
    homeroom_class_id: int
    risk_tier: str
    profile: str  # G1-G9 (phân phối điểm như v2)
    crisis_week: int
    crisis_type: str
    latents: np.ndarray  # [ability_math, ability_lang, eff, attend, lms_effort, conduct]
    # Trajectories (AR(1))
    attend_series: np.ndarray  # (n_weeks,) — chuyên cần (0-1, 1 = đi học đầy đủ)
    lms_series: np.ndarray    # (n_weeks,) — LMS effort (0-1)
    conduct_series: np.ndarray # (n_weeks,) — kỷ luật (0-1, 1 = tốt)
    grade_series: np.ndarray   # (n_weeks,) — điểm thi (0-10)
    has_life_event: bool = False  # có biến cố hoàn cảnh (~12% chung, KHÔNG theo risk tier)
    resilience: float = 0.0       # sức chống chịu (tính từ latents ability[0]+eff[2], nội bộ script)
    specialization: str = "BALANCED"  # STEM, HUMANITIES, SINGLE_CRASH, BALANCED
    crash_subject: str = ""           # Tên hoặc mã môn bị sập điểm (Bottleneck)

    def get_swb_score_at_week(self, week: int) -> float:
        """SWB score (1.0-5.0) từ latent attend + crisis."""
        base = 3.0 + self.latents[3] * 0.8  # attend ảnh hưởng SWB
        if self.crisis_week <= week:
            base -= 1.5
        return round(float(np.clip(base, 1.0, 5.0)), 2)

    def get_exam_grade(self, week: int, base_ability: float, subject_category: str = 'MATH_SCIENCE', subject_code: str = '') -> float:
        """Điểm thi tại tuần week (0-10) phản ánh:
        1. Năng lực chuyên biệt môn học (STEM vs HUMANITIES)
        2. Tình trạng học lệch (Skewed Learning) hoặc Khủng hoảng đơn môn (Bottleneck crash)
        3. Biến thiên AR(1) persistence."""
        if self.specialization == "SINGLE_CRASH" and self.crash_subject and (self.crash_subject in subject_code or subject_code.startswith(self.crash_subject)):
            # Học sinh bị sập điểm nghiêm trọng ở đúng môn nút thắt (Bottleneck ~ 1.5 - 3.0)
            ability = 2.2 + float(self.latents[0] * 0.3)
        elif self.specialization == "STEM":
            # Dân chuyên Tự Nhiên / STEM: giỏi Toán/Lý/Tin/Robotics, yếu Xã Hội
            if subject_category in ('MATH_SCIENCE', 'TECHNOLOGY'):
                ability = base_ability + 2.5 + float(self.latents[0] * 0.7)
            else:  # HUMANITIES
                ability = base_ability - 3.2 + float(self.latents[1] * 0.7)
        elif self.specialization == "HUMANITIES":
            # Dân chuyên Xã Hội / Ngôn Ngữ: giỏi Văn/Sử/GDCD/Anh, yếu STEM
            if subject_category == 'HUMANITIES':
                ability = base_ability + 2.5 + float(self.latents[1] * 0.7)
            else:  # MATH_SCIENCE / TECHNOLOGY
                ability = base_ability - 3.2 + float(self.latents[0] * 0.7)
        else:  # BALANCED
            if subject_category == 'HUMANITIES':
                ability = base_ability + float(self.latents[1] * 0.8)
            else:
                ability = base_ability + float(self.latents[0] * 0.8)

        ability = float(np.clip(ability, 1.2, 9.8))
        ar1_offset = float(self.grade_series[week-1] - 7.0)
        grade = ability + ar1_offset
        return round(float(np.clip(grade, 0.5, 10.0)), 1)


# ============================================================================
# SCALE CONVERSION (0-10 -> native scale)
# ============================================================================
LETTER_TO_10 = {
    "A+": 9.5, "A": 9.0, "B+": 8.5, "B": 8.0,
    "C+": 7.5, "C": 7.0, "D+": 6.5, "D": 6.0,
    "E": 4.5, "F": 2.5,
}

def convert_to_scale(score_10: float, scale_name: str) -> tuple:
    """Chuyển điểm 0-10 sang thang điểm gốc. Returns (native_value, score_10, letter, pct)."""
    score_10 = float(np.clip(score_10, 0.0, 10.0))
    if scale_name == 'LETTER_AF':
        for let, th in sorted(LETTER_TO_10.items(), key=lambda x: -x[1]):
            if score_10 >= th:
                return let, round(float(LETTER_TO_10[let]), 1), let, None
        return "F", round(float(LETTER_TO_10["F"]), 1), "F", None
    if scale_name == 'SCALE_6':
        native = round(float(np.clip(1 + score_10 / 10.0 * 6.0, 1, 7)), 0)
        return native, round(float(np.clip((native - 1) / 6.0 * 10.0, 0, 10)), 1), None, native
    if scale_name == 'SCALE_100':
        native = round(float(np.clip(score_10 * 10.0, 0, 100)), 0)
        return native, round(float(np.clip(native / 10.0, 0, 10)), 1), None, native
    if scale_name == 'SCALE_4':
        native = round(float(np.clip(score_10 / 10.0 * 4.0, 0, 4)), 1)
        return native, round(float(np.clip(native / 4.0 * 10.0, 0, 10)), 1), None, native
    # SCALE_10 (mặc định)
    return round(float(score_10), 1), round(float(score_10), 1), None, None


# ============================================================================
# SCHEMA GUARD — Đảm bảo 37 bảng tồn tại
# ============================================================================
SCHEMA_TABLES_37 = [
    # public (10)
    "public.users", "public.refresh_tokens", "public.teacher_assignments",
    "public.exam_papers", "public.curriculum_units", "public.exam_competencies",
    "public.audit_logs", "public.report_schedules", "public.classroom_recordings",
    "public.ai_observability_snapshots",
    # s360 (27)
    "s360.dim_school_year", "s360.dim_homeroom_class", "s360.dim_homeroom_class_student",
    "s360.dim_subject", "s360.dim_exam", "s360.dim_exam_moet", "s360.dim_so_assignment",
    "s360.dim_grade_scale_detail", "s360.dim_behavior", "s360.dim_course",
    "s360.fact_gradebooks", "s360.fact_gradebooks_moet", "s360.fact_so_assignment_grade",
    "s360.fact_subject_academic_records", "s360.fact_overall_academic_records",
    "s360.fact_so_evaluate_process_subjects", "s360.fact_behavior_logs",
    "s360.fact_absent_logs", "s360.fact_so_daily_attendance",
    "s360.fact_so_homeroom_class_attendances", "s360.fact_so_homeroom_class_late_attendances",
    "s360.fact_so_class_attendance_statistics", "s360.fact_course_attendences",
    "s360.fact_swb_survey", "s360.fact_swb_support",
    "s360.fact_student_life_events", "s360.fact_student_medical_history",
    "s360.train_student_subject_risk_dataset", "s360.fact_student_subject_risk_predictions",
]


def validate_schema(session) -> List[str]:
    """Kiểm tra toàn vẹn schema 37 bảng. Returns list các bảng thiếu."""
    missing = []
    for tbl in SCHEMA_TABLES_37:
        try:
            session.execute(text(f"SELECT 1 FROM {tbl} LIMIT 1"))
        except Exception:
            missing.append(tbl)
    return missing


# ============================================================================
# VALIDATION CHECK
# ============================================================================
def validate_correlation_matrix(corr: np.ndarray) -> bool:
    """Kiểm tra ma trận tương quan hợp lệ (symmetric, positive-definite)."""
    if corr.shape[0] != corr.shape[1]:
        logger.error("Correlation matrix must be square")
        return False
    if not np.allclose(corr, corr.T):
        logger.error("Correlation matrix must be symmetric")
        return False
    try:
        np.linalg.cholesky(corr)
    except np.linalg.LinAlgError:
        logger.error("Correlation matrix must be positive-definite")
        return False
    return True


def validate_generated_data(students: list, n_expected: int) -> bool:
    """Kiểm tra dữ liệu sinh ra hợp lệ."""
    if len(students) != n_expected:
        logger.error(f"Expected {n_expected} students, got {len(students)}")
        return False
    # Kiểm tra correlation thực tế giữa attend & grade
    if students:
        attends = np.array([s.latents[3] for s in students])
        grades = np.array([s.latents[0] for s in students])
        corr_actual = np.corrcoef(attends, grades)[0, 1]
        logger.info(f"Actual attend-grade correlation: {corr_actual:.3f}")
    return True


# ============================================================================
# CORE DATABASE SEEDER (37 TABLES)
# ============================================================================
def execute_batch(session, sql_string, params_list):
    if not params_list:
        return
    for i in range(0, len(params_list), BATCH_SIZE):
        chunk = params_list[i:i + BATCH_SIZE]
        session.execute(text(sql_string), chunk)


def seed_teacher_accounts(session):
    """Seed tài khoản thầy cô giáo (GIỮ NGUYÊN như v2) + phân công giảng dạy."""
    logger.info("Seeding teacher accounts (giữ nguyên như v2)...")
    users_sql = """
    INSERT INTO public.users (so_school_id, email, hashed_password, full_name, role, is_active)
    VALUES 
    (1, 'principal_cp@vinschool.edu.vn', :hpwd, 'Nguyễn Văn Minh (BGH)', 'PRINCIPAL', true),
    (2, 'principal_gr@vinschool.edu.vn', :hpwd, 'Trần Thị Thu Hương (BGH)', 'PRINCIPAL', true),
    (1, 'grade_head_6_cp@vinschool.edu.vn', :hpwd, 'Lê Hoàng Nam (Trưởng Khối 6)', 'GRADE_HEAD_PRIMARY', true),
    (1, 'teacher_gvcn_6a1@vinschool.edu.vn', :hpwd, 'Phạm Thị Lan (GVCN 6A1)', 'HOMEROOM_TEACHER_SECONDARY', true),
    (1, 'teacher_gvbm_math_6a1@vinschool.edu.vn', :hpwd, 'Vũ Đức Thành (GVBM Toán)', 'SUBJECT_TEACHER', true),
    (1, 'teacher_kiem_nhiem@vinschool.edu.vn', :hpwd, 'Hoàng Kim Ngân (GVCN 6A2 + GVBM Toán 6A1)', 'HOMEROOM_TEACHER_SECONDARY', true),
    (1, 'teacher_gvbm_math_multi@vinschool.edu.vn', :hpwd, 'Đỗ Minh Quân (GVBM Toán nhiều lớp)', 'SUBJECT_TEACHER', true)
    ON CONFLICT (email) DO NOTHING;
    """
    session.execute(text(users_sql), {"hpwd": DEFAULT_HASHED_PASSWORD})
    session.commit()
    logger.info("Teacher accounts seeded (giống v2).")


def seed_teacher_assignments(session):
    """Gán phân công giảng dạy mẫu (GIỮ NGUYÊN như v2)."""
    logger.info("Seeding teacher assignments (giống v2)...")
    users_map = {}
    user_rows = session.execute(text("SELECT id, email FROM public.users")).fetchall()
    for r in user_rows:
        users_map[r[1]] = r[0]

    # Lấy class_id THẬT của 6A1, 6A2, 7A1 (so_school_id=1)
    class_rows = session.execute(text("""
        SELECT id, fullname, so_school_id
        FROM s360.dim_homeroom_class
        WHERE fullname IN ('6A1', '6A2', '7A1')
    """)).fetchall()
    class_map = {(r[1], r[2]): r[0] for r in class_rows}
    c_6a1 = class_map.get(("6A1", 1))
    c_6a2 = class_map.get(("6A2", 1))
    c_7a1 = class_map.get(("7A1", 1))

    if c_6a1 is None or c_6a2 is None:
        logger.warning("dim_homeroom_class chưa có 6A1/6A2 (so_school_id=1). Bỏ qua teacher_assignments.")
        return

    assignments = [
        {"user_id": users_map.get("grade_head_6_cp@vinschool.edu.vn"),
         "role_context": "GRADE_HEAD", "academic_year_id": 2025,
         "grade_id": 6, "class_id": None, "subject_id": None},
        {"user_id": users_map.get("teacher_gvcn_6a1@vinschool.edu.vn"),
         "role_context": "HOMEROOM_PRIMARY", "academic_year_id": 2025,
         "grade_id": None, "class_id": c_6a1, "subject_id": None},
        {"user_id": users_map.get("teacher_gvbm_math_6a1@vinschool.edu.vn"),
         "role_context": "SUBJECT_TEACHER", "academic_year_id": 2025,
         "grade_id": None, "class_id": c_6a1, "subject_id": 106},
        {"user_id": users_map.get("teacher_kiem_nhiem@vinschool.edu.vn"),
         "role_context": "HOMEROOM_PRIMARY", "academic_year_id": 2025,
         "grade_id": None, "class_id": c_6a2, "subject_id": None},
        {"user_id": users_map.get("teacher_gvbm_math_multi@vinschool.edu.vn"),
         "role_context": "SUBJECT_TEACHER", "academic_year_id": 2025,
         "grade_id": None, "class_id": c_6a1, "subject_id": 106},
        {"user_id": users_map.get("teacher_gvbm_math_multi@vinschool.edu.vn"),
         "role_context": "SUBJECT_TEACHER", "academic_year_id": 2025,
         "grade_id": None, "class_id": c_6a2, "subject_id": 106},
        {"user_id": users_map.get("teacher_gvbm_math_multi@vinschool.edu.vn"),
         "role_context": "SUBJECT_TEACHER", "academic_year_id": 2025,
         "grade_id": None, "class_id": c_7a1, "subject_id": 107},
    ]
    for item in assignments:
        if not item["user_id"]:
            continue
        session.execute(text("""
            INSERT INTO public.teacher_assignments (user_id, academic_year_id, role_context, class_id, grade_id, subject_id, is_active)
            VALUES (:user_id, :academic_year_id, CAST(:role_context AS public.role_context_enum), :class_id, :grade_id, :subject_id, true)
            ON CONFLICT DO NOTHING;
        """), item)
    session.commit()
    logger.info("Teacher assignments seeded (giống v2).")


def seed_schema_guard(session):
    """Đảm bảo các bảng SWB tồn tại (idempotent)."""
    session.execute(text("""
        CREATE TABLE IF NOT EXISTS s360.fact_swb_survey (
            id                          BIGINT PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
            survey_date                 DATE NOT NULL,
            week_start                  DATE,
            month_start              DATE,
            school_year_id              INTEGER REFERENCES s360.dim_school_year(id),
            school_year                 VARCHAR(50),
            student_code                VARCHAR(50) NOT NULL,
            school_code                VARCHAR(50),
            school_name                VARCHAR(255),
            homeroom_class_id          INTEGER REFERENCES s360.dim_homeroom_class(id),
            class_code                VARCHAR(50),
            class_name                VARCHAR(100),
            grade_id                    INTEGER,
            grade_name                VARCHAR(50),
            question_set_id             BIGINT,
            question_group_id           BIGINT,
            question_group_name        VARCHAR(255),
            question_group_name_en     VARCHAR(255),
            question_id               BIGINT,
            converted_score         DOUBLE PRECISION,
            created_at              TIMESTAMPTZ DEFAULT NOW(),
            updated_at              TIMESTAMPTZ DEFAULT NOW()
        );
        CREATE TABLE IF NOT EXISTS s360.fact_swb_support (
            id                          BIGINT PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
            student_code                VARCHAR(50) NOT NULL,
            loai_can_thiep              VARCHAR(100),
            ten_ho_tro                  VARCHAR(255),
            trang_thai_ho_tro           VARCHAR(100),
            ngay_bat_dau                DATE,
            school_year_id              INTEGER REFERENCES s360.dim_school_year(id),
            school_year                 VARCHAR(50),
            school_code                VARCHAR(50),
            school_name                VARCHAR(255),
            grade_id                    INTEGER,
            grade_name                VARCHAR(50),
            homeroom_class_id          INTEGER REFERENCES s360.dim_homeroom_class(id),
            class_code                VARCHAR(50),
            class_name                VARCHAR(100),
            iep_muc_tieu                TEXT,
            iep_tiep_can                TEXT,
            iep_can_thiep_cu_the        TEXT,
            iep_ke_hoach_trien_khai    TEXT,
            iep_thu_thap_thong_tin      TEXT,
            iep_nhat_ky_tro_giup        TEXT,
            ngay_cap_nhat_iep           DATE,
            iep_actions_can_lam         TEXT,
            ten_chuong_trinh_nhom       VARCHAR(255),
            muc_tieu_chuong_trinh_nhom TEXT,
            ngay_ho_tro_gan_nhat        DATE,
            ma_van_de_dang_can_thiep    VARCHAR(100),
            reference_id                BIGINT,
            created_at                  TIMESTAMPTZ DEFAULT NOW(),
            updated_at                  TIMESTAMPTZ DEFAULT NOW()
        );
    """))


def seed_auxiliary_tables(session, students):
    """Seed các bảng fact/dim phụ còn trống (để v4 ngang v2 về độ phủ schema).
    Gồm: dim_exam_moet, dim_grade_scale_detail, dim_course, fact_course_enrolls,
    fact_so_evaluate_process_subjects, fact_so_homeroom_class_attendances,
    fact_so_homeroom_class_late_attendances, fact_so_class_attendance_statistics,
    fact_course_attendences."""
    logger.info("Seeding auxiliary tables (dim_exam_moet, grade_scale, course, evaluate, homeroom att)...")

    # --- dim_exam_moet (3 mốc/môn, khớp dim_exam) ---
    exam_moet_params = []
    for s_id, code, name, name_en, atype, scale, cat in SUBJECTS_23:
        if atype == 'REMARK':
            continue
        for m_idx, sem in [(1, 1), (2, 1), (3, 2)]:
            exam_moet_params.append({
                "id": s_id * 10 + m_idx,
                "code": f"EXAM_{code}_M{m_idx}",
                "fullname": f"Thi Mốc {m_idx} Môn {name}",
                "coeff": 2.0,
                "sem": sem
            })
    execute_batch(session, """
        INSERT INTO s360.dim_exam_moet (gradebook_type_item_id, gradebook_type_items_code, gradebook_type_items_fullname, coefficient, moet_semester_index)
        VALUES (:id, :code, :fullname, :coeff, :sem)
        ON CONFLICT (gradebook_type_item_id) DO NOTHING;
    """, exam_moet_params)

    # --- dim_grade_scale_detail (8 dòng thang điểm như v2) ---
    scale_rows = [
        (1, 'SCALE_10', 9.0, 10.0, 90.0, 100.0, 95.0, 'A+', 'Xuất sắc', 4.0, 6, 'DAT'),
        (2, 'SCALE_10', 8.0, 8.9, 80.0, 89.0, 85.0, 'A', 'Giỏi', 3.5, 5, 'DAT'),
        (3, 'SCALE_10', 7.0, 7.9, 70.0, 79.0, 75.0, 'B+', 'Khá giỏi', 3.0, 4, 'DAT'),
        (4, 'SCALE_10', 6.5, 6.9, 65.0, 69.0, 67.0, 'B', 'Khá', 2.5, 3, 'DAT'),
        (5, 'SCALE_10', 5.5, 6.4, 55.0, 64.0, 60.0, 'C+', 'Trung bình khá', 2.0, 2, 'DAT'),
        (6, 'SCALE_10', 5.0, 5.4, 50.0, 54.0, 52.0, 'C', 'Trung bình', 1.5, 2, 'DAT'),
        (7, 'SCALE_10', 3.5, 4.9, 35.0, 49.0, 42.0, 'D', 'Yếu', 1.0, 1, 'CHUA_DAT'),
        (8, 'SCALE_10', 0.0, 3.4, 0.0, 34.0, 17.0, 'F', 'Kém', 0.0, 0, 'CHUA_DAT'),
    ]
    for sr in scale_rows:
        session.execute(text("""
            INSERT INTO s360.dim_grade_scale_detail 
            (id, scale_name, min_score_range, max_score_range, min_percent, max_percent, representative_percent, grade_letter, grade_label, gpa_scale_4, scale_6_value, pass_fail_status)
            VALUES (:id, :sname, :min_s, :max_s, :min_p, :max_p, :rep_p, :gletter, :glabel, :gpa4, :s6, CAST(:pf AS public.pass_fail_enum))
            ON CONFLICT (id) DO NOTHING;
        """), {
            "id": sr[0], "sname": sr[1], "min_s": sr[2], "max_s": sr[3],
            "min_p": sr[4], "max_p": sr[5], "rep_p": sr[6], "gletter": sr[7],
            "glabel": sr[8], "gpa4": sr[9], "s6": sr[10], "pf": sr[11]
        })

    # --- dim_course (4 khóa tự chọn như v2) ---
    # LƯU Ý: v4 chỉ có 11 lớp (id 1-11), khác v2 (27 lớp). Lớp 7A1 school 1 = id 3.
    courses_data = [
        (101, 1, 2025, 7, 2, 3, "CRS_MATH_ADV_7A1", "Lớp Học Phần Toán Nâng Cao 7A1", "ELECTIVE", 35),
        (102, 1, 2025, 7, 3, 3, "CRS_ENG_CAMB_7A1", "Lớp Tiếng Anh Cambridge 7A1", "ELECTIVE", 35),
        (103, 1, 2025, 7, 4, 3, "CRS_STEM_ROBOTICS_7A1", "Lớp STEM & Robotics Khối 7", "ELECTIVE", 35),
        (104, 1, 2025, 7, 5, 3, "CRS_LIT_ADV_7A2", "Lớp Chuyên Ngữ Văn Khối 7", "ELECTIVE", 35),
    ]
    for c in courses_data:
        session.execute(text("""
            INSERT INTO s360.dim_course (id, so_school_id, school_year_id, grade_id, subject_id, homeroom_class_id, code, name, type, max_student)
            VALUES (:id, :sid, :syid, :gid, :subid, :cid, :code, :name, :type, :max_s)
            ON CONFLICT (id) DO NOTHING;
        """), {"id": c[0], "sid": c[1], "syid": c[2], "gid": c[3], "subid": c[4], "cid": c[5], "code": c[6], "name": c[7], "type": c[8], "max_s": c[9]})

    # --- fact_course_enrolls (học sinh đăng ký môn tự chọn) ---
    course_enroll_params = []
    enroll_id = 1
    for p in students:
        # ~30% học sinh đăng ký 1 khóa tự chọn
        if random.random() < 0.3:
            course_enroll_params.append({
                "id": enroll_id, "sid": p.school_id, "scode": p.code,
                "subid": random.choice([9, 10, 13, 14]), "gid": p.grade_id
            })
            enroll_id += 1
    execute_batch(session, """
        INSERT INTO s360.fact_course_enrolls (id, so_school_id, student_code, subject_id, grade_id, is_moved_out, is_student)
        VALUES (:id, :sid, :scode, :subid, :gid, 0, 1)
        ON CONFLICT (id) DO NOTHING;
    """, course_enroll_params)

    # --- fact_so_evaluate_process_subjects (đánh giá tiến trình môn học) ---
    eval_process_params = []
    eval_id = 1
    for p in students:
        for s_id, code, name, name_en, atype, scale, cat in SUBJECTS_23:
            if atype == 'REMARK':
                continue
            if code.startswith('TOAN_'):
                try:
                    if int(code.split('_')[1]) != p.grade_id:
                        continue
                except (IndexError, ValueError):
                    pass
            for sem_idx in [1, 2]:
                eval_process_params.append({
                    "id": eval_id, "eid": eval_id, "subid": s_id, "scode": p.code,
                    "syid": 2025, "sem": sem_idx,
                    "fgl": "DAT", "slevel": "ĐẠT", "comment": "Hoàn thành tốt", "tname": "Giáo viên Bộ Môn"
                })
                eval_id += 1
    execute_batch(session, """
        INSERT INTO s360.fact_so_evaluate_process_subjects
        (id, evaluate_progress_id, subject_id, student_code, school_year_id, semester_index, final_grade_level, student_level, comment, teacher_fullname)
        VALUES (:id, :eid, :subid, :scode, :syid, :sem, :fgl, :slevel, :comment, :tname)
        ON CONFLICT (id) DO NOTHING;
    """, eval_process_params)

    # --- fact_so_homeroom_class_attendances + late_attendances + class_attendance_statistics ---
    homeroom_att_params = []
    late_att_params = []
    class_stat_params = []
    for p in students:
        for week in range(1, 13):
            att_date = SCHOOL_YEAR_START + timedelta(weeks=week - 1)
            # Điểm danh lớp chủ nhiệm: status 1=đi, 2=vắng
            status = 2 if random.random() < float(np.clip(1.0 - p.attend_series[week-1], 0.0, 1.0)) else 1
            homeroom_att_params.append({
                "sid": p.school_id, "syid": 2025, "cid": p.homeroom_class_id,
                "adate": att_date, "scode": p.code, "status": status
            })
            # Đi muộn: ~5% số tuần
            if random.random() < 0.05:
                late_att_params.append({
                    "sid": p.school_id, "syid": 2025, "gid": p.grade_id, "cid": p.homeroom_class_id,
                    "adate": att_date, "scode": p.code, "sname": p.name,
                    "atime": datetime.combine(att_date, datetime.min.time()) + timedelta(hours=7, minutes=35),
                    "tlate": random.randint(5, 40)
                })
            # Thống kê chuyên cần
            class_stat_params.append({
                "scode": p.code, "date": att_date, "tl": 5,
                "la": 5 if status == 1 else 0, "lna": 0 if status == 1 else 5,
                "cid": p.homeroom_class_id, "gid": p.grade_id, "sid": p.school_id, "syid": 2025
            })
    execute_batch(session, """
        INSERT INTO s360.fact_so_homeroom_class_attendances
        (so_school_id, school_year_id, homeroom_class_id, attendance_date, student_code, status)
        VALUES (:sid, :syid, :cid, :adate, :scode, :status);
    """, homeroom_att_params)
    execute_batch(session, """
        INSERT INTO s360.fact_so_homeroom_class_late_attendances
        (so_school_id, school_year_id, grade_id, homeroom_class_id, attendance_date, student_code, user_fullname, attendance_time, is_late, status_name, time_late)
        VALUES (:sid, :syid, :gid, :cid, :adate, :scode, :sname, :atime, 1, 'DI_MUON', :tlate);
    """, late_att_params)
    execute_batch(session, """
        INSERT INTO s360.fact_so_class_attendance_statistics
        (student_code, date, total_lesson, lesson_attend, lesson_not_attend, homeroom_class_id, grade_id, so_school_id, school_year_id)
        VALUES (:scode, :date, :tl, :la, :lna, :cid, :gid, :sid, :syid)
        ON CONFLICT (id) DO NOTHING;
    """, class_stat_params)

    # --- dim_course + fact_course_attendences (Phương án 2: Điểm danh theo tiết học từng môn) ---
    course_params = []
    course_map = {}
    course_id_counter = 1
    for s_id in [1, 2]:
        for g_id in range(6, 11):
            for sub_id, code, name, name_en, atype, scale, cat in SUBJECTS_23:
                course_params.append({
                    "id": course_id_counter,
                    "sid": s_id,
                    "syid": 2025,
                    "gid": g_id,
                    "subid": sub_id,
                    "code": f"COURSE_{code}_G{g_id}_S{s_id}",
                    "name": f"Lớp {name} Khối {g_id}"
                })
                course_map[(s_id, g_id, sub_id)] = course_id_counter
                course_id_counter += 1

    execute_batch(session, """
        INSERT INTO s360.dim_course (id, so_school_id, school_year_id, grade_id, subject_id, code, name, status)
        VALUES (:id, :sid, :syid, :gid, :subid, :code, :name, 'ACTIVE')
        ON CONFLICT (id) DO NOTHING;
    """, course_params)

    # Sinh điểm danh tiết học phần (fact_course_attendences) cho từng học sinh & từng môn
    course_att_params = []
    for p in students:
        for week in range(1, 13):
            att_date = SCHOOL_YEAR_START + timedelta(weeks=week - 1)
            is_absent_day = random.random() < float(np.clip(1.0 - p.attend_series[week-1], 0.0, 1.0))
            is_unexcused = (p.risk_tier in ['HIGH', 'CRITICAL'] and week >= p.crisis_week)

            for sub_id, code, name, name_en, atype, scale, cat in SUBJECTS_23:
                if code.startswith('TOAN_'):
                    try:
                        if int(code.split('_')[1]) != p.grade_id:
                            continue
                    except (IndexError, ValueError):
                        pass
                c_id = course_map.get((p.school_id, p.grade_id, sub_id))
                if not c_id:
                    continue

                # 2 tiết / môn / tuần
                for p_idx, p_code, p_name in [(1, "PER_01", "Tiết 1"), (2, "PER_03", "Tiết 3")]:
                    # Nếu học sinh vắng trong ngày này
                    if is_absent_day and random.random() < 0.5:
                        status = "ABSENT"
                        status_name = "Vắng không phép" if is_unexcused else "Nghỉ có phép"
                        comment = "Vắng mặt không lý do" if is_unexcused else "Xin nghỉ có phép"
                    elif random.random() < 0.02:
                        status = "LATE"
                        status_name = "Đi muộn"
                        comment = "Vào lớp muộn 15 phút"
                    else:
                        status = "PRESENT"
                        status_name = "Có mặt"
                        comment = None

                    course_att_params.append({
                        "sid": p.school_id,
                        "syid": 2025,
                        "cid": c_id,
                        "pcode": p_code,
                        "pname": p_name,
                        "adate": att_date,
                        "scode": p.code,
                        "status": status,
                        "sname": status_name,
                        "comment": comment
                    })

    execute_batch(session, """
        INSERT INTO s360.fact_course_attendences
        (so_school_id, school_year_id, course_id, timetable_period_code, timetable_period_name, _date, student_code, status, status_name, comment)
        VALUES (:sid, :syid, :cid, :pcode, :pname, :adate, :scode, :status, :sname, :comment);
    """, course_att_params)

    logger.info(f"Auxiliary tables seeded: exam_moet={len(exam_moet_params)}, course_enrolls={len(course_enroll_params)}, "
                f"evaluate={len(eval_process_params)}, homeroom_att={len(homeroom_att_params)}, late={len(late_att_params)}, class_stat={len(class_stat_params)}, "
                f"dim_course={len(course_params)}, course_att={len(course_att_params)}")


def seed_benchmark_students(session, students):
    """Thêm 5 benchmark edge case students (giống v2) để test EWS scenarios.
    Mỗi student có điểm cho ALL core subjects, cả 2 học kỳ."""
    logger.info("Seeding 5 benchmark edge case students (SUT, WAR, TARDY, LMSGAP, GRADIENT)...")
    CORE_SUBJECTS_GRADE7 = [107, 2, 3, 7, 8]  # TOAN_7, VAN, ANH, KHTN, LS_DL

    benchmark_students = [
        {"scode": "HS000EDGE01", "sname": "Nguyễn Văn A_SUT", "scenario": "Điểm cao → sụt giảm đột ngột tuần 12",
         "school_id": 1, "grade_id": 7, "homeroom_class_id": 3,
         "exam_scores": {107: (8.5, 3.0, 2.5, 1.5), 2: (7.5, 2.5, 2.0, 1.0), 3: (8.0, 3.5, 3.0, 2.0), 7: (7.0, 2.0, 1.5, 1.0), 8: (8.0, 3.0, 2.5, 1.5)}},
        {"scode": "HS000EDGE02", "sname": "Trần Thị B_WAR", "scenario": "Vắng không phép liên tục (WAR=45%) nhưng điểm vẫn cao",
         "school_id": 1, "grade_id": 7, "homeroom_class_id": 3,
         "exam_scores": {107: (8.5, 8.0, 8.2, 7.8), 2: (8.8, 8.3, 8.5, 8.0), 3: (9.0, 8.5, 8.8, 8.2), 7: (8.2, 7.8, 8.0, 7.5), 8: (8.5, 8.0, 8.3, 7.8)}},
        {"scode": "HS000EDGE03", "sname": "Lê Văn C_TARDY", "scenario": "Đi muộn 10-15 phút mỗi ngày",
         "school_id": 1, "grade_id": 7, "homeroom_class_id": 3,
         "exam_scores": {107: (6.5, 6.0, 6.2, 5.8), 2: (6.8, 6.3, 6.5, 6.0), 3: (6.2, 5.8, 6.0, 5.5), 7: (6.0, 5.5, 5.8, 5.2), 8: (7.0, 6.5, 6.8, 6.2)}},
        {"scode": "HS000EDGE04", "sname": "Phạm Văn D_LMSGAP", "scenario": "LMS full điểm (9-10) nhưng thi thấp (2-4)",
         "school_id": 1, "grade_id": 7, "homeroom_class_id": 3,
         "exam_scores": {107: (3.0, 2.5, 3.5, 3.0), 2: (4.0, 3.5, 4.2, 3.8), 3: (2.5, 2.0, 3.0, 2.5), 7: (3.5, 3.0, 4.0, 3.5), 8: (3.0, 2.5, 3.5, 3.0)}},
        {"scode": "HS000EDGE05", "sname": "Hoàng Văn E_GRADIENT", "scenario": "Điểm TB (6.5) nhưng đang giảm mạnh qua các tuần",
         "school_id": 1, "grade_id": 7, "homeroom_class_id": 3,
         "exam_scores": {107: (6.5, 3.5, 3.0, 2.0), 2: (6.0, 3.0, 2.5, 1.5), 3: (7.0, 4.0, 3.5, 2.5), 7: (5.5, 3.0, 2.5, 1.5), 8: (6.5, 3.5, 3.0, 2.0)}},
    ]

    gid_counter = 1
    gradebook_moet_batch = []
    overall_academic_batch = []
    for i, bm in enumerate(benchmark_students, 1):
        scode, sid, gid_v, cid, sname = bm["scode"], bm["school_id"], bm["grade_id"], bm["homeroom_class_id"], bm["sname"]
        # Insert vào dim_homeroom_class_student
        session.execute(text("""
            INSERT INTO s360.dim_homeroom_class_student
            (id, so_student_id, student_code, student_name, homeroom_class_id, class_code, class_name,
             so_school_id, school_year_id, school_name, grade_id, grade_name, moet_code, join_date)
            VALUES (:idx, :idx, :scode, :sname, :cid, :ccode, :cname, :sid, :syid, :sname_sch, :gid, :gname, :mcode, :jdate)
            ON CONFLICT (id) DO NOTHING;
        """), {
            "idx": 99990 + i, "scode": scode, "sname": sname, "cid": cid,
            "ccode": f"CLASS_{sid}_{gid_v}A1", "cname": f"{gid_v}A1",
            "sid": sid, "syid": 2025, "sname_sch": "Vinschool Central Park",
            "gid": gid_v, "gname": f"Khối {gid_v}", "mcode": f"MOET_{scode}",
            "jdate": date(2025, 9, 5)
        })
        # Gradebook MOET (môn quốc gia) — 3 mốc điểm (khớp dim_exam_moet id 1,2,3)
        exam_scores = bm["exam_scores"]
        for sub_id in CORE_SUBJECTS_GRADE7:
            sub_exams = exam_scores.get(sub_id, (5.0, 5.0, 5.0, 5.0))
            # dim_exam_moet có id = sub_id*10 + m_idx (vd 1071,1072,1073) — khớp benchmark
            for exam_idx, (exam_id, sem_idx, m_idx) in enumerate([(1, 1, 1), (2, 1, 2), (3, 2, 3)]):
                score_val = sub_exams[exam_idx]
                gradebook_moet_batch.append({
                    "id": gid_counter, "sid": sid, "syid": 2025, "sem": sem_idx,
                    "gid": gid_v, "cid": cid, "scode": scode, "subid": sub_id,
                    "type_item_id": sub_id * 10 + m_idx, "score": score_val, "comment": None,
                    "is_locked": 1, "created_at": EXAM_CREATED_AT.get(exam_id, datetime(2025, 9, 12, 8, 0, 0))
                })
                gid_counter += 1
        # Overall academic record
        all_exam_vals = []
        for sub_id in CORE_SUBJECTS_GRADE7:
            all_exam_vals.extend(exam_scores.get(sub_id, (5.0, 5.0, 5.0, 5.0)))
        gpa_bm = round(float(np.mean(all_exam_vals)), 1)
        overall_academic_batch.append({
            "id": gid_counter, "sid": sid, "syid": 2025, "gid": gid_v, "cid": cid,
            "st_id": gid_counter, "scode": scode, "fg": gpa_bm, "s1fg": gpa_bm,
            "cond": "KHA", "s1cond": "KHA",
            "lcap": "Khá" if gpa_bm >= 6.5 else ("Trung bình" if gpa_bm >= 5.0 else "Yếu"),
            "s1lcap": "Khá" if gpa_bm >= 6.5 else ("Trung bình" if gpa_bm >= 5.0 else "Yếu"),
        })
        gid_counter += 1

    execute_batch(session, """
        INSERT INTO s360.fact_gradebooks_moet
        (id, so_school_id, school_year_id, semester_index, grade_id, homeroom_class_id, student_code, subject_id, gradebook_type_item_id, final_grade, comment, is_locked, created_at)
        VALUES (:id, :sid, :syid, :sem, :gid, :cid, :scode, :subid, :type_item_id, :score, :comment, :is_locked, :created_at)
        ON CONFLICT (id) DO NOTHING;
    """, gradebook_moet_batch)
    execute_batch(session, """
        INSERT INTO s360.fact_overall_academic_records
        (id, so_school_id, school_year_id, grade_id, homeroom_class_id, student_id, student_code, final_grade, s1_final_grade, conduct, s1_conduct, learning_capacity, s1_learning_capacity)
        VALUES (:id, :sid, :syid, :gid, :cid, :st_id, :scode, :fg, :s1fg, CAST(:cond AS public.conduct_enum), CAST(:s1cond AS public.conduct_enum), :lcap, :s1lcap)
        ON CONFLICT (id) DO NOTHING;
    """, overall_academic_batch)
    logger.info(f"Seeded {len(benchmark_students)} benchmark students (gradebook_moet={len(gradebook_moet_batch)})")


def seed_public_aux_tables(session, students):
    """Seed các bảng public phụ (ai_*, exam_papers, curriculum_units, audit_logs,
    report_schedules, classroom_recordings) — để v4 ngang v2 về độ phủ."""
    logger.info("Seeding public auxiliary tables (ai_*, exam_papers, curriculum_units, audit_logs, report_schedules, classroom_recordings)...")

    # --- curriculum_units (1 unit/môn/khối) — id tự sinh (GENERATED ALWAYS) ---
    for s_id, code, name, name_en, atype, scale, cat in SUBJECTS_23:
        for g in range(6, 11):
            session.execute(text("""
                INSERT INTO public.curriculum_units (subject_id, grade_number, code, name, description)
                VALUES (:subid, :g, :code, :name, :desc)
                ON CONFLICT DO NOTHING;
            """), {"subid": s_id, "g": g, "code": f"UNIT_{code}_G{g}", "name": f"Chương trình {name} Khối {g}", "desc": f"Chuẩn đầu ra {name} khối {g}"})

    # --- exam_papers (1 đề thi/môn/khối) — id tự sinh (GENERATED ALWAYS) ---
    for s_id, code, name, name_en, atype, scale, cat in SUBJECTS_23:
        if atype == 'REMARK':
            continue
        for g in range(6, 11):
            session.execute(text("""
                INSERT INTO public.exam_papers (so_school_id, subject_id, semester_id, grade_id, score_category, title, difficulty, difficulty_coefficient, num_questions, total_points, uploaded_by)
                VALUES (1, :subid, 1, :g, 'MIDTERM', :title, 'MEDIUM', 1.0, 10, 10.0, 1)
                ON CONFLICT DO NOTHING;
            """), {"subid": s_id, "g": g, "title": f"Đề thi {name} Khối {g}"})

    # --- audit_logs (1 log mẫu) ---
    session.execute(text("""
        INSERT INTO public.audit_logs (table_name, record_id, action, changed_by, old_values, new_values)
        VALUES ('s360.fact_gradebooks', 1, 'INSERT', 1, '{}', '{"note": "seed v4"}')
        ON CONFLICT DO NOTHING;
    """))

    # --- report_schedules (1 lịch báo cáo) ---
    session.execute(text("""
        INSERT INTO public.report_schedules (created_by, name, report_type, filter_params, cron_expr, recipients, is_active)
        VALUES (1, 'Báo cáo EWS tuần', 'at_risk', '{"week": 5}', '0 8 * * 1', ARRAY['principal@vinschool.edu.vn'], true)
        ON CONFLICT DO NOTHING;
    """))

    # --- classroom_recordings (1 bản ghi) ---
    session.execute(text("""
        INSERT INTO public.classroom_recordings (so_school_id, teacher_id, subject_id, class_id, semester_id, lesson_name, period, date, week, audio_file_url, status, progress)
        VALUES (1, 1, 106, 1, 1, 'Bài giảng Toán 6', 1, '2025-09-10', 2, 'https://example.com/rec1.mp3', 'completed', 100)
        ON CONFLICT DO NOTHING;
    """))

    # --- ai_sessions + ai_messages (1 phiên chat mẫu) ---
    session.execute(text("""
        INSERT INTO public.ai_sessions (id, user_id, title, context_filter, is_active)
        VALUES ('00000000-0000-0000-0000-000000000001', 1, 'Hỏi về học sinh rủi ro', '{"school_id": 1}', true)
        ON CONFLICT (id) DO NOTHING;
    """))
    session.execute(text("""
        INSERT INTO public.ai_messages (session_id, role, content, generated_sql, guardrail_status, token_count)
        VALUES ('00000000-0000-0000-0000-000000000001', 'user', 'Liệt kê học sinh rủi ro cao', 'SELECT * FROM ...', 'PASSED', 10)
        ON CONFLICT DO NOTHING;
    """))

    logger.info("Public auxiliary tables seeded (curriculum_units, exam_papers, audit_logs, report_schedules, classroom_recordings, ai_sessions, ai_messages)")


def seed_life_events_and_medical(session, students):
    """Seed 2 bảng mới:
    - fact_student_life_events: biến cố cuộc sống (phạm vi LOW→CRITICAL) — ly hôn, qua đời, tai nạn...
    - fact_student_medical_history: tiền sử y tế / bệnh lý mãn tính (CHỈ học sinh có bệnh)."""
    logger.info("Seeding life events (LOW→CRITICAL) + medical history (chỉ học sinh có bệnh)...")

    # --- Biến cố cuộc sống: 8% chung cho MỌI học sinh (hoàn cảnh, KHÔNG theo risk tier).
    # `has_life_event` đã được quyết định khi tạo StudentV4 (đồng bộ crisis_week).
    # Severity dựa trên resilience: kiên cường → biến cố nhẹ (vẫn học tốt);
    # dễ tổn thương → biến cố nặng (gây crisis). ---
    LIFE_EVENTS = [
        ("FAMILY_DIVORCE", "Bố mẹ ly hôn", "Gia đình tan vỡ, học sinh sống với mẹ"),
        ("BEREAVEMENT", "Người thân qua đời", "Mất người thân, học sinh suy sụp tinh thần"),
        ("FAMILY_ACCIDENT", "Tai nạn gia đình", "Tai nạn giao thông / lao động trong gia đình"),
        ("FAMILY_CONFLICT", "Mâu thuẫn gia đình", "Xung đột kéo dài giữa các thành viên"),
        ("ACADEMIC_PRESSURE", "Áp lực học tập", "Áp lực thi cử, kỳ vọng quá cao từ gia đình"),
        ("MENTAL_CRISIS", "Khủng hoảng tâm lý", "Trầm cảm, lo âu, khủng hoảng tuổi dậy thì"),
    ]

    life_event_params = []
    for p in students:
        # Chỉ học sinh đã được gán has_life_event=True (12% chung) mới có biến cố
        if not p.has_life_event:
            continue
        event_type, event_name, desc = random.choice(LIFE_EVENTS)
        # Severity dựa trên resilience: kiên cường → nhẹ, dễ tổn thương → nặng
        if p.resilience < -0.5:
            severity = random.choice(["HIGH", "CRITICAL"])
        else:
            severity = random.choice(["LOW", "MODERATE"])
        # Ngày biến cố: trước crisis_week nếu có, ngẫu nhiên tuần 1-8 nếu không
        if p.crisis_week < 12:
            event_week = max(1, p.crisis_week - random.randint(0, 2))
        else:
            event_week = random.randint(1, 8)
        # Mô hình thời gian (Temporal Status): time_quantity + time_unit + status.
        # event_week 1-8 (đã xảy ra trong kỳ) → biến cố gần đây hầu hết ONGOING;
        # biến cố xa (>= 4 tuần trước) có thể đã RESOLVED nhưng vẫn lưu hồ sơ.
        time_qty = random.randint(1, 6)
        time_unit = random.choice(["WEEK", "MONTH"])
        status = "ONGOING" if event_week >= 4 else "RESOLVED"
        life_event_params.append({
            "student_code": p.code,
            "event_type": event_type,
            "event_name": event_name,
            "event_date": SCHOOL_YEAR_START + timedelta(weeks=event_week),
            "severity": severity,
            "description": desc,
            "time_quantity": time_qty,
            "time_unit": time_unit,
            "status": status,
            "school_year_id": 2025,
            "so_school_id": p.school_id
        })
    execute_batch(session, """
        INSERT INTO s360.fact_student_life_events
        (student_code, event_type, event_name, event_date, severity, description, time_quantity, time_unit, status, school_year_id, so_school_id)
        VALUES (:student_code, :event_type, :event_name, :event_date, :severity, :description, :time_quantity, :time_unit, :status, :school_year_id, :so_school_id);
    """, life_event_params)

    # --- Tiền sử y tế & Bệnh lý (gồm cả Mãn tính & Ngắn hạn như gãy tay, mổ ruột thừa, ~8%) ---
    MEDICAL_CONDITIONS = [
        # Mãn tính lâu dài (is_chronic = True)
        ("DIABETES", "Tiểu đường type 1", "Cần theo dõi đường huyết, chế độ ăn đặc biệt", True),
        ("CARDIOVASCULAR", "Bệnh tim bẩm sinh", "Hạn chế vận động mạnh, cần theo dõi tim", True),
        ("ASTHMA", "Hen suyễn mãn tính", "Dễ lên cơn hen khi gắng sức, cần thuốc dự phòng", True),
        ("ALLERGY", "Dị ứng thức ăn", "Dị ứng đậu phộng / hải sản, cần tránh", True),
        ("MENTAL_HEALTH", "Rối loạn lo âu / Trầm cảm", "Cần hỗ trợ tâm lý định kỳ", True),
        ("OPHTHALMIC", "Bệnh thị lực / Nhược thị mắt", "Tật khúc xạ mắt nặng, xếp ngồi bàn đầu để nhìn bảng", True),
        # Ngắn hạn / Cấp tính (is_chronic = False)
        ("INJURY", "Gãy tay / Chấn thương xương", "Bó bột tay, tạm thời miễn học Thể dục & bài kiểm tra viết", False),
        ("SURGERY", "Phẫu thuật mổ ruột thừa", "Mổ ruột thừa, đang giai đoạn nghỉ dưỡng phục hồi sức khỏe", False),
        ("ACUTE_INFECTION", "Bệnh nhiễm trùng / Sốt cấp tính", "Sốt xuất huyết / Viêm đường hô hấp cấp vừa điều trị", False),
    ]
    medical_params = []
    for p in students:
        if random.random() > 0.08:  # chỉ ~8% học sinh có bệnh/sự cố y tế
            continue
        cond_type, cond_name, notes, is_chronic = random.choice(MEDICAL_CONDITIONS)
        if is_chronic:
            time_qty = random.randint(1, 24)
            time_unit = "MONTH"
            status = "ONGOING"
            diag_date = SCHOOL_YEAR_START - timedelta(days=random.randint(30, 365))
        else:
            time_qty = random.randint(1, 6)
            time_unit = random.choice(["WEEK", "MONTH"])
            status = "ONGOING" if random.random() < 0.7 else "RESOLVED"
            diag_date = SCHOOL_YEAR_START - timedelta(days=random.randint(7, 60))

        medical_params.append({
            "student_code": p.code,
            "condition_type": cond_type,
            "condition_name": cond_name,
            "diagnosed_date": diag_date,
            "severity": random.choice(["LOW", "MODERATE", "HIGH"]),
            "is_chronic": is_chronic,
            "notes": notes,
            "time_quantity": time_qty,
            "time_unit": time_unit,
            "status": status,
            "school_year_id": 2025,
            "so_school_id": p.school_id
        })
    execute_batch(session, """
        INSERT INTO s360.fact_student_medical_history
        (student_code, condition_type, condition_name, diagnosed_date, severity, is_chronic, notes, time_quantity, time_unit, status, school_year_id, so_school_id)
        VALUES (:student_code, :condition_type, :condition_name, :diagnosed_date, :severity, :is_chronic, :notes, :time_quantity, :time_unit, :status, :school_year_id, :so_school_id);
    """, medical_params)

    logger.info(f"Seeded life_events={len(life_event_params)}, medical_history={len(medical_params)}")


def seed_golden_set_v4(session, n_students_per_school: int = 100, skip_metadata: bool = False):
    """Seed Golden Set V4 — 23 môn, 2 trường, mỗi trường n_students_per_school học sinh.
    skip_metadata=True → bỏ qua sync metadata (không gọi API embedding)."""
    logger.info("=" * 60)
    logger.info(f"GOLDEN SET V4 SEED START (2 schools x {n_students_per_school} students, 23 subjects)")
    logger.info("=" * 60)

    # --- Validation 1: Correlation matrix ---
    if not validate_correlation_matrix(CORR_MATRIX):
        raise ValueError("Invalid correlation matrix. Aborting.")

    # --- 0. Schema Guard ---
    seed_schema_guard(session)

    # --- 1. School Year ---
    session.execute(text("""
        INSERT INTO s360.dim_school_year (id, code, fullname, start_date, end_date, is_current, is_locked)
        VALUES (2025, '2025-2026', 'Năm học 2025-2026', :start, :end, 1, 1)
        ON CONFLICT (id) DO NOTHING;
    """), {"start": SCHOOL_YEAR_START, "end": SCHOOL_YEAR_END})

    # --- 2. Subjects (23 môn) ---
    for s_id, code, name, name_en, atype, scale, cat in SUBJECTS_23:
        session.execute(text("""
            INSERT INTO s360.dim_subject (id, code, name, name_en, assessment_type, subject_category, default_scale_name, is_active)
            VALUES (:id, :code, :name, :name_en, CAST(:atype AS public.assessment_type_enum), :cat, :scale, 1)
            ON CONFLICT (id) DO NOTHING;
        """), {"id": s_id, "code": code, "name": name, "name_en": name_en, "atype": atype, "cat": cat, "scale": scale})

    # --- 2b. Exams Catalog (dim_exam) — cần thiết cho FK fact_gradebooks.so_exam_id ---
    # 3 mốc điểm/môn: (mốc, semester_index) — khớp EXAM_MILESTONES trong gradebooks.
    #   mốc 1 = TX đầu HK1 (sem 1), mốc 2 = Giữa HK1 (sem 1), mốc 3 = Đầu HK2 (sem 2)
    exams_params = []
    for s_id, code, name, name_en, atype, scale, cat in SUBJECTS_23:
        if atype == 'REMARK':
            continue
        for m_idx, sem in [(1, 1), (2, 1), (3, 2)]:
            exams_params.append({
                "id": s_id * 10 + m_idx,
                "school_year_id": 2025,
                "subject_id": s_id,
                "grade_id": 8,
                "exam_code": f"EXAM_{code}_M{m_idx}",
                "exam_name": f"Thi Mốc {m_idx} Môn {name}",
                "coefficient": 2.0,
                "moet_semester_index": sem
            })
    execute_batch(session, """
        INSERT INTO s360.dim_exam (id, school_year_id, subject_id, grade_id, exam_code, exam_name, coefficient, moet_semester_index)
        VALUES (:id, :school_year_id, :subject_id, :grade_id, :exam_code, :exam_name, :coefficient, :moet_semester_index)
        ON CONFLICT (id) DO NOTHING;
    """, exams_params)

    # --- 3. Homeroom Classes (2 schools, grades 6-10) ---
    # School 1 grade 6 có 2 lớp (6A1, 6A2) để khớp teacher_assignments như v2.
    classes_params = []
    c_id = 1
    for s_id in [1, 2]:
        for g_id in range(6, 11):
            num_classes = 2 if (s_id == 1 and g_id == 6) else 1
            for c_num in range(1, num_classes + 1):
                classes_params.append({
                    "id": c_id,
                    "so_school_id": s_id,
                    "school_year_id": 2025,
                    "grade_id": g_id,
                    "code": f"CLASS_{s_id}_{g_id}A{c_num}",
                    "fullname": f"{g_id}A{c_num}",
                    "teacher_code": f"GV_{s_id}_{g_id}"
                })
                c_id += 1
    execute_batch(session, """
        INSERT INTO s360.dim_homeroom_class (id, so_school_id, school_year_id, grade_id, code, fullname, teacher_code, is_active)
        VALUES (:id, :so_school_id, :school_year_id, :grade_id, :code, :fullname, :teacher_code, 1)
        ON CONFLICT (id) DO NOTHING;
    """, classes_params)

    # --- 3b. Teacher accounts & assignments (GIỮ NGUYÊN như v2) ---
    seed_teacher_accounts(session)
    seed_teacher_assignments(session)

    # --- 4. Generate Students (Copula + AR(1) + Logistic Decay) ---
    n_total = n_students_per_school * 2
    latents = generate_correlated_latents(n_total, CORR_MATRIX, seed=SEED)

    # Risk stratification
    risk_tiers = []
    for i in range(n_total):
        risk_tiers.append(RISK_POOL[i % len(RISK_POOL)])

    # Crisis weeks: 8% chung có biến cố hoàn cảnh (KHÔNG theo risk tier);
    # chỉ biến cố + resilience thấp mới gây crisis (điểm sụt giảm).
    # Quậy phá/học tệ KHÔNG biến cố → không crisis (risk do hành vi).
    # Cha mẹ ly hôn nhưng kiên cường → không crisis (vẫn học tốt).
    crisis_weeks = np.full(n_total, 999, dtype=np.float64)
    for i in range(n_total):
        has_event = random.random() < 0.08
        resilience = latents[i][0] * 0.5 + latents[i][2] * 0.5
        if has_event and resilience < -0.5:
            crisis_weeks[i] = random.randint(4, 8)

    # AR(1) trajectories cho từng học sinh
    n_weeks = 12
    attend_series = ar1_series(n_total, AR1_PHI, 0.9, AR1_NOISE, n_weeks, seed=SEED)
    lms_series = ar1_series(n_total, AR1_PHI, 0.85, AR1_NOISE, n_weeks, seed=SEED)
    conduct_series = ar1_series(n_total, AR1_PHI, 0.9, AR1_NOISE, n_weeks, seed=SEED)
    grade_series = ar1_series(n_total, AR1_PHI, 7.0, 0.5, n_weeks, seed=SEED)

    # Logistic decay cho crisis
    grade_drop = logistic_decay(n_total, n_weeks, crisis_weeks, LOGISTIC_D_MAX, LOGISTIC_K, seed=SEED)
    grade_series = grade_series * grade_drop  # Áp logistic decay

    # Tạo StudentV4 objects
    students = []
    classes_by_school = {
        1: [c for c in classes_params if c["so_school_id"] == 1],
        2: [c for c in classes_params if c["so_school_id"] == 2],
    }
    class_map = {c["id"]: c for c in classes_params}

    for i in range(n_total):
        s_id = i + 1
        school_id = 1 if i < n_students_per_school else 2
        idx_in_school = i % n_students_per_school
        sch_classes = classes_by_school[school_id]
        target_class = sch_classes[idx_in_school % len(sch_classes)]

        class_id = target_class["id"]
        grade_id = target_class["grade_id"]
        # Gán profile G1-G9 (trải rộng điểm 0-10) + latent ability tạo đa dạng
        profile = random.choices(PROFILE_LIST, PROFILE_PROB)[0]
        # Đồng bộ với crisis_weeks logic: 8% chung có biến cố + resilience thấp → crisis
        st_has_event = random.random() < 0.08
        st_resilience = float(latents[i][0] * 0.5 + latents[i][2] * 0.5)

        # Gán specialization đa dạng (25% STEM, 25% HUMANITIES, 15% SINGLE_CRASH, 35% BALANCED)
        spec_rand = random.random()
        if spec_rand < 0.25:
            specialization = "STEM"
            crash_subject = ""
        elif spec_rand < 0.50:
            specialization = "HUMANITIES"
            crash_subject = ""
        elif spec_rand < 0.65:
            specialization = "SINGLE_CRASH"
            crash_subject = random.choice(["TOAN", "LY", "SINH", "VAN", "LS_DL", "GDCD", "TIN"])
        else:
            specialization = "BALANCED"
            crash_subject = ""

        st = StudentV4(
            student_id=s_id,
            code=f"HS{s_id:04d}",
            name=generate_vietnamese_name(),
            gender=random.choice(['Nam', 'Nữ']),
            school_id=school_id,
            grade_id=grade_id,
            homeroom_class_id=class_id,
            risk_tier=risk_tiers[i],
            profile=profile,
            crisis_week=int(crisis_weeks[i]),
            crisis_type=random.choice([
                "Gia đình có biến cố", "Trầm cảm", "Áp lực học tập", "Mâu thuẫn gia đình"
            ]) if crisis_weeks[i] < 12 else "",
            has_life_event=st_has_event,
            resilience=st_resilience,
            specialization=specialization,
            crash_subject=crash_subject,
            latents=latents[i],
            attend_series=attend_series[i],
            lms_series=lms_series[i],
            conduct_series=conduct_series[i],
            grade_series=grade_series[i],
        )
        students.append(st)

    # --- Validation 2: Generated data ---
    if not validate_generated_data(students, n_total):
        raise ValueError("Generated data validation failed.")

    # --- 5. Users (students) ---
    users_params = []
    students_params = []
    for p in students:
        users_params.append({
            "so_school_id": p.school_id,
            "email": f"{p.code.lower()}@vinschool.edu.vn",
            "hashed_password": DEFAULT_HASHED_PASSWORD,
            "full_name": p.name,
            "role": "STUDENT",
            "student_code": p.code,
            "so_student_id": p.student_id
        })
        cls_info = class_map[p.homeroom_class_id]
        students_params.append({
            "id": p.student_id,
            "so_student_id": p.student_id,
            "student_code": p.code,
            "student_name": p.name,
            "homeroom_class_id": p.homeroom_class_id,
            "class_code": cls_info["code"],
            "class_name": f"Lớp {cls_info['fullname']} - Trường {p.school_id}",
            "so_school_id": p.school_id,
            "school_year_id": 2025,
            "grade_id": p.grade_id,
            "grade_name": f"Khối {p.grade_id}",
            "join_date": date(2025, 9, 1)
        })

    execute_batch(session, """
        INSERT INTO public.users (so_school_id, email, hashed_password, full_name, role, student_code, so_student_id)
        VALUES (:so_school_id, :email, :hashed_password, :full_name, CAST(:role AS public.user_role_enum), :student_code, :so_student_id);
    """, users_params)

    execute_batch(session, """
        INSERT INTO s360.dim_homeroom_class_student 
        (id, so_student_id, student_code, student_name, homeroom_class_id, class_code, class_name, so_school_id, school_year_id, grade_id, grade_name, join_date)
        VALUES (:id, :so_student_id, :student_code, :student_name, :homeroom_class_id, :class_code, :class_name, :so_school_id, :school_year_id, :grade_id, :grade_name, :join_date);
    """, students_params)

    # --- 6. Behavior Dimensions ---
    session.execute(text("""
        INSERT INTO s360.dim_behavior (id, code, name, group_code, group_name, point)
        VALUES 
        (1, 'VI_PHAM_NE_NEP', 'Đi học muộn / Tóc vi phạm', 'NE_NEP', 'Nề nếp', -2.0),
        (2, 'QUAY_PHA_TRONG_GIO', 'Nói chuyện riêng / Quậy phá', 'KY_LUAT', 'Kỷ luật Class', -5.0),
        (3, 'KHEN_THUONG_HOC_TAP', 'Học tập xuất sắc', 'KHEN_THUONG', 'Khen thưởng', 5.0)
        ON CONFLICT (id) DO NOTHING;
    """))

    # --- 7. Behavior Logs (CAUSAL: conduct_series thấp -> nhiều vi phạm) ---
    behavior_logs_params = []
    for p in students:
        if p.risk_tier in ['HIGH', 'CRITICAL']:
            num_logs = random.randint(2, 5)
            for _ in range(num_logs):
                w_offset = random.randint(p.crisis_week, 12) if p.crisis_week < 12 else random.randint(1, 12)
                log_date = SCHOOL_YEAR_START + timedelta(weeks=w_offset)
                behavior_logs_params.append({
                    "so_school_id": p.school_id,
                    "school_year_id": 2025,
                    "student_code": p.code,
                    "behavior_id": random.choice([1, 2]),
                    "behavior_code": "QUAY_PHA_TRONG_GIO",
                    "behavior_fullname": "Nói chuyện riêng / Quậy phá trong giờ",
                    "behavior_point": -5.0,
                    "behavior_comment": "Học sinh lơ đãng, không tập trung nghe giảng",
                    "comment_date": log_date
                })

    execute_batch(session, """
        INSERT INTO s360.fact_behavior_logs 
        (so_school_id, school_year_id, student_code, behavior_id, behavior_code, behavior_fullname, behavior_point, behavior_comment, comment_date)
        VALUES (:so_school_id, :school_year_id, :student_code, :behavior_id, :behavior_code, :behavior_fullname, :behavior_point, :behavior_comment, :comment_date);
    """, behavior_logs_params)

    # --- 8. Absence Logs & Attendance (CAUSAL: attend_series thấp -> nghỉ nhiều) ---
    absent_logs_params = []
    daily_attendance_params = []

    for p in students:
        for week in range(1, 13):
            week_date = SCHOOL_YEAR_START + timedelta(weeks=week - 1)
            # Chuyên cần từ AR(1) series (0-1)
            attend_prob = float(np.clip(1.0 - p.attend_series[week-1], 0.0, 1.0))
            if p.risk_tier in ['HIGH', 'CRITICAL'] and week >= p.crisis_week:
                attend_prob = max(attend_prob, 0.5)

            if random.random() < attend_prob:
                is_unexcused = (p.risk_tier in ['HIGH', 'CRITICAL'] and week >= p.crisis_week)
                absent_logs_params.append({
                    "so_school_id": p.school_id,
                    "school_year_id": 2025,
                    "homeroom_class_id": p.homeroom_class_id,
                    "student_code": p.code,
                    "reason": "Gia đình có việc bận" if not is_unexcused else "Trốn học không lý do",
                    "reason_category": "CO_PHEU" if not is_unexcused else "KHONG_PHEU",
                    "from_date": week_date,
                    "to_date": week_date,
                    "is_approved": 0 if is_unexcused else 1,
                    "absent_date": week_date
                })
                daily_attendance_params.append({
                    "_date": week_date,
                    "school_year_id": 2025,
                    "student_code": p.code,
                    "homeroom_class_id": p.homeroom_class_id,
                    "grade_id": p.grade_id,
                    "total_periods": 5,
                    "absent_periods": 5,
                    "absent_no_permission": 5 if is_unexcused else 0,
                    "absent_with_permission": 0 if is_unexcused else 5
                })

    execute_batch(session, """
        INSERT INTO s360.fact_absent_logs 
        (so_school_id, school_year_id, homeroom_class_id, student_code, reason, reason_category, from_date, to_date, is_approved, absent_date)
        VALUES (:so_school_id, :school_year_id, :homeroom_class_id, :student_code, :reason, :reason_category, :from_date, :to_date, :is_approved, :absent_date);
    """, absent_logs_params)

    execute_batch(session, """
        INSERT INTO s360.fact_so_daily_attendance
        (_date, school_year_id, student_code, homeroom_class_id, grade_id, total_periods, absent_periods, absent_no_permission, absent_with_permission)
        VALUES (:_date, :school_year_id, :student_code, :homeroom_class_id, :grade_id, :total_periods, :absent_periods, :absent_no_permission, :absent_with_permission);
    """, daily_attendance_params)

    # --- 9. SWB Survey & SWB Support ---
    swb_survey_params = []
    swb_support_params = []

    for p in students:
        for week in range(1, 13):
            survey_date = SCHOOL_YEAR_START + timedelta(weeks=week - 1)
            swb_score = p.get_swb_score_at_week(week)
            swb_survey_params.append({
                "survey_date": survey_date,
                "school_year_id": 2025,
                "school_year": "2025-2026",
                "student_code": p.code,
                "homeroom_class_id": p.homeroom_class_id,
                "grade_id": p.grade_id,
                "question_set_id": 195,
                "question_group_id": 6,
                "question_group_name": "Sức khỏe tâm thần & Cảm xúc",
                "question_group_name_en": "Mental Wellbeing Index",
                "question_id": 264,
                "converted_score": swb_score
            })

        if p.risk_tier == 'CRITICAL' and p.crisis_week < 12:
            start_d = SCHOOL_YEAR_START + timedelta(weeks=p.crisis_week)
            swb_support_params.append({
                "student_code": p.code,
                "loai_can_thiep": "Hỗ trợ Tư vấn Tâm lý & Can thiệp Đặc biệt",
                "ten_ho_tro": p.crisis_type,
                "trang_thai_ho_tro": "Đang xử lý",
                "ngay_bat_dau": start_d,
                "school_year_id": 2025,
                "school_year": "2025-2026",
                "grade_id": p.grade_id,
                "homeroom_class_id": p.homeroom_class_id,
                "iep_muc_tieu": "Hỗ trợ ổn định tâm lý, giúp học sinh vượt qua biến cố gia đình và cải thiện chuyên cần",
                "iep_tiep_can": "Tham vấn tâm lý cá nhân 2 buổi/tuần kết hợp trao đổi sát sao với GVCN",
                "iep_can_thiep_cu_the": f"Chuyên viên tâm lý làm việc trực tiếp về sự cố: {p.crisis_type}. Đề nghị GVBM không ép phát biểu.",
                "iep_ke_hoach_trien_khai": "Theo dõi chỉ số SWB hàng tuần, đánh giá lại sau 4 tuần can thiệp",
                "iep_thu_thap_thong_tin": f"Học sinh có biểu hiện trầm cảm, thu mình sau sự cố: {p.crisis_type}",
                "iep_nhat_ky_tro_giup": "Buổi 1: Học sinh khóc nhiều khi nhắc đến biến cố. Buổi 2: Đã hướng dẫn kỹ năng giải tỏa cảm xúc.",
                "ngay_cap_nhat_iep": start_d + timedelta(days=7),
                "iep_actions_can_lam": "⬜ Đang thực hiện lộ trình IEP - Cần theo dõi điểm chuyên cần",
                "ma_van_de_dang_can_thiep": "FAMILY_CRISIS_DEPRESSION"
            })

    execute_batch(session, """
        INSERT INTO s360.fact_swb_survey 
        (survey_date, school_year_id, school_year, student_code, homeroom_class_id, grade_id, question_set_id, question_group_id, question_group_name, question_group_name_en, question_id, converted_score)
        VALUES (:survey_date, :school_year_id, :school_year, :student_code, :homeroom_class_id, :grade_id, :question_set_id, :question_group_id, :question_group_name, :question_group_name_en, :question_id, :converted_score);
    """, swb_survey_params)

    execute_batch(session, """
        INSERT INTO s360.fact_swb_support 
        (student_code, loai_can_thiep, ten_ho_tro, trang_thai_ho_tro, ngay_bat_dau, school_year_id, school_year, grade_id, homeroom_class_id, iep_muc_tieu, iep_tiep_can, iep_can_thiep_cu_the, iep_ke_hoach_trien_khai, iep_thu_thap_thong_tin, iep_nhat_ky_tro_giup, ngay_cap_nhat_iep, iep_actions_can_lam, ma_van_de_dang_can_thiep)
        VALUES (:student_code, :loai_can_thiep, :ten_ho_tro, :trang_thai_ho_tro, :ngay_bat_dau, :school_year_id, :school_year, :grade_id, :homeroom_class_id, :iep_muc_tieu, :iep_tiep_can, :iep_can_thiep_cu_the, :iep_ke_hoach_trien_khai, :iep_thu_thap_thong_tin, :iep_nhat_ky_tro_giup, :ngay_cap_nhat_iep, :iep_actions_can_lam, :ma_van_de_dang_can_thiep);
    """, swb_support_params)

    # --- 10. Gradebooks (23 môn, AR(1) + Logistic Decay) ---
    # MỖI MÔN TẠO 3 MỐC ĐIỂM (2 HK1 + 1 HK2) với created_at QUÁ KHỨ + is_locked=1
    # để EWS feature_extractor (WHERE is_locked=1 AND created_at<=cutoff) trả về dữ liệu.
    gradebooks_params = []
    subject_records_params = []
    overall_records_params = []

    # 3 mốc điểm: (exam_id, semester_index, created_at, week)
    # exam_id = s_id*10 + mốc (1=TX HK1, 2=Giữa HK1, 3=Đầu HK2)
    EXAM_MILESTONES = [
        (1, 1, 1),   # TX đầu HK1 (week 1)
        (2, 1, 5),   # Giữa HK1 (week 5)
        (3, 2, 1),   # Đầu HK2 (week 1)
    ]

    for p in students:
        subject_grades = []
        # base_ability theo PROFILE G1-G9 (trải rộng 0-10 như v2), không theo risk_tier
        base_ability = PROFILE_BASE_ABILITY[p.profile]

        for s_id, code, name, name_en, atype, scale, cat in SUBJECTS_23:
            if atype == 'REMARK':
                continue  # Môn nhận xét xử lý riêng
            if code.startswith('TOAN_'):
                try:
                    if int(code.split('_')[1]) != p.grade_id:
                        continue
                except (IndexError, ValueError):
                    pass
            # Điểm thi từ grade_series (AR(1) + logistic decay + specialization) — dùng mốc giữa HK1 (week 5)
            exam_grade = p.get_exam_grade(week=5, base_ability=base_ability, subject_category=cat, subject_code=code)
            native, score_10, letter, pct = convert_to_scale(exam_grade, scale)
            subject_grades.append(score_10)

            # Tạo 3 mốc điểm cho môn này
            for m_idx, sem_idx, week in EXAM_MILESTONES:
                # Điểm mỗi mốc: biến thiên nhẹ quanh điểm chính (AR(1) persistence)
                m_grade = float(np.clip(exam_grade + random.uniform(-0.5, 0.5), 0.0, 10.0))
                m_native, m_score, m_letter, m_pct = convert_to_scale(m_grade, scale)
                gradebooks_params.append({
                    "id": len(gradebooks_params) + 1,
                    "so_school_id": p.school_id,
                    "school_year_id": 2025,
                    "semester_index": sem_idx,
                    "homeroom_class_id": p.homeroom_class_id,
                    "student_code": p.code,
                    "subject_id": s_id,
                    "exam_id": s_id * 10 + m_idx,
                    "final_grade": m_score,
                    "letter": m_letter,
                    "pct": m_pct,
                    "scale_name": scale,
                    "max_grade": 10.0,
                    "pass_fail": 'DAT' if m_score >= 5.0 else 'CHUA_DAT',
                    "is_locked": 1,
                    "created_at": EXAM_CREATED_AT[m_idx]
                })

        avg_gpa = round(float(np.mean(subject_grades)), 2)
        overall_records_params.append({
            "id": p.student_id,
            "so_school_id": p.school_id,
            "school_year_id": 2025,
            "grade_id": p.grade_id,
            "homeroom_class_id": p.homeroom_class_id,
            "student_id": p.student_id,
            "student_code": p.code,
            "final_grade": avg_gpa,
            "s1_final_grade": avg_gpa,
            "conduct": "TOT" if p.risk_tier == 'SAFE' else ("KHA" if p.risk_tier == 'MODERATE' else "TRUNG_BINH"),
            "learning_capacity": "Giỏi" if avg_gpa >= 8.0 else ("Khá" if avg_gpa >= 6.5 else "Trung bình")
        })

    execute_batch(session, """
        INSERT INTO s360.fact_gradebooks 
        (id, so_school_id, school_year_id, semester_index, homeroom_class_id, student_code, subject_id, so_exam_id, final_grade, final_grade_letter, final_grade_percent, scale_name_used, max_grade, pass_fail_status, is_locked, created_at)
        VALUES (:id, :so_school_id, :school_year_id, :semester_index, :homeroom_class_id, :student_code, :subject_id, :exam_id, :final_grade, :letter, :pct, :scale_name, :max_grade, CAST(:pass_fail AS public.pass_fail_enum), :is_locked, :created_at);
    """, gradebooks_params)

    execute_batch(session, """
        INSERT INTO s360.fact_overall_academic_records 
        (id, so_school_id, school_year_id, grade_id, homeroom_class_id, student_id, student_code, final_grade, s1_final_grade, conduct, learning_capacity)
        VALUES (:id, :so_school_id, :school_year_id, :grade_id, :homeroom_class_id, :student_id, :student_code, :final_grade, :s1_final_grade, CAST(:conduct AS public.conduct_enum), :learning_capacity);
    """, overall_records_params)

    # --- 10b. LMS Assignments (dim_so_assignment) + Điểm LMS (fact_so_assignment_grade) ---
    # EWS feature_extractor có 5 LMS features từ fact_so_assignment_grade JOIN dim_so_assignment.
    # Cần seed để EWS có đủ 4 nhóm features (score, lms, attendance, behavior).
    # QUAN TRỌNG: feature_extractor JOIN theo (so_school_id, grade_id) → phải seed assignment
    # cho CẢ 2 TRƯỜNG x MỌI KHỐI 6-10, không chỉ school 1/grade 8.
    # Mỗi môn SCORED: 4 bài tập LMS/học kỳ, due_date trong quá khứ (trước cutoff week 5).
    assignments_params = []
    assign_id = 1
    for school_id in [1, 2]:
        for g_id in range(6, 11):  # grade 6-10 (khớp dim_homeroom_class)
            for s_id, code, name, name_en, atype, scale, cat in SUBJECTS_23:
                if atype == 'REMARK':
                    continue
                if code.startswith('TOAN_'):
                    try:
                        if int(code.split('_')[1]) != g_id:
                            continue
                    except (IndexError, ValueError):
                        pass
                for sem_idx in [1, 2]:
                    for w in range(1, 5):  # 4 bài tập mỗi học kỳ
                        due = (SCHOOL_YEAR_START + timedelta(weeks=w)) if sem_idx == 1 else (date(2026, 1, 20) + timedelta(weeks=w))
                        assignments_params.append({
                            "assignment_id": assign_id,
                            "so_school_id": school_id,
                            "grade_id": g_id,
                            "semester_index": sem_idx,
                            "subject_id": s_id,
                            "code": f"ASS_{school_id}_{g_id}_{code}_SEM{sem_idx}_W{w}",
                            "fullname": f"Bài tập {name} Khối {g_id} HK{sem_idx} Tuần {w}",
                            "max_grade": 10.0,
                            "date_assigned": due - timedelta(days=7),
                            "due_date": due
                        })
                        assign_id += 1
    execute_batch(session, """
        INSERT INTO s360.dim_so_assignment 
        (assignment_id, so_school_id, grade_id, semester_index, subject_id, code, fullname, max_grade, date_assigned, due_date)
        VALUES (:assignment_id, :so_school_id, :grade_id, :semester_index, :subject_id, :code, :fullname, :max_grade, :date_assigned, :due_date)
        ON CONFLICT (assignment_id) DO NOTHING;
    """, assignments_params)

    # Điểm LMS: mỗi học sinh nộp bài với xác suất theo profile + lms_series AR(1).
    # CHỈ lấy assignments KHỚP (so_school_id, grade_id) của học sinh — mirror feature_extractor.
    # M0.1: seed thêm cột hành vi làm bài (active_time_sec, tab_hidden_count, idle_sec, rte)
    # để M3 (lms_evidence) demo được các nhóm: effortful-but-lost / rapid-guess / off-task.
    lms_grade_params = []
    lms_id = 1
    for p in students:
        # Xác suất nộp bài theo profile (G1-G9 như v2): G1 cao, G9 thấp
        submit_prob = {
            "G1": 0.95, "G2": 0.85, "G3": 0.80, "G4": 0.70, "G5": 0.60,
            "G6": 0.85, "G7": 0.55, "G8": 0.30, "G9": 0.10,
        }.get(p.profile, 0.70)
        # Điểm LMS gốc theo profile (tương quan với điểm thi) + lms_effort latent
        lms_base = PROFILE_BASE_ABILITY[p.profile] + p.latents[4] * 0.8
        lms_base = float(np.clip(lms_base, 0.0, 10.0))

        for a in assignments_params:
            # CHỈ bài tập đúng trường + đúng khối của học sinh (feature_extractor JOIN điều kiện này)
            if a["so_school_id"] != p.school_id or a["grade_id"] != p.grade_id:
                continue
            if random.random() > submit_prob:
                continue  # không nộp bài → không có dòng (EWS tính submission rate)
            # Điểm LMS: lms_base + biến thiên AR(1) theo tuần
            week_idx = a["semester_index"] * 4 + a["due_date"].isocalendar()[1] % 4
            lms_score = float(np.clip(lms_base + (p.lms_series[week_idx % 12] - 0.85) * 3.0, 0.0, 10.0))
            # M0.1: hành vi làm bài LMS (time_limit mặc định 30 phút = 1800s).
            time_limit = 1800
            if lms_score < 5.0 and p.latents[4] > 0.5:
                # Nỗ lực nhưng không hiểu: làm lâu, nhiều lần thử.
                active_sec = random.randint(1500, time_limit)
                attempts = random.randint(2, 4)
                tab_hidden = 0
                rte = 1
            elif lms_score < 5.0 and random.random() < 0.4:
                # Làm qua loa / đoán mò.
                active_sec = random.randint(30, 150)
                attempts = 1
                tab_hidden = 0
                rte = 0
            elif random.random() < 0.05:
                # Treo máy: tổng thời gian dài nhưng active thấp + rời tab nhiều.
                active_sec = random.randint(200, 500)
                tab_hidden = random.randint(3, 6)
                attempts = 1
                rte = 0
            else:
                # Làm bài bình thường.
                active_sec = random.randint(400, 1400)
                attempts = 1
                tab_hidden = 0
                rte = 1
            submitted_at = datetime.combine(a["due_date"], datetime.min.time()) - timedelta(hours=random.randint(1, 24))
            lms_grade_params.append({
                "id": lms_id,
                "so_school_id": p.school_id,
                "assignment_id": a["assignment_id"],
                "student_code": p.code,
                "final_grade": round(lms_score, 1),
                "is_locked": 1,
                "started_at": submitted_at - timedelta(minutes=random.randint(5, 60)),
                "submitted_at": submitted_at,
                "attempt_count": attempts,
                "time_spent_sec": active_sec + tab_hidden * 300 + random.randint(0, 200),
                "active_time_sec": active_sec,
                "tab_hidden_count": tab_hidden,
                "idle_sec": tab_hidden * 300,
                "rte": rte,
            })
            lms_id += 1

    execute_batch(session, """
        INSERT INTO s360.fact_so_assignment_grade 
        (id, so_school_id, assignment_id, student_code, final_grade, is_locked,
         started_at, submitted_at, attempt_count, time_spent_sec, active_time_sec,
         tab_hidden_count, idle_sec, rte)
        VALUES (:id, :so_school_id, :assignment_id, :student_code, :final_grade, :is_locked,
                :started_at, :submitted_at, :attempt_count, :time_spent_sec, :active_time_sec,
                :tab_hidden_count, :idle_sec, :rte);
    """, lms_grade_params)
    logger.info(f"Seeded {len(lms_grade_params)} LMS assignment grades (dim_so_assignment={len(assignments_params)})")

    # --- 10c. Auxiliary tables (dim_exam_moet, grade_scale, course, evaluate, homeroom att) ---
    # Để v4 ngang v2 về độ phủ schema (các bảng fact/dim phụ còn trống).
    seed_auxiliary_tables(session, students)

    # --- 10d. Benchmark edge case students (5 học sinh như v2) ---
    seed_benchmark_students(session, students)

    # --- 10e. Public auxiliary tables (ai_*, exam_papers, curriculum_units, audit_logs...) ---
    seed_public_aux_tables(session, students)

    # --- 10f. Life events (biến cố LOW→CRITICAL) + Medical history (chỉ học sinh có bệnh) ---
    seed_life_events_and_medical(session, students)

    # --- 11. Sync Metadata (BỎ QUA NẾU --skip-metadata HOẶC API LỖI) ---
    session.commit()
    if skip_metadata:
        logger.info("SKIP metadata sync (--skip-metadata). Không gọi API embedding.")
    else:
        logger.info("Synchronizing metadata index for schools (timeout 30s per school)...")
        import concurrent.futures
        for school_id in [1, 2]:
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                fut = pool.submit(sync_school_metadata, so_school_id=school_id)
                try:
                    fut.result(timeout=30)
                    logger.info(f"Metadata sync school {school_id}: OK")
                except Exception as e:
                    logger.warning(f"Metadata sync school {school_id}: skipped (timeout/error: {e})")
                    fut.cancel()
                    continue

    # --- Validation 3: Schema integrity ---
    missing = validate_schema(session)
    if missing:
        logger.warning(f"Missing tables: {missing}")
    else:
        logger.info(f"Schema validation: ALL {len(SCHEMA_TABLES_37)} tables OK")

    logger.info("=" * 60)
    logger.info(f"GOLDEN SET V4 SEED COMPLETED: {len(students)} students, 23 subjects, 2 schools")
    logger.info("=" * 60)
    return students


# ============================================================================
# MAIN ENTRY POINT
# ============================================================================
def main():
    import argparse
    parser = argparse.ArgumentParser(description="Master Golden Set Mock Generator v4 (Copula + AR(1) + Logistic Decay)")
    parser.add_argument("--reset-db", action="store_true", help="Clean database and seed Golden Set v4 dataset")
    parser.add_argument("--students-per-school", type=int, default=100, help="Students per school (default: 100)")
    parser.add_argument("--skip-metadata", action="store_true", help="Bỏ qua sync metadata (không gọi API embedding)")
    args = parser.parse_args()

    session = SessionLocal()
    try:
        if args.reset_db:
            clean_database(session)
            seed_golden_set_v4(session, n_students_per_school=args.students_per_school, skip_metadata=args.skip_metadata)
        else:
            logger.info("No --reset-db flag. Running default seed...")
            clean_database(session)
            seed_golden_set_v4(session, n_students_per_school=args.students_per_school, skip_metadata=args.skip_metadata)
    except Exception as e:
        session.rollback()
        logger.error(f"Execution failed: {e}", exc_info=True)
        sys.exit(1)
    finally:
        session.close()


def clean_database(session):
    """Clean database trước khi seed (dùng TRUNCATE CASCADE để tránh FK violation)."""
    logger.info("Cleaning database...")
    tables = [
        "s360.fact_swb_survey", "s360.fact_swb_support",
        "s360.fact_student_life_events", "s360.fact_student_medical_history",
        "s360.fact_behavior_logs", "s360.fact_absent_logs",
        "s360.fact_so_daily_attendance", "s360.fact_gradebooks",
        "s360.fact_gradebooks_moet", "s360.fact_so_assignment_grade",
        "s360.fact_subject_academic_records", "s360.fact_overall_academic_records",
        "s360.fact_so_evaluate_process_subjects", "s360.fact_course_attendences",
        "s360.fact_so_class_attendance_statistics",
        "s360.fact_so_homeroom_class_attendances",
        "s360.fact_so_homeroom_class_late_attendances",
        "s360.dim_homeroom_class_student", "s360.dim_homeroom_class",
        "s360.dim_subject", "s360.dim_exam", "s360.dim_exam_moet",
        "s360.dim_behavior", "s360.dim_grade_scale_detail",
        "s360.dim_so_assignment", "s360.dim_course", "s360.dim_school_year",
        "public.users", "public.refresh_tokens", "public.teacher_assignments",
    ]
    # TRUNCATE CASCADE xử lý đúng FK dependencies
    try:
        tables_str = ", ".join(tables)
        session.execute(text(f"TRUNCATE TABLE {tables_str} RESTART IDENTITY CASCADE;"))
    except Exception as e:
        # Fallback: TRUNCATE từng bảng để chống lỗi thứ tự
        logger.warning(f"TRUNCATE CASCADE failed ({e}). Falling back to per-table...")
        session.rollback()
        for tbl in reversed(tables):
            try:
                session.execute(text(f"TRUNCATE TABLE {tbl} RESTART IDENTITY CASCADE;"))
            except Exception as e2:
                logger.warning(f"Truncate {tbl}: {e2}")
                session.rollback()
    session.commit()
    logger.info("Database cleaned.")


if __name__ == "__main__":
    main()