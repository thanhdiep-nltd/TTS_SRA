"""Script kiểm tra import và chạy nhanh các unit logic thuần của M0..M4."""

import sys

try:
    # 1. Module M0 & DB Models
    import src.models.tables as tables
    import src.models.s360_tables as s360_tables
    print("✓ Model tables OK (AssignmentCompetency, StudentKnowledgeGap, DimSoAssignment, FactSoAssignmentGrade)")

    # 2. Module M1 (Content Difficulty)
    import src.services.content_difficulty as cd
    from src.schemas.exam_analysis import ExamContentAnalysis
    print("✓ Content Difficulty (CDI, Bloom Distribution, Semantic Distance) OK")

    # 3. Module M2 (Knowledge Gap)
    from src.services.knowledge_gap import UnitWeight, compute_unit_mastery, aggregate_class_gaps
    units = [UnitWeight(unit_id=1, weight=0.5, bloom_level=2), UnitWeight(unit_id=2, weight=0.5, bloom_level=5)]
    gaps = compute_unit_mastery(6.0, 10.0, units)
    assert len(gaps) == 2
    print("✓ Knowledge Gap logic OK")

    # 4. Module M3 (LMS Evidence)
    from src.ews.lms_evidence import LmsAssignmentEvidence, classify_lms_behavior, mark_missing_in_exam
    sample_lms = [
        LmsAssignmentEvidence(unit_name="Chương 1", final_grade=3.0, active_time_sec=1500, time_limit_sec=1800, rte=1),
        LmsAssignmentEvidence(unit_name="Chương 2", final_grade=2.0, rte=0),
        LmsAssignmentEvidence(unit_name="Chương 3", final_grade=3.0, active_time_sec=100, time_spent_sec=1000, tab_hidden_count=4),
        LmsAssignmentEvidence(unit_name="Chương 4", submitted=False),
    ]
    patterns = classify_lms_behavior(sample_lms)
    assert {p.pattern for p in patterns} == {"EFFORT_BUT_LOST", "RUSHED", "OFF_TASK", "SKIPPED"}
    print("✓ LMS Evidence classification & noise filtering OK")

    # 5. Module M4 (Pass/Fail Forecast)
    from src.services.pass_fail_forecast import StudentAbility, ExamUnit, forecast_exam, summarize
    students = [
        StudentAbility(student_code="S1", ability={1: 8.0, 2: 7.0}),
        StudentAbility(student_code="S2", ability={1: 3.0, 2: 4.0}),
    ]
    exam_units = [ExamUnit(unit_id=1, weight=0.6), ExamUnit(unit_id=2, weight=0.4)]
    forecasts = forecast_exam(students, exam_units, cdi=0.45)
    summary = summarize(forecasts)
    assert summary["total"] == 2
    print("✓ Pass/Fail Forecast logic OK")

    # 6. Routers & Tools
    import src.api.v1.knowledge_gap
    import src.api.v1.pass_fail_forecast
    import src.agents.data_service_agent.tools
    print("✓ API Routers and Agent Tools OK")

    print("\n==========================================")
    print("🎉 TẤT CẢ MODULES M0 -> M4 ĐÃ ĐƯỢC KIỂM TRA THÀNH CÔNG!")
    print("==========================================")

except Exception as e:
    print(f"❌ ERROR: {e}")
    sys.exit(1)
