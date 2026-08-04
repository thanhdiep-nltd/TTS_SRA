#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
generate_train_dataset.py — EWS Training Data Synthesizer (Latent Causal Model)

MÔ TẢ:
    Script SINH dữ liệu train cho GBDT Early Warning System (EWS) bằng mô hình
    nhân quả tiềm ẩn (Latent Causal Model). KHÔNG query database thật.

KIẾN TRÚC:
    Latent Variables (TAD-PG) → Full Trajectory → Ground Truth (65/15/10/10)
                                                    ↓
                                              Features tại Checkpoint (temporal asymmetry)

OUTPUT:
    1. data_mock/mock_train_data/train_risk_dataset.csv
    2. s360.train_student_subject_risk_dataset (DB insert - optional)

TECH REFINEMENTS:
    - Numpy Vectorization: xử lý hàng loạt, ~113K rows trong < 1 giây
    - Feature Noise (5%): chống overfitting cho GBDT

Author: Product Team & Senior Reviewer Consensus
Version: 1.0
"""

import os
import sys
import time
import warnings
import numpy as np
import pandas as pd
from numpy.typing import NDArray
from typing import Optional

# Suppress harmless RuntimeWarning from np.nanmean on all-NaN slices
warnings.filterwarnings("ignore", "Mean of empty slice", category=RuntimeWarning)

# ============================================================================
# PHẦN 1: CẤU HÌNH & HẰNG SỐ
# ============================================================================

# --- TAD-PG Personas (giữ nguyên từ v2 generator) ---
PERSONAS = ["High_Achiever", "STEM_Focus", "Humanities_Focus", "Diligent_Average", "Academic_At_Risk"]
PERSONA_WEIGHTS = np.array([15, 15, 15, 45, 10], dtype=np.float64)
PERSONA_PROB = PERSONA_WEIGHTS / PERSONA_WEIGHTS.sum()

# --- Score Profiles G1-G9 ---
PROFILES = ["G1", "G2", "G3", "G4", "G5", "G6", "G7", "G8", "G9"]
PROFILE_WEIGHTS = np.array([10, 20, 12, 15, 8, 10, 12, 8, 5], dtype=np.float64)
PROFILE_PROB = PROFILE_WEIGHTS / PROFILE_WEIGHTS.sum()

# --- Danh sách môn học ---
# (subject_id, name, is_math_science, subject_category)
SUBJECTS = [
    (106, "Toán", True, "MATH_SCIENCE"),
    (2, "Ngữ văn", False, "HUMANITIES"),
    (3, "Tiếng Anh", False, "HUMANITIES"),
    (7, "KHTN", True, "MATH_SCIENCE"),
    (8, "Lịch sử & Địa lý", False, "HUMANITIES"),
    (4, "Vật lý", True, "MATH_SCIENCE"),
    (5, "Hóa học", True, "MATH_SCIENCE"),
    (6, "Sinh học", True, "MATH_SCIENCE"),
    (13, "Tin học", True, "TECHNOLOGY"),
    (14, "STEM", True, "TECHNOLOGY"),
    (9, "Cambridge English", False, "HUMANITIES"),
]
N_SUBJECTS = len(SUBJECTS)
SUBJECT_IDS = np.array([s[0] for s in SUBJECTS])
IS_MATH_SCIENCE = np.array([s[2] for s in SUBJECTS], dtype=bool)
SUBJECT_CATEGORIES = np.array([s[3] for s in SUBJECTS])

# --- Cấu hình bài kiểm tra theo MoET ---
# Mỗi học kỳ có 4 cột điểm với hệ số khác nhau
# week_frac: vị trí tương đối trong học kỳ (0.0 → 1.0)
EXAM_COEFFS = np.array([1, 2, 3, 3], dtype=np.int32)        # Hệ số
EXAM_WEEK_FRAC = np.array([0.20, 0.45, 0.65, 0.90])         # Vị trí trong kỳ
N_EXAMS = len(EXAM_COEFFS)

# --- Checkpoints theo học kỳ ---
CHECKPOINTS_SEM1 = np.array([5, 8, 11, 14, 16], dtype=np.int32)
CHECKPOINTS_SEM2 = np.array([23, 26, 29, 32, 34], dtype=np.int32)
N_CHECKPOINTS = len(CHECKPOINTS_SEM1)

# --- Trọng số Ground Truth (65/15/10/10) ---
W_SCORE = 0.65
W_LMS = 0.15
W_ATTEND = 0.10
W_BEHAVE = 0.10

# --- Ngưỡng mapping final_grade → risk_level ---
RISK_THRESHOLDS = [6.5, 5.0, 3.5]  # LOW ≥ 6.5 > MODERATE ≥ 5.0 > HIGH ≥ 3.5 > CRITICAL
RISK_LEVELS = ["LOW", "MODERATE", "HIGH", "CRITICAL"]

# --- Feature Noise Level ---
FEATURE_NOISE_LEVEL = 0.05  # 5%

# --- Semester configs ---
SEMESTER_CONFIGS = [
    {"idx": 1, "weeks": CHECKPOINTS_SEM1, "scope": "SEMESTER_1", "total_weeks": 18},
    {"idx": 2, "weeks": CHECKPOINTS_SEM2, "scope": "SEMESTER_2", "total_weeks": 18},
]

# --- Seed cho reproducibility ---
RNG = np.random.default_rng(42)

# --- Đường dẫn output ---
OUTPUT_DIR = os.path.dirname(os.path.abspath(__file__))
CSV_PATH = os.path.join(OUTPUT_DIR, "train_risk_dataset.csv")

# ============================================================================
# PHẦN 2: SINH LATENT VARIABLES (TAD-PG)
# ============================================================================

def generate_students(
    n_students: int = 1028,
    school_year_id: int = 2025,
) -> dict:
    """
    Sinh latent variables cho N học sinh bằng TAD-PG engine (vectorized).

    Returns dict với các key:
        - codes: (N,) student codes
        - persona_idx: (N,) chỉ số persona
        - profile_idx: (N,) chỉ số profile
        - c_math: (N,) năng lực toán học
        - c_lang: (N,) năng lực ngôn ngữ
        - eff: (N,) effort
        - conduct: (N,) xu hướng hạnh kiểm
        - attend: (N,) xu hướng chuyên cần
    """
    # Persona & Profile assignment (vectorized weighted random)
    persona_idx = RNG.choice(len(PERSONAS), size=n_students, p=PERSONA_PROB)
    profile_idx = RNG.choice(len(PROFILES), size=n_students, p=PROFILE_PROB)

    # Latent variables: phân phối chuẩn, clip trong [-2.0, 2.0]
    c_math = np.clip(RNG.normal(0, 0.8, size=n_students), -2.0, 2.0)
    c_lang = np.clip(RNG.normal(0, 0.8, size=n_students), -2.0, 2.0)
    eff = np.clip(RNG.normal(0, 1.0, size=n_students), -2.0, 2.0)
    conduct = np.clip(RNG.normal(0.5, 0.8, size=n_students), -2.0, 2.0)
    attend = np.clip(RNG.normal(0.5, 0.8, size=n_students), -2.0, 2.0)

    # Điều chỉnh latent variables theo persona
    for p_idx, p_name in enumerate(PERSONAS):
        mask = persona_idx == p_idx
        n_mask = mask.sum()
        if n_mask == 0:
            continue
        if p_name == "High_Achiever":
            c_math[mask] = np.clip(RNG.normal(1.2, 0.4, size=n_mask), -2.0, 2.0)
            c_lang[mask] = np.clip(RNG.normal(1.2, 0.4, size=n_mask), -2.0, 2.0)
            eff[mask] = np.clip(RNG.normal(1.5, 0.4, size=n_mask), -2.0, 2.0)
            conduct[mask] = np.clip(RNG.normal(1.5, 0.3, size=n_mask), -2.0, 2.0)
            attend[mask] = np.clip(RNG.normal(1.5, 0.3, size=n_mask), -2.0, 2.0)
        elif p_name == "STEM_Focus":
            c_math[mask] = np.clip(RNG.normal(1.5, 0.4, size=n_mask), -2.0, 2.0)
            c_lang[mask] = np.clip(RNG.normal(-0.2, 0.5, size=n_mask), -2.0, 2.0)
            eff[mask] = np.clip(RNG.normal(1.2, 0.4, size=n_mask), -2.0, 2.0)
        elif p_name == "Humanities_Focus":
            c_math[mask] = np.clip(RNG.normal(-0.5, 0.5, size=n_mask), -2.0, 2.0)
            c_lang[mask] = np.clip(RNG.normal(1.2, 0.4, size=n_mask), -2.0, 2.0)
        elif p_name == "Academic_At_Risk":
            c_math[mask] = np.clip(RNG.normal(-1.2, 0.5, size=n_mask), -2.0, 2.0)
            c_lang[mask] = np.clip(RNG.normal(-1.0, 0.5, size=n_mask), -2.0, 2.0)
            eff[mask] = np.clip(RNG.normal(-1.5, 0.5, size=n_mask), -2.0, 2.0)
            conduct[mask] = np.clip(RNG.normal(-0.5, 0.6, size=n_mask), -2.0, 2.0)
            attend[mask] = np.clip(RNG.normal(-0.5, 0.6, size=n_mask), -2.0, 2.0)

    # Sinh student codes
    codes, grades, schools = _generate_student_codes(n_students)

    # M2: tuần nhập học (global week 1..36, 1 = đầu HK1, 19 = đầu HK2).
    #   - 88%: có mặt từ đầu HK1 (join_week = 1)
    #   - 8% : nhập giữa HK1 (week 3..17) → cửa sổ expected ngắn hơn
    #   - 4% : nhập trong HK2 (week 19..36) → CHUYEN_TRUONG ở toàn bộ HK1
    # Các học sinh nhập học trễ có submitted/expected khác nhau → model học đúng
    # 3 bucket (mirror feature_extractor serve-side, tránh train/serve skew).
    join_r = RNG.uniform(0, 1, size=n_students)
    join_week_global = np.ones(n_students, dtype=np.int32)
    mid_mask = (join_r >= 0.88) & (join_r < 0.96)
    late_mask = join_r >= 0.96
    join_week_global[mid_mask] = RNG.integers(3, 18, size=int(mid_mask.sum()))
    join_week_global[late_mask] = RNG.integers(19, 37, size=int(late_mask.sum()))

    return {
        "codes": codes,
        "grades": grades,
        "schools": schools,
        "persona_idx": persona_idx,
        "profile_idx": profile_idx,
        "c_math": c_math,
        "c_lang": c_lang,
        "eff": eff,
        "conduct": conduct,
        "attend": attend,
        "join_week_global": join_week_global,
    }


def _generate_student_codes(n_students: int) -> tuple[NDArray[np.str_], NDArray[np.int32], NDArray[np.int32]]:
    """
    Sinh mã học sinh format HS{school}{grade}{idx:04d}
    Phân bố: 50% school 1, 50% school 2, grade 6-11.
    """
    schools = RNG.integers(1, 3, size=n_students)  # 1 hoặc 2
    grades = RNG.integers(6, 12, size=n_students)  # 6-11
    # Dùng index làm số thứ tự (đơn giản hơn v2)
    indices = np.arange(1, n_students + 1)

    codes = np.array([
        f"HS{s}{g}{i:04d}" for s, g, i in zip(schools, grades, indices)
    ], dtype=str)
    return codes, grades, schools


# ============================================================================
# PHẦN 3: SCORE TRAJECTORY GENERATION (VECTORIZED)
# ============================================================================

def _get_profile_trend_offsets(
    profile_idx: NDArray[np.int32],  # (N,)
    week_frac: float,                # 0.0 → 1.0
    n_students: int,
) -> NDArray[np.float64]:
    """
    Tính trend offset cho mỗi student tại một vị trí tuần trong kỳ.
    Profile G1-G9 quyết định xu hướng điểm.

    Returns: (N,) array - offset cộng vào base score
    """
    offsets = np.zeros(n_students, dtype=np.float64)

    for p_idx, p_name in enumerate(PROFILES):
        mask = profile_idx == p_idx
        n_mask = mask.sum()
        if n_mask == 0:
            continue

        if p_name == "G1":        # Cao ổn định
            offsets[mask] = RNG.uniform(0.5, 1.5, size=n_mask)
        elif p_name == "G2":      # Trung bình ổn định
            offsets[mask] = RNG.uniform(-0.5, 0.5, size=n_mask)
        elif p_name == "G3":      # Cải thiện dần
            offsets[mask] = -1.5 + 2.5 * week_frac + RNG.uniform(-0.3, 0.3, size=n_mask)
        elif p_name == "G4":      # TB-thấp biến động
            offsets[mask] = RNG.uniform(-1.5, -0.5, size=n_mask)
        elif p_name == "G5":      # Cao giảm dần
            offsets[mask] = 1.5 - 2.0 * week_frac + RNG.uniform(-0.3, 0.3, size=n_mask)
        elif p_name == "G6":      # Thấp, LMS bù
            offsets[mask] = RNG.uniform(-3.0, -2.0, size=n_mask)
        elif p_name == "G7":      # Giảm mạnh
            offsets[mask] = 0.5 - 3.0 * week_frac + RNG.uniform(-0.3, 0.3, size=n_mask)
        elif p_name == "G8":      # Rất thấp
            offsets[mask] = RNG.uniform(-4.0, -2.5, size=n_mask)
        elif p_name == "G9":      # Zero
            offsets[mask] = -10.0

    return offsets


def generate_exam_scores(
    students: dict,
) -> NDArray[np.float64]:
    """
    Sinh điểm thi cho tất cả (student, subject, exam) — vectorized.

    Returns: (N_students, N_subjects, N_exams) array
    """
    N = len(students["codes"])
    c_math = students["c_math"]
    c_lang = students["c_lang"]
    eff = students["eff"]
    profile_idx = students["profile_idx"]

    # Base ability theo loại môn: (N,) → (N, N_subjects)
    # Mỗi cột: base_ability cho subject đó
    base = np.zeros((N, N_SUBJECTS), dtype=np.float64)
    for s_idx in range(N_SUBJECTS):
        if IS_MATH_SCIENCE[s_idx]:
            base[:, s_idx] = np.clip(6.5 + 1.5 * c_math + 0.5 * eff, 0.0, 10.0)
        else:
            base[:, s_idx] = np.clip(6.5 + 1.5 * c_lang + 0.5 * eff, 0.0, 10.0)

    # Sinh điểm cho từng bài kiểm tra
    all_scores = np.zeros((N, N_SUBJECTS, N_EXAMS), dtype=np.float64)

    for e_idx in range(N_EXAMS):
        week_frac = float(EXAM_WEEK_FRAC[e_idx])

        # Trend offset: (N,) → (N, N_SUBJECTS)
        offset = _get_profile_trend_offsets(profile_idx, week_frac, N)
        offset_2d = np.tile(offset[:, np.newaxis], (1, N_SUBJECTS))

        # Noise: (N, N_SUBJECTS)
        noise = RNG.normal(0, 0.3, size=(N, N_SUBJECTS))

        # Score = base + offset + noise, clip [0, 10]
        scores = np.clip(base + offset_2d + noise, 0.0, 10.0)

        # Làm tròn 1 chữ số thập phân
        all_scores[:, :, e_idx] = np.round(scores, 1)

    return all_scores  # (N, N_SUBJECTS, N_EXAMS)


# ============================================================================
# PHẦN 4: LMS TRAJECTORY GENERATION (VECTORIZED)
# ============================================================================

def generate_lms_data(
    students: dict,
) -> dict:
    """
    Sinh dữ liệu LMS cho tất cả student (vectorized).

    Returns dict:
        - submission_rate: (N, N_SUBJECTS) — tỷ lệ nộp bài LMS toàn kỳ
        - avg_score: (N, N_SUBJECTS) — điểm LMS trung bình
        - weekly_scores: (N, N_SUBJECTS, 18) — điểm LMS theo từng tuần
    """
    N = len(students["codes"])
    persona_idx = students["persona_idx"]
    eff = students["eff"]

    # --- Base LMS behavior theo persona ---
    # submission_rate: (N,)
    sub_rate = np.full(N, 0.70, dtype=np.float64)
    avg_lms = np.full(N, 6.5, dtype=np.float64)

    for p_idx, p_name in enumerate(PERSONAS):
        mask = persona_idx == p_idx
        n_mask = mask.sum()
        if n_mask == 0:
            continue
        if p_name == "High_Achiever":
            sub_rate[mask] = RNG.uniform(0.85, 0.98, size=n_mask)
            avg_lms[mask] = RNG.uniform(7.5, 9.5, size=n_mask)
        elif p_name in ("STEM_Focus", "Humanities_Focus"):
            sub_rate[mask] = RNG.uniform(0.75, 0.92, size=n_mask)
            avg_lms[mask] = RNG.uniform(7.0, 9.0, size=n_mask)
        elif p_name == "Diligent_Average":
            sub_rate[mask] = RNG.uniform(0.65, 0.88, size=n_mask)
            avg_lms[mask] = RNG.uniform(5.5, 7.5, size=n_mask)
        elif p_name == "Academic_At_Risk":
            sub_rate[mask] = np.clip(RNG.uniform(0.15, 0.55, size=n_mask), 0.01, 0.99)
            avg_lms[mask] = RNG.uniform(1.5, 4.5, size=n_mask)

    # Effort modifier: eff cao → tăng nhẹ sub_rate và avg_score
    eff_mod = np.clip(eff * 0.05, -0.10, 0.10)
    sub_rate = np.clip(sub_rate + eff_mod, 0.01, 0.99)
    avg_lms = np.clip(avg_lms + eff * 0.2, 0.0, 10.0)

    # Mở rộng ra (N, N_SUBJECTS)
    sub_rate_2d = np.tile(sub_rate[:, np.newaxis], (1, N_SUBJECTS))
    avg_lms_2d = np.tile(avg_lms[:, np.newaxis], (1, N_SUBJECTS))

    # Sinh weekly scores: mỗi tuần có 1 LMS assignment
    n_weeks = 18
    weekly_scores = np.zeros((N, N_SUBJECTS, n_weeks), dtype=np.float64)

    for w in range(n_weeks):
        # Mỗi tuần: học sinh có xác suất sub_rate để nộp bài
        submitted = RNG.uniform(0, 1, size=(N, N_SUBJECTS)) < sub_rate_2d
        # Điểm nếu nộp: xoay quanh avg_lms
        score_if_submit = np.clip(
            avg_lms_2d + RNG.normal(0, 1.0, size=(N, N_SUBJECTS)),
            0.0, 10.0,
        )
        weekly_scores[:, :, w] = np.where(submitted, score_if_submit, np.nan)

    return {
        "submission_rate": sub_rate_2d,
        "avg_score": avg_lms_2d,
        "weekly_scores": weekly_scores,  # (N, N_SUBJECTS, 18), NaN = không nộp
    }


# ============================================================================
# PHẦN 5: ATTENDANCE TRAJECTORY GENERATION (VECTORIZED)
# ============================================================================

def generate_attendance_data(
    students: dict,
    n_days: int = 90,  # ~90 ngày học / học kỳ
) -> dict:
    """
    Sinh dữ liệu điểm danh cho tất cả student (vectorized).

    Returns dict:
        - daily_absence_rate: (N,) — tỷ lệ vắng toàn kỳ
        - unexcused_absent_rate: (N,) — tỷ lệ vắng không phép
        - excused_absent_days: (N,) — số ngày vắng có phép
        - total_late_count: (N,) — số lần đi muộn
        - daily_status: (N, n_days) — 0=đi học, 1=vắng KP, 2=vắng CP, 3=đi muộn
    """
    N = len(students["codes"])
    attend = students["attend"]
    persona_idx = students["persona_idx"]

    # Base absence rate from latent variable
    # Tăng dải tỷ lệ nghỉ để có đủ học sinh rủi ro chuyên cần (trước đây attendance_component
    # ~99.8% LOW → không train được sub-model riêng). Cần absence > 0.5 để có HIGH/CRITICAL.
    absence_rate = np.clip(0.15 - 0.06 * attend, 0.01, 0.80)

    # Persona modifier
    for p_idx, p_name in enumerate(PERSONAS):
        mask = persona_idx == p_idx
        n_mask = mask.sum()
        if n_mask == 0:
            continue
        if p_name == "Academic_At_Risk":
            absence_rate[mask] = np.clip(absence_rate[mask] + 0.35, 0.05, 0.85)
        elif p_name == "High_Achiever":
            absence_rate[mask] = np.clip(absence_rate[mask] - 0.05, 0.01, 0.30)

    # Chi tiết: unexcused rate = 60% absence, excused = 40% absence
    unexcused_rate = absence_rate * 0.6
    excused_rate = absence_rate * 0.4

    # Số ngày
    daily_status = np.zeros((N, n_days), dtype=np.int32)
    for d in range(n_days):
        rnd = RNG.uniform(0, 1, size=N)
        # Đi muộn: ~3% số ngày
        late_mask = RNG.uniform(0, 1, size=N) < 0.03
        # Vắng không phép
        unexcused_mask = (rnd < unexcused_rate) & ~late_mask
        # Vắng có phép
        excused_mask = (rnd >= unexcused_rate) & (rnd < unexcused_rate + excused_rate) & ~late_mask

        daily_status[late_mask, d] = 3
        daily_status[unexcused_mask, d] = 1
        daily_status[excused_mask, d] = 2

    # Tổng hợp
    excused_absent_days = (daily_status == 2).sum(axis=1)
    total_late_count = (daily_status == 3).sum(axis=1)
    daily_absence_rate = ((daily_status == 1) | (daily_status == 2)).sum(axis=1) / n_days
    unexcused_absent_rate = (daily_status == 1).sum(axis=1) / n_days

    return {
        "daily_absence_rate": daily_absence_rate,
        "unexcused_absent_rate": unexcused_absent_rate,
        "excused_absent_days": excused_absent_days,
        "total_late_count": total_late_count,
        "daily_status": daily_status,
    }


# ============================================================================
# PHẦN 6: BEHAVIOR TRAJECTORY GENERATION (VECTORIZED)
# ============================================================================

def generate_behavior_data(
    students: dict,
) -> dict:
    """
    Sinh dữ liệu hành vi, kỷ luật cho tất cả student (vectorized).

    Returns dict:
        - total_demerit_points: (N,) — tổng điểm rèn luyện bị trừ
        - repeat_offense_count: (N,) — số lần tái phạm
        - severe_sanction_count: (N,) — số lần kỷ luật chính thức
    """
    N = len(students["codes"])
    conduct = students["conduct"]
    persona_idx = students["persona_idx"]

    # Base demerit từ latent variable
    # conduct ∈ [-2, 2], conduct cao → ít vi phạm
    # Tăng dải điểm trừ kỷ luật để có đủ học sinh rủi ro hạnh kiểm (trước đây quá sạch,
    # behavior_component ~100% LOW → không train được sub-model riêng).
    base_demerit = np.clip(3.0 - conduct * 1.2, 0.0, 7.0)

    # Persona modifier (khuếch đại mạnh hơn để tạo dải rủi ro rộng)
    for p_idx, p_name in enumerate(PERSONAS):
        mask = persona_idx == p_idx
        n_mask = mask.sum()
        if n_mask == 0:
            continue
        if p_name == "Academic_At_Risk":
            base_demerit[mask] *= RNG.uniform(2.0, 4.0, size=n_mask)
        elif p_name == "High_Achiever":
            base_demerit[mask] *= RNG.uniform(0.0, 0.2, size=n_mask)
        elif p_name == "Diligent_Average":
            base_demerit[mask] *= RNG.uniform(0.0, 0.6, size=n_mask)
        else:
            base_demerit[mask] *= RNG.uniform(0.5, 2.0, size=n_mask)

    # Poisson-distributed counts
    total_demerit_points = np.round(base_demerit, 2)

    # Repeat offenses và severe sanctions
    repeat_offense_count = np.clip(
        RNG.poisson(np.clip(total_demerit_points * 0.3, 0.1, 5.0)),
        0, 20,
    ).astype(np.int32)

    severe_sanction_count = np.clip(
        RNG.poisson(np.clip(total_demerit_points * 0.1, 0.0, 3.0)),
        0, 10,
    ).astype(np.int32)

    return {
        "total_demerit_points": total_demerit_points,
        "repeat_offense_count": repeat_offense_count,
        "severe_sanction_count": severe_sanction_count,
    }


# ============================================================================
# PHẦN 7: GROUND TRUTH COMPUTATION (65/15/10/10)
# ============================================================================

def compute_ground_truth(
    exam_scores: NDArray[np.float64],  # (N, N_SUBJECTS, N_EXAMS)
    lms_data: dict,
    attendance_data: dict,
    behavior_data: dict,
) -> dict:
    """
    Tính GROUND TRUTH (y) cho tất cả (student, subject) — vectorized.

    Công thức 65/15/10/10:
        final_grade = 0.65 × score_component
                    + 0.15 × lms_component
                    + 0.10 × attendance_component
                    + 0.10 × behavior_component

    Returns dict:
        - actual_final_grade: (N, N_SUBJECTS) — điểm tổng kết
        - actual_risk_level: (N, N_SUBJECTS) — nhãn rủi ro
        - is_at_risk: (N, N_SUBJECTS) — binary flag
    """
    N, NS, NE = exam_scores.shape

    # --- Score Component (65%): Weighted avg of ALL exams ---
    # (N, N_SUBJECTS, N_EXAMS) × (N_EXAMS,) → (N, N_SUBJECTS)
    total_weight = EXAM_COEFFS.sum()  # 1+2+3+3 = 9
    score_component = np.sum(
        exam_scores * EXAM_COEFFS[np.newaxis, np.newaxis, :],
        axis=2,
    ) / total_weight  # (N, N_SUBJECTS)

    # --- LMS Component (15%) ---
    # avg_score đã là (N, N_SUBJECTS), chuẩn hóa 0-10
    lms_component = lms_data["avg_score"]  # (N, N_SUBJECTS)

    # --- Attendance Component (10%) ---
    # daily_absence_rate: (N,) → (N, 1) broadcast
    # Hệ số 2.5 (trước 1.0) để nhạy hơn: nghỉ 15% → 6.25 (MODERATE), 25% → 3.75 (HIGH),
    # 35% → 1.25 (CRITICAL). Trước đây hệ số 1.0 khiến sub-model attendance gắn LOW cho
    # mọi học sinh (chỉ HIGH khi nghỉ >50%) — không phân biệt được học sinh nghỉ nhiều.
    absence_rate = attendance_data["daily_absence_rate"][:, np.newaxis]  # (N, 1)
    attend_component = np.clip(10.0 * (1.0 - absence_rate * 2.5), 0.0, 10.0)  # (N, N_SUBJECTS), broadcast

    # --- Behavior Component (10%) ---
    # Hệ số 1.0 (trước 0.3) để dải điểm trừ kỷ luật tạo đủ biến thiên rủi ro:
    # demerit 3.5 → 6.5 (MODERATE), 5 → 5.0 (HIGH), 6.5 → 3.5 (CRITICAL).
    demerit = behavior_data["total_demerit_points"][:, np.newaxis]  # (N, 1)
    behave_component = np.clip(10.0 - demerit * 1.0, 0.0, 10.0)  # (N, N_SUBJECTS)

    # --- Công thức tổng hợp ---
    latent_final_grade = (
        W_SCORE * score_component
        + W_LMS * lms_component
        + W_ATTEND * attend_component
        + W_BEHAVE * behave_component
    )
    actual_final_grade = np.clip(np.round(latent_final_grade, 1), 0.0, 10.0)

    # --- Mapping → risk level ---
    actual_risk_level = np.full((N, NS), "LOW", dtype=object)
    is_at_risk = np.zeros((N, NS), dtype=np.int32)

    for level, threshold in zip(RISK_LEVELS, RISK_THRESHOLDS + [0.0]):
        if level == "LOW":
            mask = actual_final_grade >= threshold
        elif level == "MODERATE":
            mask = (actual_final_grade >= threshold) & (actual_final_grade < RISK_THRESHOLDS[0])
        elif level == "HIGH":
            mask = (actual_final_grade >= threshold) & (actual_final_grade < RISK_THRESHOLDS[1])
        else:  # CRITICAL
            mask = actual_final_grade < RISK_THRESHOLDS[2]
        actual_risk_level[mask] = level

    is_at_risk = (actual_final_grade < 5.0).astype(np.int32)

    return {
        "actual_final_grade": actual_final_grade,
        "actual_risk_level": actual_risk_level,
        "is_at_risk": is_at_risk,
        # Component riêng từng yếu tố (0-10) — dùng làm target riêng cho từng sub-model
        # trong factor-ensemble, thay vì dùng chung actual_risk_level (rủi ro TỔNG).
        "score_component": score_component,
        "lms_component": lms_component,
        "attendance_component": attend_component,
        "behavior_component": behave_component,
    }


# ============================================================================
# PHẦN 8: FEATURE EXTRACTION TẠI CHECKPOINT
# ============================================================================

def compute_features_at_checkpoint(
    exam_scores: NDArray[np.float64],  # (N, N_SUBJECTS, N_EXAMS)
    exam_weeks: NDArray[np.int32],     # (N_EXAMS,) — tuần thực tế của từng bài KT
    lms_data: dict,
    attendance_data: dict,
    behavior_data: dict,
    checkpoint_week: int,
    semester_idx: int,
    students: dict,
) -> pd.DataFrame:
    """
    Tính 22 features (9 temporal + 6 LMS + 4 attendance + 3 behavior) cho tất cả (student, subject) tại 1 checkpoint.
    LMS theo 3 bucket (NỘP / BỎ KHÔNG LÀM / CHUYỂN TRƯỜNG) — mirror feature_extractor serve-side.

    Chỉ dùng dữ liệu đến checkpoint_week (temporal asymmetry).
    Thêm noise 5% vào features.

    Returns: DataFrame với (N × N_SUBJECTS) rows.
    """
    N, NS, NE = exam_scores.shape
    n_days = attendance_data["daily_status"].shape[1]

    # === Xác định tuần thực tế ===
    # Semester 1: tuần 1-18, Semester 2: tuần 19-36
    sem_offset = 0 if semester_idx == 1 else 18

    # === TEMPORAL FEATURES (9) ===
    # Chỉ dùng các bài kiểm tra đã diễn ra trước checkpoint
    exam_mask = (exam_weeks + sem_offset) <= checkpoint_week  # (N_EXAMS,)

    # weighted_early_avg: nửa đầu các bài đã có
    # weighted_late_avg: nửa sau các bài đã có
    seen_exam_indices = np.where(exam_mask)[0]
    n_seen = len(seen_exam_indices)

    if n_seen == 0:
        # Fallback: chưa có bài nào
        weighted_early = np.zeros((N, NS))
        weighted_late = np.zeros((N, NS))
        score_slope = np.zeros((N, NS))
        score_volatility = np.zeros((N, NS))
        max_drop = np.zeros((N, NS))
        last_score = np.zeros((N, NS))
        max_coeff = np.zeros((N, NS))
        hw_count = np.zeros((N, NS), dtype=np.int32)
        last_hw = np.zeros((N, NS))
    else:
        seen_scores = exam_scores[:, :, exam_mask]  # (N, NS, n_seen)
        seen_coeffs = EXAM_COEFFS[exam_mask]  # (n_seen,)

        # weighted_early_avg: nửa đầu
        mid = max(1, n_seen // 2)
        early_s = seen_scores[:, :, :mid]
        early_c = seen_coeffs[:mid]
        weighted_early = np.sum(early_s * early_c[np.newaxis, np.newaxis, :], axis=2) / early_c.sum()

        # weighted_late_avg: nửa sau
        if mid < n_seen:
            late_s = seen_scores[:, :, mid:]
            late_c = seen_coeffs[mid:]
            weighted_late = np.sum(late_s * late_c[np.newaxis, np.newaxis, :], axis=2) / late_c.sum()
        else:
            weighted_late = weighted_early.copy()

        # score_slope: OLS slope theo tuần
        if n_seen >= 2:
            x = exam_weeks[exam_mask].astype(np.float64)
            y = seen_scores  # (N, NS, n_seen)
            x_mean = x.mean()
            y_mean = y.mean(axis=2, keepdims=True)
            numer = ((x - x_mean) * (y - y_mean)).sum(axis=2)
            denom = ((x - x_mean) ** 2).sum()
            score_slope = np.where(denom > 0, numer / denom, 0.0)
        else:
            score_slope = np.zeros((N, NS))

        # score_volatility
        score_volatility = np.std(seen_scores, axis=2) if n_seen >= 2 else np.zeros((N, NS))

        # max_drop
        if n_seen >= 2:
            diffs = np.diff(seen_scores, axis=2)  # (N, NS, n_seen-1)
            max_drop = np.abs(np.minimum(diffs, 0)).max(axis=2)
        else:
            max_drop = np.zeros((N, NS))

        # last_score
        last_score = seen_scores[:, :, -1]

        # max_coefficient_so_far
        max_coeff = seen_coeffs.max()

        # high_weight_score_count (coeff >= 2)
        hw_mask = seen_coeffs >= 2
        hw_count = hw_mask.sum()

        # last_high_weight_score
        hw_indices = np.where(hw_mask)[0]
        if len(hw_indices) > 0:
            last_hw = seen_scores[:, :, hw_indices[-1]]
        else:
            last_hw = last_score.copy()

    # === LMS FEATURES (5) ===
    #   • NỘP            : submitted > 0                  → avg thực, rate = submitted/expected
    #   • BỎ KHÔNG LÀM   : submitted = 0 AND expected > 0 → rate = 0.0 (phạt rủi ro), avg = NULL
    #   • CHUYỂN TRƯỜNG  : submitted = 0 AND expected = 0 → rate = NULL (không phạt), avg = NULL
    # expected (đáng lẽ nộp) = số bài do trong cửa sổ hiện diện [join_week, checkpoint].
    # Generator: 1 assignment/tuần → expected = số tuần từ join đến checkpoint.
    weeks_so_far = min(checkpoint_week - sem_offset, 18)

    # Tuần nhập học cục bộ (local week 1..18) trong học kỳ này.
    #   join trước học kỳ → có mặt từ đầu (local_join = 1);
    #   join trong học kỳ → local_join = tuần join (19..36 ở HK1 → >18 → chưa có mặt).
    sem_start_global = 1 if semester_idx == 1 else 19
    jw = students["join_week_global"]  # (N,) global week 1..36
    local_join = np.where(
        jw < sem_start_global,
        1,
        jw - sem_start_global + 1,
    ).astype(np.float64)  # (N,)

    # Đã có mặt tại checkpoint? (local_join <= weeks_so_far)
    present_at_ck = local_join <= weeks_so_far  # (N,)

    # expected: số assignment do trong [join, checkpoint]
    expected = np.where(present_at_ck, weeks_so_far - local_join + 1, 0)  # (N,)

    # Weekly scores trong cửa sổ hiện diện: che các tuần trước khi nhập học → NaN
    weekly = lms_data["weekly_scores"][:, :, :weeks_so_far]  # (N, NS, weeks_so_far)
    week_idx = (np.arange(weeks_so_far) + 1).astype(np.float64)  # 1-based
    in_window = local_join[:, np.newaxis] <= week_idx[np.newaxis, :]  # (N, weeks_so_far)
    weekly_eff = np.where(in_window[:, np.newaxis, :], weekly, np.nan)  # (N, NS, weeks_so_far)

    submitted = (~np.isnan(weekly_eff)).sum(axis=2)  # (N, NS)
    exp2d = expected[:, np.newaxis]  # (N, 1) → broadcast (N, NS)

    # submission rate: submitted>0 → thực; submitted=0 & expected>0 → 0.0; else NULL
    with np.errstate(invalid="ignore", divide="ignore"):
        lms_submission_rate = np.where(
            submitted > 0,
            submitted / np.maximum(exp2d, 1),
            np.where(exp2d > 0, 0.0, np.nan),
        )

    # avg score theo 3 bucket (đồng bộ serve-side feature_extractor):
    #   • NỘP            : submitted > 0                  → avg thực
    #   • BỎ KHÔNG LÀM   : submitted = 0 AND expected > 0 → 0.0 (có trách nhiệm, phạt rủi ro)
    #   • CHUYỂN TRƯỜNG  : submitted = 0 AND expected = 0 → NaN (không phạt)
    with np.errstate(invalid="ignore"):
        lms_avg = np.nanmean(weekly_eff, axis=2)  # (N, NS)
    lms_avg = np.where(
        (submitted == 0) & (exp2d > 0),
        0.0,
        lms_avg,
    )

    # recent = 4 tuần gần nhất (do trong [cutoff-28, cutoff])
    recent_weeks = min(weeks_so_far, 4)
    if recent_weeks > 0:
        recent_expected = np.where(
            present_at_ck,
            weeks_so_far - np.maximum(local_join, weeks_so_far - 3) + 1,
            0,
        )  # (N,)
        recent_weekly = weekly_eff[:, :, -recent_weeks:]  # (N, NS, recent_weeks)
        recent_submitted = (~np.isnan(recent_weekly)).sum(axis=2)
        recent_exp2d = recent_expected[:, np.newaxis]
        with np.errstate(invalid="ignore", divide="ignore"):
            lms_recent_sub_rate = np.where(
                recent_submitted > 0,
                recent_submitted / np.maximum(recent_exp2d, 1),
                np.where(recent_exp2d > 0, 0.0, np.nan),
            )
        with np.errstate(invalid="ignore"):
            lms_recent_avg = np.nanmean(recent_weekly, axis=2)  # NULL nếu không nộp
        lms_recent_avg = np.where(
            (recent_submitted == 0) & (recent_exp2d > 0),
            0.0,
            lms_recent_avg,
        )
        # drop = lms_avg - COALESCE(recent_avg, lms_avg) (mirror feature_extractor)
        lms_recent_avg_clean = np.where(np.isnan(lms_recent_avg), lms_avg, lms_recent_avg)
        lms_recent_drop = lms_avg - lms_recent_avg_clean  # NULL nếu lms_avg NULL
    else:
        lms_recent_sub_rate = np.full((N, NS), np.nan)
        lms_recent_avg = np.full((N, NS), np.nan)
        lms_recent_drop = np.full((N, NS), np.nan)

    # lms_gradebook_gap = lms_avg - last_score (NULL nếu lms_avg NULL; last_score luôn có trong train)
    lms_gradebook_gap = lms_avg - last_score

    # === ATTENDANCE FEATURES (4) ===
    # Tính đến checkpoint: xác định số ngày học
    days_so_far = int(n_days * (checkpoint_week - sem_offset) / 18)
    days_so_far = np.clip(days_so_far, 1, n_days)

    daily_status_partial = attendance_data["daily_status"][:, :days_so_far]

    daily_absence_rate = ((daily_status_partial == 1) | (daily_status_partial == 2)).sum(axis=1) / days_so_far
    unexcused_absent_rate = (daily_status_partial == 1).sum(axis=1) / days_so_far
    excused_absent_days = (daily_status_partial == 2).sum(axis=1)
    total_late_count = (daily_status_partial == 3).sum(axis=1)

    # === BEHAVIOR FEATURES (3) ===
    # Các behavior features đã là toàn kỳ (không thay đổi theo checkpoint)
    total_demerit_points = behavior_data["total_demerit_points"]
    repeat_offense_count = behavior_data["repeat_offense_count"]
    severe_sanction_count = behavior_data["severe_sanction_count"]

    # === GHÉP THÀNH DATAFRAME ===
    rows = []
    for i in range(N):
        for s_idx in range(NS):
            row = {
                "student_code": students["codes"][i],
                "so_school_id": int(students["schools"][i]),
                "subject_id": SUBJECT_IDS[s_idx],
                "school_year_id": 2025,
                "semester_index": semester_idx,
                "evaluated_at_week": checkpoint_week,
                "subject_category": SUBJECT_CATEGORIES[s_idx],
                "grade_level": int(students["grades"][i]),
                # Temporal (9)
                "weighted_early_avg": round(float(weighted_early[i, s_idx]), 2),
                "weighted_late_avg": round(float(weighted_late[i, s_idx]), 2),
                "score_slope": round(float(score_slope[i, s_idx]), 4),
                "score_volatility": round(float(score_volatility[i, s_idx]), 4),
                "max_drop": round(float(max_drop[i, s_idx]), 2),
                "last_score": round(float(last_score[i, s_idx]), 2),
                "max_coefficient_so_far": round(float(max_coeff[i, s_idx]) if isinstance(max_coeff, np.ndarray) else float(max_coeff), 2),
                "high_weight_score_count": int(hw_count[i, s_idx]) if isinstance(hw_count, np.ndarray) else int(hw_count),
                "last_high_weight_score": round(float(last_hw[i, s_idx]), 2),
                # LMS (5)
                "lms_avg_score": round(float(lms_avg[i, s_idx]), 2),
                "lms_recent_drop": round(float(lms_recent_drop[i, s_idx]), 2),
                "lms_submission_rate": round(float(lms_submission_rate[i, s_idx]), 4),
                "lms_recent_submission_rate": round(float(lms_recent_sub_rate[i, s_idx]), 4),
                "lms_gradebook_gap": round(float(lms_gradebook_gap[i, s_idx]), 2),
                # Attendance (4)
                "daily_absence_rate": round(float(daily_absence_rate[i]), 4),
                "unexcused_absent_rate": round(float(unexcused_absent_rate[i]), 4),
                "excused_absent_days": int(excused_absent_days[i]),
                "total_late_count": int(total_late_count[i]),
                # Behavior (3)
                "total_demerit_points": round(float(total_demerit_points[i]), 2),
                "repeat_offense_count": int(repeat_offense_count[i]),
                "severe_sanction_count": int(severe_sanction_count[i]),
                # Ground Truth — sẽ được gán sau
                "actual_final_grade": 0.0,
                "actual_risk_level": "",
                "is_at_risk": 0,
            }
            rows.append(row)

    return pd.DataFrame(rows)


def add_noise_to_features(df: pd.DataFrame, noise_level: float = FEATURE_NOISE_LEVEL) -> pd.DataFrame:
    """
    Thêm noise ngẫu nhiên vào features để chống overfitting.
    Chỉ tác động lên cột numeric features, không tác động lên ground truth.
    """
    feature_cols = [
        "weighted_early_avg", "weighted_late_avg", "score_slope",
        "score_volatility", "max_drop", "last_score",
        "max_coefficient_so_far", "high_weight_score_count", "last_high_weight_score",
        "lms_avg_score", "lms_recent_drop", "lms_submission_rate",
        "lms_recent_submission_rate", "lms_gradebook_gap",
        "daily_absence_rate", "unexcused_absent_rate",
        "excused_absent_days", "total_late_count",
        "total_demerit_points", "repeat_offense_count", "severe_sanction_count",
    ]

    df_noisy = df.copy()
    for col in feature_cols:
        if col in df_noisy.columns:
            values = df_noisy[col].values.astype(np.float64)
            noise = RNG.uniform(1.0 - noise_level, 1.0 + noise_level, size=len(values))
            noisy_values = values * noise
            # Làm tròn giữ nguyên kiểu dữ liệu gốc
            if col in ("excused_absent_days", "total_late_count", "repeat_offense_count",
                       "severe_sanction_count", "high_weight_score_count"):
                df_noisy[col] = np.round(noisy_values).astype(np.int32)
            elif col in ("score_slope", "score_volatility"):
                df_noisy[col] = np.round(noisy_values, 4)
            elif col in ("lms_submission_rate", "lms_recent_submission_rate",
                         "daily_absence_rate", "unexcused_absent_rate"):
                df_noisy[col] = np.clip(np.round(noisy_values, 4), 0.0, 1.0)
            else:
                df_noisy[col] = np.round(noisy_values, 2)
    return df_noisy


# ============================================================================
# PHẦN 9: MAIN PIPELINE
# ============================================================================

def generate_training_dataset(n_students: int = 1028) -> pd.DataFrame:
    """
    Pipeline chính: sinh toàn bộ training dataset.

    Steps:
        1. Sinh latent variables (TAD-PG)
        2. Sinh exam score trajectory
        3. Sinh LMS, attendance, behavior data
        4. Tính Ground Truth (65/15/10/10)
        5. Với mỗi checkpoint, tính features (X)
        6. Thêm noise 5% vào features
        7. Merge features + ground truth
        8. Export CSV
    """
    t_start = time.time()
    print(f"[START] Generating EWS training dataset for {n_students} students...")
    print(f"   Expected rows: {n_students} x {N_SUBJECTS} x 2 semesters x {N_CHECKPOINTS} checkpoints")
    print(f"                 = {n_students * N_SUBJECTS * 2 * N_CHECKPOINTS:,} rows\n")

    # === Bước 1: Sinh latent variables ===
    print("[PERSONA] [1/7] Generating latent variables (TAD-PG)...")
    students = generate_students(n_students)
    persona_counts = np.bincount(students["persona_idx"], minlength=len(PERSONAS))
    for p_idx, p_name in enumerate(PERSONAS):
        print(f"       {p_name}: {persona_counts[p_idx]} students")
    profile_counts = np.bincount(students["profile_idx"], minlength=len(PROFILES))
    for p_idx, p_name in enumerate(PROFILES):
        print(f"       Profile {p_name}: {profile_counts[p_idx]} students")

    # === Bước 2: Sinh exam scores ===
    print("\n[SCORE] [2/7] Generating exam score trajectories...")
    exam_scores = generate_exam_scores(students)
    total_exams = exam_scores.shape[0] * exam_scores.shape[1] * exam_scores.shape[2]
    print(f"       Generated {total_exams:,} exam scores ({exam_scores.shape})")

    # === Bước 3: Sinh LMS, attendance, behavior ===
    print("\n[LMS] [3/7] Generating LMS data...")
    lms_data = generate_lms_data(students)

    print("[ATTEND] [4/7] Generating attendance data...")
    attendance_data = generate_attendance_data(students)

    print("[BEHAVE] [5/7] Generating behavior data...")
    behavior_data = generate_behavior_data(students)

    # === Bước 4: Tính Ground Truth ===
    print("\n[GT] [6/7] Computing Ground Truth (65/15/10/10)...")
    gt = compute_ground_truth(exam_scores, lms_data, attendance_data, behavior_data)

    # Phân phối risk levels
    risk_levels_flat = gt["actual_risk_level"].flatten()
    for level in RISK_LEVELS:
        count = (risk_levels_flat == level).sum()
        print(f"       {level}: {count} ({count / len(risk_levels_flat) * 100:.1f}%)")

    # === Bước 5-7: Features tại checkpoint + Noise + Merge ===
    print(f"\n[FEAT] [7/7] Computing features at checkpoints + noise...")

    all_dfs = []
    sem_offsets = {1: 0, 2: 18}

    for sem_config in SEMESTER_CONFIGS:
        sem_idx = sem_config["idx"]
        weeks = sem_config["weeks"]

        # Tuần thực tế của các bài kiểm tra trong học kỳ này
        exam_weeks = np.round(EXAM_WEEK_FRAC * sem_config["total_weeks"]).astype(np.int32)

        for cw in weeks:
            t_ck = time.time()
            df_ck = compute_features_at_checkpoint(
                exam_scores=exam_scores,
                exam_weeks=exam_weeks,
                lms_data=lms_data,
                attendance_data=attendance_data,
                behavior_data=behavior_data,
                checkpoint_week=int(cw),
                semester_idx=sem_idx,
                students=students,
            )

            # Gắn ground truth vào DataFrame
            # Lưu ý: attendance_component & behavior_component là (N, 1) — không đổi theo môn,
            # nên dùng [:, 0] và gán cho mọi subject (broadcast).
            for s_idx in range(N_SUBJECTS):
                mask = df_ck["subject_id"] == SUBJECT_IDS[s_idx]
                df_ck.loc[mask, "actual_final_grade"] = gt["actual_final_grade"][:, s_idx]
                df_ck.loc[mask, "actual_risk_level"] = gt["actual_risk_level"][:, s_idx]
                df_ck.loc[mask, "is_at_risk"] = gt["is_at_risk"][:, s_idx]
                df_ck.loc[mask, "score_component"] = gt["score_component"][:, s_idx]
                df_ck.loc[mask, "lms_component"] = gt["lms_component"][:, s_idx]
                df_ck.loc[mask, "attendance_component"] = gt["attendance_component"][:, 0]
                df_ck.loc[mask, "behavior_component"] = gt["behavior_component"][:, 0]

            # Thêm noise
            df_ck = add_noise_to_features(df_ck)

            all_dfs.append(df_ck)
            print(f"       Week {cw:2d} (Sem {sem_idx}): {len(df_ck):,} rows - "
                  f"{time.time() - t_ck:.2f}s")

    # === Gộp tất cả checkpoints ===
    print("\n[MERGE] Merging all checkpoints...")
    final_df = pd.concat(all_dfs, ignore_index=True)

    # Sắp xếp cột theo schema
    column_order = [
        "student_code", "so_school_id", "subject_id", "school_year_id", "semester_index", "evaluated_at_week",
        "subject_category", "grade_level",
        "weighted_early_avg", "weighted_late_avg", "score_slope", "score_volatility", "max_drop",
        "last_score", "max_coefficient_so_far", "high_weight_score_count", "last_high_weight_score",
        "lms_avg_score", "lms_recent_drop", "lms_submission_rate", "lms_recent_submission_rate", "lms_gradebook_gap",
        "daily_absence_rate", "unexcused_absent_rate", "excused_absent_days", "total_late_count",
        "total_demerit_points", "repeat_offense_count", "severe_sanction_count",
        "score_component", "lms_component", "attendance_component", "behavior_component",
        "actual_final_grade", "actual_risk_level", "is_at_risk",
    ]
    final_df = final_df[column_order]

    t_elapsed = time.time() - t_start
    print(f"\n[DONE] Generated {len(final_df):,} rows in {t_elapsed:.2f}s")
    print(f"   Shape: {final_df.shape}")
    print(f"   Memory: {final_df.memory_usage(deep=True).sum() / 1024 / 1024:.1f} MB")

    return final_df


# ============================================================================
# PHẦN 10: CLI & EXPORT
# ============================================================================

def export_to_csv(df: pd.DataFrame, path: str = CSV_PATH):
    """Export DataFrame to CSV."""
    print(f"\n[CSV] Exporting to {path}...")
    df.to_csv(path, index=False)
    file_size = os.path.getsize(path) / 1024 / 1024
    print(f"   [OK] Saved! File size: {file_size:.1f} MB")


# Các cột tồn tại trong bảng s360.train_student_subject_risk_dataset (schema).
# DataFrame có thể chứa thêm cột phụ (subject_category, grade_level, *_component)
# chỉ dùng cho CSV/EDA — phải lọc bỏ trước khi insert vào DB.
_SCHEMA_COLS = [
    "student_code", "so_school_id", "subject_id", "school_year_id",
    "semester_index", "evaluated_at_week",
    "weighted_early_avg", "weighted_late_avg", "score_slope", "score_volatility",
    "max_drop", "last_score", "max_coefficient_so_far", "high_weight_score_count",
    "last_high_weight_score",
    "lms_avg_score", "lms_recent_drop", "lms_submission_rate",
    "lms_recent_submission_rate", "lms_gradebook_gap",
    "daily_absence_rate", "unexcused_absent_rate", "excused_absent_days",
    "total_late_count",
    "total_demerit_points", "repeat_offense_count", "severe_sanction_count",
    "actual_final_grade", "actual_risk_level", "is_at_risk",
]


def export_to_db(df: pd.DataFrame, connection_string: Optional[str] = None):
    """
    Export DataFrame to s360.train_student_subject_risk_dataset.
    Optional — chỉ dùng khi có DB connection.
    """
    if connection_string is None:
        print("\n[SKIP] DB export skipped (no connection string provided)")
        return

    try:
        from sqlalchemy import create_engine
        engine = create_engine(connection_string)

        # Chỉ giữ các cột có trong schema (bỏ cột phụ chỉ dùng cho CSV/EDA)
        missing = [c for c in _SCHEMA_COLS if c not in df.columns]
        if missing:
            print(f"   [WARN] Thiếu cột so với schema (bỏ qua): {missing}")
        export_df = df[[c for c in _SCHEMA_COLS if c in df.columns]].copy()

        # Batch insert với chunk size 10,000 — dùng executemany (mặc định) thay vì
        # method="multi" để tránh tạo INSERT khổng lồ gây timeout.
        chunk_size = 10000
        n_chunks = (len(export_df) + chunk_size - 1) // chunk_size

        print(f"\n[DB] Exporting to DB ({n_chunks} chunks of {chunk_size})...")
        for i in range(0, len(export_df), chunk_size):
            chunk = export_df.iloc[i:i + chunk_size]
            chunk.to_sql(
                "train_student_subject_risk_dataset",
                con=engine,
                schema="s360",
                if_exists="append",
                index=False,
            )
            print(f"       Chunk {i // chunk_size + 1}/{n_chunks}: {len(chunk)} rows")

        print("   [OK] DB export complete!")
    except Exception as e:
        print(f"   [WARN] DB export failed: {e}")
        print("   (CSV file is still available)")


def main():
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="EWS Training Data Generator")
    parser.add_argument("--n-students", type=int, default=1028,
                        help="Number of students to generate (default: 1028)")
    parser.add_argument("--csv", type=str, default=CSV_PATH,
                        help=f"CSV output path (default: {CSV_PATH})")
    parser.add_argument("--db", type=str, default=None,
                        help="Optional DB connection string for direct insert")
    parser.add_argument("--no-csv", action="store_true",
                        help="Skip CSV export")
    parser.add_argument("--seed", type=int, default=42,
                        help="Random seed (default: 42)")

    args = parser.parse_args()

    # Set seed
    global RNG
    RNG = np.random.default_rng(args.seed)

    # Generate
    df = generate_training_dataset(n_students=args.n_students)

    # Export
    if not args.no_csv:
        export_to_csv(df, args.csv)

    if args.db:
        export_to_db(df, args.db)

    print("\n[DONE] All done!")


if __name__ == "__main__":
    main()
