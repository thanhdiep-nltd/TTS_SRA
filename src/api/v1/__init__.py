from fastapi import APIRouter

from src.api.v1 import (
    analytics,
    analytics_v2,
    auth,
    chat,
    exam_papers,
    exam_validity,
    exams,
    gradebook,
    knowledge,
    mappings,
    notifications,
    question_bank,
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
api_router.include_router(exam_validity.router)
api_router.include_router(question_bank.router)
api_router.include_router(exams.router)
api_router.include_router(notifications.router)
api_router.include_router(chat.router)
api_router.include_router(recordings.router)

__all__ = ["api_router"]
