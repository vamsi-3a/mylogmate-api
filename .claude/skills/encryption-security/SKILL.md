---
name: encryption-security
description: Use when implementing data encryption/decryption, handling sensitive data, managing encryption keys, or any security-related code. Trigger when working with log entry content storage or retrieval.
---

# Encryption & Security Patterns

## AES-256 Encryption (Fernet)
```python
from cryptography.fernet import Fernet
from app.core.config import settings

_cipher = Fernet(settings.ENCRYPTION_KEY)

def encrypt_content(plain_text: str) -> str:
    return _cipher.encrypt(plain_text.encode("utf-8")).decode("utf-8")

def decrypt_content(encrypted_text: str) -> str:
    return _cipher.decrypt(encrypted_text.encode("utf-8")).decode("utf-8")
```

## Usage in Services
```python
# On create/edit — encrypt before DB write
entry.content_encrypted = encrypt_content(payload.content)

# On read — decrypt before returning to API
response.content = decrypt_content(entry.content_encrypted)
```

## Key Generation
```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```
Store in ENCRYPTION_KEY env var. NEVER commit to code.

## Rules
- EVERY log entry content must be encrypted before DB insert
- EVERY log entry content must be decrypted at service layer for API response
- The Celery embedding task also decrypts content before generating embeddings
- Never cache decrypted content to disk — only in-memory during request
- Never log decrypted content
- Encryption key rotation: future consideration, not v1
