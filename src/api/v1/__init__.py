from fastapi import APIRouter

from src.api.v1 import (
    analytics,
    analytics_v2,
    auth,
    chat,
    curriculum,
    ews,
    exam_papers,
    exam_validity,
    exams,
    gradebook,
    knowledge,
    knowledge_gap,
    lesson_plans,
    mappings,
    notifications,
    pass_fail_forecast,
    question_bank,
    question_classify,
    recordings,
    reports,
    school,
    score_import,
    scores,
    students,
    users,
)

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(school.router)
api_router.include_router(students.router)
api_router.include_router(exam_papers.router)
api_router.include_router(knowledge.router)
# gradebook + mappings (route tĩnh /scores/gradebook, /scores/mappings...) phải đăng ký
# TRƯỚC scores.router để không bị /scores/{score_id} (động) che mất.
api_router.include_router(gradebook.router)
api_router.include_router(mappings.router)
api_router.include_router(score_import.router)
api_router.include_router(scores.router)
api_router.include_router(analytics.router)
api_router.include_router(reports.router)
api_router.include_router(analytics_v2.router)
api_router.include_router(ews.router)
api_router.include_router(exam_validity.router)
api_router.include_router(question_bank.router)
api_router.include_router(exams.router)
api_router.include_router(notifications.router)
api_router.include_router(chat.router)
api_router.include_router(curriculum.router)
api_router.include_router(recordings.router)
api_router.include_router(knowledge_gap.router)
api_router.include_router(lesson_plans.router)
api_router.include_router(pass_fail_forecast.router)
api_router.include_router(question_classify.router)

__all__ = ["api_router"]
