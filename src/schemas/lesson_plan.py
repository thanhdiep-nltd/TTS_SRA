# -*- coding: utf-8 -*-
"""Pydantic schemas for Lesson Plans (Kế hoạch bài dạy) & Curriculum pacing."""

from typing import List, Optional
from pydantic import BaseModel, Field


class SubjectOption(BaseModel):
    """Môn học."""
    id: int
    code: str
    name: str
    has_lesson_plans: bool = False
    grade_id: Optional[int] = None


class GradeOption(BaseModel):
    """Khối lớp."""
    id: int
    name: str
    has_lesson_plans: bool = False


class LessonTargetItem(BaseModel):
    """Mục tiêu kiến thức / năng lực của bài học."""
    id: int
    code: str
    name: str
    description: Optional[str] = None
    order_number: int = 1


class LessonPlanBrief(BaseModel):
    """Thông tin tóm tắt bài học trong cây phân cấp."""
    id: int
    code: str
    name: str
    period: float
    order_number: int
    unit_id: int
    curriculum_unit_id: Optional[int] = None
    curriculum_unit_name: Optional[str] = None
    has_plan: bool = True
    target_count: int = 0
    content_length: int = 0


class UnitTreeItem(BaseModel):
    """Chương trong cây phân cấp khóa học."""
    id: int
    code: str
    name: str
    order_number: int
    period: float
    lessons: List[LessonPlanBrief] = []


class CourseTreeItem(BaseModel):
    """Khóa học kèm cấu trúc cây Chương và Bài học."""
    id: int
    code: str
    name: str
    period: float
    description: Optional[str] = None
    units: List[UnitTreeItem] = []


class CourseSummary(BaseModel):
    """Tóm tắt khóa học."""
    id: int
    code: str
    name: str
    period: float
    description: Optional[str] = None
    unit_count: int = 0
    lesson_count: int = 0


class LessonPlanDetail(BaseModel):
    """Chi tiết đầy đủ của một Giáo án bài dạy."""
    lesson_id: int
    lesson_name: str
    lesson_code: str
    period: float
    order_number: int
    unit_id: int
    unit_name: str
    unit_code: str
    course_id: int
    course_name: str
    course_code: str
    
    # Mỏ neo SGK
    curriculum_unit_id: Optional[int] = None
    curriculum_unit_name: Optional[str] = None
    curriculum_summary: Optional[str] = None
    curriculum_keywords: Optional[List[str]] = None
    
    # Nội dung giáo án
    plan_id: Optional[int] = None
    plan_name: Optional[str] = None
    content_own: Optional[str] = None
    description: Optional[str] = None
    
    # Mục tiêu & tích hợp
    targets: List[LessonTargetItem] = []
    related_lms_questions_count: int = 0
