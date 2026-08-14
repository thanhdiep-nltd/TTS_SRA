"""Unit tests for Interdisciplinary Early Warning System (EWS) Service."""

from src.ews.interdisciplinary_service import (
    CLUSTERS_CONFIG,
    calculate_student_cluster_risk,
    get_clusters_list,
)
from src.ews.risk_config import RiskConfig


def test_get_clusters_list():
    clusters = get_clusters_list()
    assert len(clusters) == 2
    codes = [c["code"] for c in clusters]
    assert "STEM" in codes
    assert "WAR_AND_PEACE" in codes


def test_stem_single_math_subject():
    """Học sinh học 1 môn Toán thông thường + các môn STEM cơ bản."""
    student_info = {
        "student_code": "HS001",
        "student_name": "Nguyễn Văn A",
        "class_name": "7A1",
        "grade_id": 7,
    }
    predictions = [
        {"subject_code": "TOAN_7", "subject_name": "Toán 7", "risk_score": 30.0, "risk_level": "LOW"},
        {"subject_code": "LY", "subject_name": "Vật lý", "risk_score": 40.0, "risk_level": "MODERATE"},
        {"subject_code": "SINH", "subject_name": "Sinh học", "risk_score": 20.0, "risk_level": "LOW"},
        {"subject_code": "TIN", "subject_name": "Tin học", "risk_score": 10.0, "risk_level": "LOW"},
        {"subject_code": "ROBOTICS", "subject_name": "STEM Robotics", "risk_score": 25.0, "risk_level": "LOW"},
    ]
    res = calculate_student_cluster_risk(student_info, predictions, "STEM")
    assert res is not None
    assert res.student_code == "HS001"
    assert res.cluster_code == "STEM"
    # Weighted calculation: 30*0.3 + 40*0.2 + 20*0.2 + 10*0.15 + 25*0.15 = 9 + 8 + 4 + 1.5 + 3.75 = 26.25
    assert abs(res.cluster_risk_score - 26.25) < 0.1
    assert res.cluster_risk_level in ("LOW", "MODERATE")
    assert res.bottleneck_subject is None


def test_stem_multiple_math_subjects_mean_aggregation():
    """Học sinh học 2 môn Toán (Toán 7: 80.0, Toán Cambridge: 60.0) -> Trụ cột Toán lấy trung bình 70.0."""
    student_info = {
        "student_code": "HS002",
        "student_name": "Trần Thị B",
        "class_name": "7A1",
        "grade_id": 7,
    }
    predictions = [
        {"subject_code": "TOAN_7", "subject_name": "Toán 7", "risk_score": 80.0, "risk_level": "HIGH"},
        {"subject_code": "CAM_MATH", "subject_name": "Toán Cambridge", "risk_score": 60.0, "risk_level": "HIGH"},
        {"subject_code": "LY", "subject_name": "Vật lý", "risk_score": 50.0, "risk_level": "MODERATE"},
        {"subject_code": "SINH", "subject_name": "Sinh học", "risk_score": 40.0, "risk_level": "MODERATE"},
        {"subject_code": "TIN", "subject_name": "Tin học", "risk_score": 30.0, "risk_level": "LOW"},
    ]
    res = calculate_student_cluster_risk(student_info, predictions, "STEM")
    assert res is not None

    math_pillar = next(p for p in res.pillars if p.pillar_id == "math")
    assert math_pillar.risk_score == 70.0  # (80 + 60) / 2
    assert len(math_pillar.enrolled_subjects) == 2


def test_stem_elective_omitted_auto_reweighting():
    """Học sinh không học Robotics (chỉ học 4 môn Toán, Lý, Sinh, Tin) -> tự động re-weight trọng số đạt 100%."""
    student_info = {
        "student_code": "HS003",
        "student_name": "Lê Hoàng C",
        "class_name": "8A1",
        "grade_id": 8,
    }
    predictions = [
        {"subject_code": "TOAN_8", "subject_name": "Toán 8", "risk_score": 50.0, "risk_level": "MODERATE"},
        {"subject_code": "LY", "subject_name": "Vật lý", "risk_score": 50.0, "risk_level": "MODERATE"},
        {"subject_code": "SINH", "subject_name": "Sinh học", "risk_score": 50.0, "risk_level": "MODERATE"},
        {"subject_code": "TIN", "subject_name": "Tin học", "risk_score": 50.0, "risk_level": "MODERATE"},
    ]
    res = calculate_student_cluster_risk(student_info, predictions, "STEM")
    assert res is not None

    # Robotics is inactive
    robotics_pillar = next(p for p in res.pillars if p.pillar_id == "engineering")
    assert not robotics_pillar.is_active

    active_pillars = [p for p in res.pillars if p.is_active]
    assert len(active_pillars) == 4
    total_weights = sum(p.normalized_weight for p in active_pillars)
    assert abs(total_weights - 1.0) < 0.001
    assert abs(res.cluster_risk_score - 50.0) < 0.01


def test_bottleneck_detection():
    """Môn Toán bị 95.0 (CRITICAL) kéo tụt cả cụm STEM trong khi các môn khác điểm rủi ro rất thấp."""
    student_info = {
        "student_code": "HS004",
        "student_name": "Phạm Văn D",
        "class_name": "9A1",
        "grade_id": 9,
    }
    predictions = [
        {"subject_code": "TOAN_9", "subject_name": "Toán 9", "risk_score": 95.0, "risk_level": "CRITICAL"},
        {"subject_code": "LY", "subject_name": "Vật lý", "risk_score": 20.0, "risk_level": "LOW"},
        {"subject_code": "SINH", "subject_name": "Sinh học", "risk_score": 15.0, "risk_level": "LOW"},
        {"subject_code": "TIN", "subject_name": "Tin học", "risk_score": 10.0, "risk_level": "LOW"},
    ]
    res = calculate_student_cluster_risk(student_info, predictions, "STEM")
    assert res is not None
    assert res.bottleneck_subject == "Toán học"
    assert res.bottleneck_risk == 95.0
    # Penalty makes cluster risk higher than simple average
    assert res.cluster_risk_score > 40.0


def test_war_and_peace_cluster():
    """Kiểm tra cụm Chiến Tranh & Hòa Bình (Văn + Sử Địa + GDCD)."""
    student_info = {
        "student_code": "HS005",
        "student_name": "Vũ Thu E",
        "class_name": "9A2",
        "grade_id": 9,
    }
    predictions = [
        {"subject_code": "VAN", "subject_name": "Ngữ văn", "risk_score": 30.0, "risk_level": "LOW"},
        {"subject_code": "LS_DL", "subject_name": "Lịch sử & Địa lý", "risk_score": 25.0, "risk_level": "LOW"},
        {"subject_code": "GDCD", "subject_name": "Giáo dục công dân", "risk_score": 20.0, "risk_level": "LOW"},
    ]
    res = calculate_student_cluster_risk(student_info, predictions, "WAR_AND_PEACE")
    assert res is not None
    assert res.cluster_code == "WAR_AND_PEACE"
    # Weighted: 30*0.4 + 25*0.4 + 20*0.2 = 12 + 10 + 4 = 26.0
    assert abs(res.cluster_risk_score - 26.0) < 0.1
