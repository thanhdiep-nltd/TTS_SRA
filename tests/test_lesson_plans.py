# -*- coding: utf-8 -*-
"""Unit tests for Lesson Plans endpoints and schemas."""

from unittest.mock import MagicMock
from src.schemas.lesson_plan import CourseSummary, LessonPlanDetail, LessonTargetItem, UnitTreeItem


def test_lesson_plan_schemas():
    target = LessonTargetItem(
        id=1,
        code="TGT_01",
        name="Biết khái niệm tập hợp",
        description="Học sinh biết viết tập hợp",
        order_number=1,
    )
    assert target.id == 1
    assert target.code == "TGT_01"

    detail = LessonPlanDetail(
        lesson_id=3001,
        lesson_name="Tập hợp. Phần tử của tập hợp",
        lesson_code="TOAN6_HK1_C1_B1",
        period=2.0,
        order_number=1,
        unit_id=2001,
        unit_name="SỐ TỰ NHIÊN",
        unit_code="TOAN6_HK1_C1",
        course_id=1000,
        course_name="Toán 6 - Học kỳ 1",
        course_code="TOAN6_HK1",
        curriculum_unit_id=392,
        curriculum_unit_name="Tập hợp. Phần tử của tập hợp",
        plan_id=5001,
        plan_name="Giáo án Tập hợp",
        content_own="## I. MỤC TIÊU\n...",
        targets=[target],
        related_lms_questions_count=10,
    )
    assert detail.lesson_id == 3001
    assert detail.related_lms_questions_count == 10
    assert len(detail.targets) == 1
    assert detail.targets[0].name == "Biết khái niệm tập hợp"
