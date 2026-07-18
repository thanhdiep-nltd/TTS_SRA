from pydantic import BaseModel, ConfigDict


class ORMBase(BaseModel):
    """Base cho các schema đọc từ ORM object (from_attributes)."""

    model_config = ConfigDict(from_attributes=True)
