Write tests for the specified module:

1. Read the source code
2. Create test file mirroring app/ structure in tests/
3. Use fixtures from conftest.py (client, auth_headers, db_session)
4. Mock ALL externals (Groq, Qdrant, SMTP, Celery)
5. Write: happy path + auth failure (401) + validation error (422) + not found (404) + permission (403)
6. Run pytest on the new file and fix failures
7. Verify all tests pass

Module to test: $ARGUMENTS
