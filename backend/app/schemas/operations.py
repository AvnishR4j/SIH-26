from datetime import datetime
from typing import Literal

from app.schemas.auth import StrictModel

OperationType = Literal["enhance_image", "generate_listing"]
OperationStatus = Literal["queued", "running", "succeeded", "failed"]


class OperationError(StrictModel):
    code: str
    message: str
    details: dict[str, object]


class OperationResponse(StrictModel):
    id: str
    type: OperationType
    status: OperationStatus
    resource_type: Literal["draft"]
    resource_id: str
    poll_after_seconds: int
    error: OperationError | None
    created_at: datetime
    updated_at: datetime
