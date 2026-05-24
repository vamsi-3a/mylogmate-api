Prepare changes for commit:

1. Run `make lint` (ruff + mypy) — fix any issues
2. Run `make test` — fix any test failures  
3. Show `git diff --stat` for review
4. Suggest a Conventional Commit message based on the changes
5. Stage the changes with `git add`
6. Show the suggested commit command but DO NOT execute it — wait for my approval

Format: feat|fix|chore|refactor|test|docs: short description
