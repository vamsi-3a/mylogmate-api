---
name: auth-jwt-oauth
description: Use when implementing authentication, JWT token management, Google OAuth, password hashing, refresh tokens, forgot/reset password, or auth middleware. Trigger on app/core/security.py, app/api/v1/auth.py, or any auth-related work.
---

# Auth Patterns

## JWT Token Structure
- Access token: 15 min expiry, contains {user_id, username, is_admin, exp}
- Refresh token: 7 day expiry, stored in httpOnly secure cookie
- Signed with HS256 using JWT_SECRET_KEY from env

## Token Creation
```python
from jose import jwt
from datetime import datetime, timedelta, timezone

def create_access_token(user_id: str, username: str, is_admin: bool) -> str:
    payload = {
        "sub": user_id, "username": username, "is_admin": is_admin,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=15), "type": "access"
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm="HS256")

def create_refresh_token(user_id: str) -> str:
    payload = {
        "sub": user_id,
        "exp": datetime.now(timezone.utc) + timedelta(days=7), "type": "refresh"
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm="HS256")
```

## Password Hashing
```python
from passlib.context import CryptContext
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=12)

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)
```

## Google OAuth Flow
1. Frontend: initiates Google sign-in, receives ID token
2. Frontend: sends ID token to POST /api/v1/auth/google
3. Backend: verifies token with google-auth library
4. Backend: creates user if new (google_id, email), or finds existing
5. Backend: issues JWT access + refresh tokens
6. Auto-creates "Self" context for new users

## Forgot Password Flow
1. User sends email to POST /api/v1/auth/forgot-password
2. Backend generates JWT reset token (1 hour expiry, type="reset")
3. Celery task sends email via SMTP with reset link containing token
4. User clicks link → frontend sends new password + token to POST /api/v1/auth/reset-password
5. Backend verifies reset token, updates password hash

## Auth Dependency
```python
async def get_current_user(token: str = Depends(oauth2_scheme), db: AsyncSession = Depends(get_db)) -> User:
    payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=["HS256"])
    if payload.get("type") != "access":
        raise UnauthorizedError("Invalid token type")
    user = await UserService.get_by_id(db, payload["sub"])
    if not user or not user.is_active:
        raise UnauthorizedError("User not found or inactive")
    return user

async def get_admin_user(current_user: User = Depends(get_current_user)) -> User:
    if not current_user.is_admin:
        raise ForbiddenError("Admin access required")
    return current_user
```

## Security Rules
- NEVER log passwords or tokens
- Refresh token: httpOnly, Secure, SameSite=Lax cookie
- Rate limit auth endpoints: 5/min/IP
- On signup: auto-create "Self" context for the user
