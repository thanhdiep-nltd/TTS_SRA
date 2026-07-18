from contextvars import ContextVar
from uuid import UUID

# Context variables for thread/task-safe propagation of user environment
current_user_school_id: ContextVar[UUID | None] = ContextVar("current_user_school_id", default=None)
current_user_role: ContextVar[str | None] = ContextVar("current_user_role", default=None)
current_user_id: ContextVar[UUID | None] = ContextVar("current_user_id", default=None)
