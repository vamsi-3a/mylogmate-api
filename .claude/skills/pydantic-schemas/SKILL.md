---
name: pydantic-schemas
description: Use when creating request/response schemas in app/schemas/. Covers Pydantic v2 patterns, field validation, ORM integration, nested schemas, custom validators. Trigger on any file in app/schemas/.
---

# Pydantic Schema Patterns

## Request Schema
```python
from pydantic import BaseModel, Field, field_validator
from datetime import date

class CreateLogRequest(BaseModel):
    context_id: str = Field(..., description="UUID of the context")
    content: str = Field(..., min_length=1, max_length=10000, description="Log entry text")
    date_type: str = Field(..., pattern="^(daily|weekly|custom)$")
    date_start: date
    date_end: date
    tag_ids: list[str] = Field(default_factory=list, max_length=20)

    @field_validator("date_end")
    @classmethod
    def end_after_start(cls, v, info):
        if info.data.get("date_start") and v < info.data["date_start"]:
            raise ValueError("date_end must be >= date_start")
        return v
```

## Response Schema
```python
class LogResponse(BaseModel):
    id: str
    context_id: str
    content: str  # Decrypted content (never encrypted in response)
    date_type: str
    date_start: date
    date_end: date
    tags: list[TagResponse] = []
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
```

## Rules
- Request schemas: Create*Request, Update*Request (Update uses Optional fields)
- Response schemas: *Response with model_config from_attributes=True
- Use Field() with min_length, max_length, pattern, ge, le for validation
- Use field_validator for cross-field validation
- Never expose password_hash, encryption keys, or internal IDs in responses
- Nest response schemas: LogResponse contains list[TagResponse]
- Common schemas in app/schemas/common.py: ApiResponse, PaginatedResponse, ErrorResponse
