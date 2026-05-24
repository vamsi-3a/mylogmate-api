---
path: app/api/**
---
- Routes are THIN. validate → service → ApiResponse. No business logic.
- Every protected route: Depends(get_current_user). Admin: Depends(get_admin_user).
- Always specify response_model and status_code.
- Response envelope: ApiResponse or PaginatedResponse.
- Never access DB directly in routes. Go through services.
