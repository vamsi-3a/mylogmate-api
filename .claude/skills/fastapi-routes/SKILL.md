---
name: fastapi-routes
description: Use when creating/modifying FastAPI route handlers in app/api/v1/. Covers endpoint structure, dependencies, response formatting, status codes, rate limiting, error handling. Trigger on any file in app/api/.
---

# FastAPI Route Patterns

## Route Template
```python
from fastapi import APIRouter, Depends, status
from app.api.deps import get_current_user, get_db
from app.schemas.common import ApiResponse
from app.schemas.logs import CreateLogRequest, LogResponse
from app.services.log_service import LogService

router = APIRouter(prefix="/logs", tags=["logs"])

@router.post("/", response_model=ApiResponse[LogResponse], status_code=status.HTTP_201_CREATED)
async def create_log(
    payload: CreateLogRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[LogResponse]:
    result = await LogService.create(db=db, user_id=current_user.id, payload=payload)
    return ApiResponse(data=result, message="Log created", success=True)
```

## Rules
- Always specify response_model and status_code
- Use Depends(get_current_user) for ALL protected routes
- Use Depends(get_admin_user) for admin-only routes
- Route is THIN: validate → service call → return. No logic here.
- Handle service exceptions with proper HTTP status codes via exception handlers
- List endpoints: return PaginatedResponse with page/page_size/total
- Use Query() params for GET filters: context_id, date_from, date_to, tag_ids, page, page_size
- Rate limit: auth endpoints 5/min/IP, AI recall 50/day/user (via slowapi)

## Response Envelope
```python
class ApiResponse(BaseModel, Generic[T]):
    data: T | None = None
    message: str = ""
    success: bool = True

class PaginatedResponse(ApiResponse[list[T]], Generic[T]):
    total: int
    page: int
    page_size: int
```

## Error Responses
```python
# 400
ApiResponse(success=False, message="Validation error", data=None)
# 401
ApiResponse(success=False, message="Invalid credentials")
# 404
ApiResponse(success=False, message="Log entry not found")
# 429
ApiResponse(success=False, message="Rate limit exceeded. Try again later.")
```

## Registering Routes
In app/main.py: `app.include_router(logs_router, prefix="/api/v1")`
